"""Deterministic backend-only Manhattan routing against fixed placed geometry.

Low-bend candidates precede a direction-aware compressed visibility-grid A*.
Net trees share projected attachments. A complete no-crossing pass is retried
under bounded deterministic net orders before a verified unsplit-X fallback.
A greedy failure is NOT a proof that no planar solution exists. Complexity and
budgets are recorded in RoutingOptions; no full-grid raster search is used.
"""
from __future__ import annotations

import heapq
from typing import Any, Mapping

from app.services.asc_validation import ERROR, ExportDiagnostic, NetGeometry, WireSegment, validate_net_geometry
from app.services.connectivity import ConnectivityModel, validate_connectivity
from app.services.grid_system import GridSystem, Point
from app.services.production import checkpoint
from .geometry import CollisionDetector, axis, manhattan, on_segment, prepare_problem
from .models import RoutedFlag, RoutingOptions, RoutingProblem, RoutingResult, SafeCrossing
from .optimizer import normalize_segments, path_segments


class _BudgetExceeded(Exception):
    pass


class _Router:
    def __init__(self, problem: RoutingProblem, metrics: dict[str, int]):
        self.problem = problem
        self.options = problem.options
        self.detector = CollisionDetector(problem)
        self.metrics = metrics
        self.failures: list[ExportDiagnostic] = []

    def _accept(self, segments: list[WireSegment], occupied: list[WireSegment],
                crossings: list[SafeCrossing], fallback: bool) -> list[SafeCrossing] | None:
        pending = list(crossings)
        for segment in segments:
            self.metrics["collision_checks"] += 1
            valid, added = self.detector.segment_allowed(segment, occupied, pending, allow_crossings=fallback)
            if not valid:
                return None
            for crossing in added:
                if crossing not in pending:
                    pending.append(crossing)
        return pending

    def _goals(self, start: Point, tree: list[WireSegment], occupied: list[WireSegment],
               crossings: list[SafeCrossing], net: str) -> list[Point]:
        points: set[Point] = set()
        for segment in tree:
            points.update((segment.start, segment.end))
            if axis(segment) == "h":
                points.add((max(min(start[0], max(segment.start[0], segment.end[0])), min(segment.start[0], segment.end[0])), segment.start[1]))
            else:
                points.add((segment.start[0], max(min(start[1], max(segment.start[1], segment.end[1])), min(segment.start[1], segment.end[1]))))
        return sorted((p for p in points if self.detector.point_allowed(p, net, occupied, crossings)),
                      key=lambda p: (manhattan(start, p), p))

    def _lanes(self, start: Point, goals: list[Point], occupied: list[WireSegment], margin: int) -> tuple[list[int], list[int]]:
        xs = {start[0], *(p[0] for p in goals)}
        ys = {start[1], *(p[1] for p in goals)}
        step = GridSystem.SIZE
        for obstacle in self.problem.obstacles:
            a, b, c, d = obstacle.expanded
            xs.update((a - step, c + step))
            ys.update((b - step, d + step))
        for pin in self.problem.pins.values():
            xs.update((pin.escape[0] - step, pin.escape[0], pin.escape[0] + step))
            ys.update((pin.escape[1] - step, pin.escape[1], pin.escape[1] + step))
        for segment in occupied:
            for x, y in (segment.start, segment.end):
                xs.update((x - step, x, x + step))
                ys.update((y - step, y, y + step))
        xs.update((min(xs) - margin, max(xs) + margin))
        ys.update((min(ys) - margin, max(ys) + margin))
        return sorted(xs), sorted(ys)

    def connect(self, net: str, start: Point, tree: list[WireSegment], occupied: list[WireSegment],
                crossings: list[SafeCrossing], fallback: bool) -> tuple[list[WireSegment], list[SafeCrossing]] | None:
        goals = self._goals(start, tree, occupied, crossings, net)
        if start in goals:
            return [], crossings
        if not goals:
            return None
        xs, ys = self._lanes(start, goals, occupied, self.options.envelope_margins[0])
        candidates: list[tuple[int, int, tuple[Point, ...]]] = []
        for goal in goals:
            variants = [[start, goal], [start, (goal[0], start[1]), goal],
                        [start, (start[0], goal[1]), goal]]
            # Feature lanes, not a dense grid. Stable sorted cost later.
            variants.extend([start, (x, start[1]), (x, goal[1]), goal] for x in xs)
            variants.extend([start, (start[0], y), (goal[0], y), goal] for y in ys)
            for points in variants:
                checkpoint(iterations=1)
                segments = path_segments(net, points)
                if any(s.start[0] != s.end[0] and s.start[1] != s.end[1] for s in segments):
                    continue
                candidates.append((max(0, len(segments) - 1), sum(manhattan(s.start, s.end) for s in segments), tuple(points)))
        best = None
        for bends, length, points in sorted(set(candidates)):
            checkpoint(iterations=1)
            self.metrics["candidate_paths"] += 1
            segments = path_segments(net, list(points))
            accepted = self._accept(segments, occupied, crossings, fallback)
            if accepted is None:
                continue
            score = (len(accepted) - len(crossings), bends, length, points)
            if best is None or score < best[0]:
                best = (score, segments, accepted)
            if not fallback or score[0] == 0:
                return segments, accepted
        # A planar A* path is preferable to a short crossing candidate.
        for margin in self.options.envelope_margins:
            try:
                answer = self._search(net, start, tree, goals, occupied, crossings, fallback, margin)
            except _BudgetExceeded:
                self.metrics["budget_exhaustions"] += 1
                continue
            if answer is not None:
                if best is None or len(answer[1]) <= len(best[2]):
                    return answer
                return best[1], best[2]
        return (best[1], best[2]) if best else None

    def _search(self, net: str, start: Point, tree: list[WireSegment], goals: list[Point],
                occupied: list[WireSegment], crossings: list[SafeCrossing], fallback: bool,
                margin: int) -> tuple[list[WireSegment], list[SafeCrossing]] | None:
        self.metrics["astar_searches"] += 1
        xs, ys = self._lanes(start, goals, occupied, margin)
        size = len(xs) * len(ys)
        self.metrics["peak_grid_vertices"] = max(self.metrics["peak_grid_vertices"], size)
        if size > self.options.max_grid_vertices:
            raise _BudgetExceeded()
        point_cache: dict[tuple[int, int], bool] = {}
        edge_cache: dict[tuple[Point, Point], tuple[bool, int]] = {}

        def allowed(i: int, j: int) -> bool:
            key = (i, j)
            if key not in point_cache:
                point_cache[key] = self.detector.point_allowed((xs[i], ys[j]), net, occupied, crossings)
            return point_cache[key]

        def distance(point: Point) -> int:
            return min(manhattan(point, g) for g in goals)

        def is_goal(point: Point) -> bool:
            return any(on_segment(point, s.start, s.end) for s in tree)

        origin = (xs.index(start[0]), ys.index(start[1]), "")
        costs = {origin: (0, 0)}
        parent: dict[tuple[int, int, str], tuple[int, int, str]] = {}
        heap = [(0, distance(start), 0, origin)]
        expanded = 0
        while heap:
            checkpoint(iterations=1)
            crosses, _, cost, state = heapq.heappop(heap)
            if costs.get(state) != (crosses, cost):
                continue
            expanded += 1
            self.metrics["astar_states"] += 1
            if expanded > self.options.max_search_states:
                raise _BudgetExceeded()
            i, j, incoming = state
            point = (xs[i], ys[j])
            if is_goal(point):
                points = [point]
                cursor = state
                while cursor in parent:
                    cursor = parent[cursor]
                    points.append((xs[cursor[0]], ys[cursor[1]]))
                segments = path_segments(net, list(reversed(points)))
                accepted = self._accept(segments, occupied, crossings, fallback)
                if accepted is not None:
                    return segments, accepted
            for di, dj, direction in ((-1, 0, "h"), (0, -1, "v"), (0, 1, "v"), (1, 0, "h")):
                ni, nj = i + di, j + dj
                # Foreign wire coordinates are not vertices: skip to next free
                # point so an X lies strictly inside one unsplit search edge.
                while 0 <= ni < len(xs) and 0 <= nj < len(ys) and not allowed(ni, nj):
                    ni += di
                    nj += dj
                if not (0 <= ni < len(xs) and 0 <= nj < len(ys)):
                    continue
                target = (xs[ni], ys[nj])
                key = tuple(sorted((point, target)))
                if key not in edge_cache:
                    self.metrics["collision_checks"] += 1
                    valid, added = self.detector.segment_allowed(WireSegment(net, point, target), occupied, crossings, allow_crossings=fallback)
                    edge_cache[key] = valid, len(set(added) - set(crossings))
                valid, extra = edge_cache[key]
                if not valid:
                    continue
                bend = self.options.bend_penalty if incoming and incoming != direction else 0
                new_cost = (crosses + extra, cost + manhattan(point, target) + bend)
                child = (ni, nj, direction)
                if child not in costs or new_cost < costs[child]:
                    costs[child] = new_cost
                    parent[child] = state
                    heapq.heappush(heap, (new_cost[0], new_cost[1] + distance(target), new_cost[1], child))
        return None

    def run_order(self, nets: list, fallback: bool) -> RoutingResult | None:
        occupied: list[WireSegment] = []
        crossings: list[SafeCrossing] = []
        geometries: list[NetGeometry] = []
        junctions = {}
        flags: list[RoutedFlag] = []
        for net in nets:
            checkpoint(iterations=1, segments=len(occupied))
            net_pins = [self.problem.pins[p.key] for p in net.pins]
            if not net_pins:
                continue
            remaining = sorted(net_pins, key=lambda p: (p.escape, p.key))
            root = remaining.pop(0)
            tree = [WireSegment(net.name, root.point, root.escape)]
            ports = {root.escape}
            while remaining:
                checkpoint(iterations=1, segments=len(occupied) + len(tree))
                pin = min(remaining, key=lambda p: (min(manhattan(p.escape, q) for q in ports), p.escape, p.key))
                exhausted = self.metrics["budget_exhaustions"]
                answer = self.connect(net.name, pin.escape, tree, occupied + tree, crossings, fallback)
                if answer is None:
                    self.metrics["failed_connections"] += 1
                    code = "ROUTING_SEARCH_LIMIT" if self.metrics["budget_exhaustions"] > exhausted else "NO_SAFE_ROUTE"
                    self.failures.append(ExportDiagnostic(
                        ERROR, code, f"Cannot connect {pin.key} to net {net.name} within the fixed-placement routing budgets",
                        net=net.name, component=pin.terminal.component, pin=pin.terminal.pin, actual=pin.point))
                    return None
                branches, crossings = answer
                tree.extend(branches)
                tree.append(WireSegment(net.name, pin.point, pin.escape))
                ports.add(pin.escape)
                remaining.remove(pin)
            protected = {p.point for p in net_pins} | ports
            tree, net_junctions = normalize_segments(tree, protected, {c.point for c in crossings})
            geometry = NetGeometry(net.name, [p.terminal for p in net_pins], [], tree)
            if net.labels:
                # One canonical flag; layout spacing score favors outside ports
                # and leaves wires connected without label-assisted islands.
                candidates = [p for p in ports if self.detector.point_allowed(p, net.name, occupied, crossings)]
                if not candidates:
                    self.failures.append(ExportDiagnostic(
                        ERROR, "NO_SAFE_ROUTE", f"No safe flag attachment for net {net.name}",
                        net=net.name, component=root.terminal.component, pin=root.terminal.pin, actual=root.point))
                    return None
                def flag_score(p: Point) -> tuple:
                    spacing = self.options.label_spacing
                    crowding = sum(max(0, spacing - manhattan(p, f.point)) for f in flags)
                    proximity = sum(max(0, spacing - manhattan(p, pin.point)) for pin in self.problem.pins.values() if pin.net != net.name)
                    # Ground tends downward, supply upward, output rightward.
                    preference = -p[1] if net.name == "0" else (p[1] if net.name == "VCC" else (-p[0] if net.name in ("VOUT", "OUT+") else p[0]))
                    return crowding + proximity, preference, p
                flag_point = min(candidates, key=flag_score)
                geometry.flags.append(flag_point)
                flags.append(RoutedFlag(net.name, flag_point, net.name))
            geometries.append(geometry)
            junctions[net.name] = net_junctions
            occupied.extend(tree)
            checkpoint(segments=len(occupied))
        # Preserve logical source order in the externally visible result.
        return RoutingResult(geometries, junctions, [], self.metrics, flags, tuple(sorted(set(crossings), key=lambda c: (c.point, c.nets))))


def _audit(result: RoutingResult, problem: RoutingProblem, connectivity: ConnectivityModel) -> list[ExportDiagnostic]:
    found = validate_connectivity(connectivity, result.net_geometries)
    found.extend(validate_net_geometry(result.net_geometries))
    detector = CollisionDetector(problem)
    occupied = [s for n in result.net_geometries for s in n.segments]
    for geometry in result.net_geometries:
        for segment in geometry.segments:
            # A normalized lead can only have the exact designated corridor.
            designated = next((pin.key for pin in problem.pins.values() if pin.net == geometry.name
                               and on_segment(segment.start, pin.point, pin.escape)
                               and on_segment(segment.end, pin.point, pin.escape)), None)
            valid, _ = detector.segment_allowed(segment, occupied, result.crossings,
                                                 allow_crossings=True, escape_pin=designated)
            if not valid:
                found.append(ExportDiagnostic(ERROR, "ROUTING_COLLISION", "Final segment violates component/pin/crossing reservations", net=geometry.name, actual=segment.start))
        for flag in geometry.flags:
            if not detector.point_allowed(flag, geometry.name, occupied, result.crossings):
                found.append(ExportDiagnostic(ERROR, "UNSAFE_ROUTING_FLAG", "Flag touches foreign geometry or a crossing", net=geometry.name, actual=flag))
    return found


def route_nets(connectivity: ConnectivityModel, layouts: Mapping[str, Mapping[str, Any]], *,
               options: RoutingOptions | None = None) -> RoutingResult:
    """Route validated source nets without changing symbols, pins or placements.

    Returns existing NetGeometry/WireSegment objects plus real junctions and
    canonical RoutedFlag records. Every error returns EMPTY geometry/flags;
    callers must not serialize any failed intermediate attempt.
    """
    checkpoint("routing")
    options = options or RoutingOptions()
    diagnostics = validate_connectivity(connectivity)
    metrics = {key: 0 for key in ("candidate_paths", "astar_searches", "astar_states", "peak_grid_vertices",
                                 "collision_checks", "budget_exhaustions", "order_attempts", "failed_connections",
                                 "crossings", "segments", "length", "planar_attempts", "fallback_attempts")}
    integer_options = (options.clearance, options.label_spacing, options.bend_penalty,
                       options.max_grid_vertices, options.max_search_states, options.max_order_attempts)
    valid_types = (all(isinstance(value, int) and not isinstance(value, bool) for value in integer_options)
                   and isinstance(options.allow_crossings, bool)
                   and isinstance(options.envelope_margins, (tuple, list))
                   and all(isinstance(value, int) and not isinstance(value, bool)
                           for value in options.envelope_margins))
    if not valid_types or options.clearance < 0 or options.clearance % GridSystem.SIZE or options.label_spacing < 0 or options.label_spacing % GridSystem.SIZE or not options.envelope_margins or any(m <= 0 or m % GridSystem.SIZE for m in options.envelope_margins) or min(options.max_grid_vertices, options.max_search_states, options.max_order_attempts) <= 0 or options.bend_penalty < 0:
        diagnostics.append(ExportDiagnostic(ERROR, "INVALID_ROUTING_OPTIONS", "Routing clearances/margins must be grid aligned; search budgets positive"))
    if any(d.severity == ERROR for d in diagnostics):
        return RoutingResult(diagnostics=diagnostics, metrics=metrics)
    problem, preparation = prepare_problem(connectivity, layouts, options)
    diagnostics.extend(preparation)
    if any(d.severity == ERROR for d in diagnostics):
        return RoutingResult(diagnostics=diagnostics, metrics=metrics)
    nets = [net for net in connectivity.nets if net.pins]
    router = _Router(problem, metrics)
    # Full restart is a simple bounded rip-up: later nets cannot be trapped by
    # a fixed earlier tree forever. Never use unordered set iteration for order.
    orders = [nets, list(reversed(nets)),
              sorted(nets, key=lambda n: (-len(n.pins), n.name)),
              sorted(nets, key=lambda n: (len(n.pins), n.name))]
    seen = set()
    orders = [order for order in orders if not (tuple(n.name for n in order) in seen or seen.add(tuple(n.name for n in order)))]
    for fallback in ([False, True] if options.allow_crossings else [False]):
        for order in orders[:options.max_order_attempts]:
            checkpoint(iterations=1)
            metrics["order_attempts"] += 1
            metrics["fallback_attempts" if fallback else "planar_attempts"] += 1
            result = router.run_order(order, fallback)
            if result is None:
                continue
            audited = _audit(result, problem, connectivity)
            if any(d.severity == ERROR for d in audited):
                # Never fall through with unsafe intermediate geometry.
                router.failures.extend(d for d in audited if d.severity == ERROR)
                continue
            result.net_geometries.sort(key=lambda n: next(i for i, net in enumerate(connectivity.nets) if net.name == n.name))
            result.flags.sort(key=lambda f: (f.net, f.point))
            result.diagnostics = diagnostics + [d for d in audited if d not in diagnostics]
            metrics["crossings"] = len(result.crossings)
            metrics["segments"] = sum(len(n.segments) for n in result.net_geometries)
            metrics["length"] = sum(manhattan(s.start, s.end) for n in result.net_geometries for s in n.segments)
            return result
    for failure in router.failures:
        if failure not in diagnostics:
            diagnostics.append(failure)
    if not router.failures:
        code = "ROUTING_SEARCH_LIMIT" if metrics["budget_exhaustions"] else "NO_SAFE_ROUTE"
        diagnostics.append(ExportDiagnostic(ERROR, code, "No safe route found within deterministic net-order and visibility search budgets; fixed placement was not changed"))
    return RoutingResult(diagnostics=diagnostics, metrics=metrics)
