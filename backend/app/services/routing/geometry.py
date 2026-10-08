"""Exact integer collision predicates and immutable placed-symbol preparation.

Boxes are closed, including their expanded clearance boundary. Only a straight
outward lead contained in the designated owner's escape corridor can penetrate
that owner's expanded box. Unwired pin corridors are reserved but never emitted.
"""
from __future__ import annotations

from typing import Mapping, Any

from app.services.asc_validation import ERROR, ExportDiagnostic, PinPoint, WireSegment
from app.services.connectivity import ConnectivityModel
from app.services.grid_system import GridSystem, Point
from app.services.production import checkpoint
from app.services.pin_maps import COMPONENT_LIBRARY, PinResolver, PinOrientation, resolve_component_kind
from .models import ComponentObstacle, RoutingOptions, RoutingPin, RoutingProblem, SafeCrossing

DIRECTIONS = {PinOrientation.UP: (0, -1), PinOrientation.DOWN: (0, 1),
              PinOrientation.LEFT: (-1, 0), PinOrientation.RIGHT: (1, 0)}


def axis(segment: WireSegment) -> str:
    return "h" if segment.start[1] == segment.end[1] else "v"


def on_segment(p: Point, a: Point, b: Point, *, strict: bool = False) -> bool:
    if strict and p in (a, b):
        return False
    return ((a[0] == b[0] == p[0] and min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))
            or (a[1] == b[1] == p[1] and min(a[0], b[0]) <= p[0] <= max(a[0], b[0])))


def intersection(a: WireSegment, b: WireSegment) -> tuple[str, Point | None]:
    """Disjoint, point contact, proper X, or positive-length overlap."""
    if axis(a) == axis(b):
        if axis(a) == "h":
            if a.start[1] != b.start[1]:
                return "none", None
            lo = max(min(a.start[0], a.end[0]), min(b.start[0], b.end[0]))
            hi = min(max(a.start[0], a.end[0]), max(b.start[0], b.end[0]))
            p = (lo, a.start[1])
        else:
            if a.start[0] != b.start[0]:
                return "none", None
            lo = max(min(a.start[1], a.end[1]), min(b.start[1], b.end[1]))
            hi = min(max(a.start[1], a.end[1]), max(b.start[1], b.end[1]))
            p = (a.start[0], lo)
        return ("overlap", p) if hi > lo else (("touch", p) if hi == lo else ("none", None))
    h, v = (a, b) if axis(a) == "h" else (b, a)
    p = (v.start[0], h.start[1])
    if not on_segment(p, a.start, a.end) or not on_segment(p, b.start, b.end):
        return "none", None
    if on_segment(p, a.start, a.end, strict=True) and on_segment(p, b.start, b.end, strict=True):
        return "cross", p
    return "touch", p


def box_contains(box: tuple[int, int, int, int], p: Point) -> bool:
    return box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]


def hits_box(segment: WireSegment, box: tuple[int, int, int, int]) -> bool:
    if axis(segment) == "h":
        return (box[1] <= segment.start[1] <= box[3]
                and max(min(segment.start[0], segment.end[0]), box[0])
                <= min(max(segment.start[0], segment.end[0]), box[2]))
    return (box[0] <= segment.start[0] <= box[2]
            and max(min(segment.start[1], segment.end[1]), box[1])
            <= min(max(segment.start[1], segment.end[1]), box[3]))


def manhattan(a: Point, b: Point) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def prepare_problem(connectivity: ConnectivityModel, layouts: Mapping[str, Mapping[str, Any]],
                    options: RoutingOptions) -> tuple[RoutingProblem, list[ExportDiagnostic]]:
    pins: dict[str, RoutingPin] = {}
    obstacles: list[ComponentObstacle] = []
    diagnostics: list[ExportDiagnostic] = []
    owner = {pin.key: net.name for net in connectivity.nets for pin in net.pins}
    unique = {str(comp.get("_inst_name", key)): comp for key, comp in connectivity.components.items()}
    for reference in sorted(unique):
        checkpoint(iterations=1)
        layout = layouts.get(reference)
        if layout is None:
            diagnostics.append(ExportDiagnostic(ERROR, "MISSING_LAYOUT", "Component has no placed layout", component=reference))
            continue
        definition = COMPONENT_LIBRARY.get(resolve_component_kind(layout))
        if definition is None:
            diagnostics.append(ExportDiagnostic(ERROR, "UNSUPPORTED_ROUTING_SYMBOL", "No verified symbol geometry; routing cannot substitute another symbol", component=reference))
            continue
        try:
            anchor = tuple(layout["_ltspice_anchor"])
            if len(anchor) != 2 or not GridSystem.is_point_on_grid(anchor):
                raise ValueError("Placed anchor must be an exact LTspice grid point")
            rotation = str(layout.get("_ltspice_rotation", "R0"))
            mirrored = bool(layout.get("_ltspice_mirror", False))
            degrees, mirror = PinResolver.parse_orientation(rotation, mirrored)
            x0, y0, x1, y1 = definition.bounds
            corners = [PinResolver.transform_offset(x, y, degrees, mirror)
                       for x in (x0, x1) for y in (y0, y1)]
            ax = anchor[0] + definition.anchor[0]
            ay = anchor[1] + definition.anchor[1]
            bounds = (ax + min(x for x, _ in corners), ay + min(y for _, y in corners),
                      ax + max(x for x, _ in corners), ay + max(y for _, y in corners))
            c = options.clearance
            expanded = (bounds[0] - c, bounds[1] - c, bounds[2] + c, bounds[3] + c)
            obstacles.append(ComponentObstacle(reference, bounds, expanded))
            for definition_pin in definition.pins:
                resolved = PinResolver.resolve_pin_geometry(definition, definition_pin.id, anchor, rotation, mirrored)
                point = resolved.absolute
                if not GridSystem.is_point_on_grid(point):
                    raise ValueError("Resolved pin is off grid; router does not snap pins")
                dx, dy = DIRECTIONS[resolved.facing]
                distance = c + GridSystem.SIZE
                if dx > 0:
                    distance = expanded[2] - point[0] + GridSystem.SIZE
                elif dx < 0:
                    distance = point[0] - expanded[0] + GridSystem.SIZE
                elif dy > 0:
                    distance = expanded[3] - point[1] + GridSystem.SIZE
                else:
                    distance = point[1] - expanded[1] + GridSystem.SIZE
                escape = (point[0] + dx * distance, point[1] + dy * distance)
                terminal = PinPoint(reference, resolved.pin_id, point)
                key = f"{reference}.{resolved.pin_id}"
                pins[key] = RoutingPin(terminal, resolved.facing, owner.get(key), escape)
        except (KeyError, TypeError, ValueError) as exc:
            diagnostics.append(ExportDiagnostic(ERROR, "INVALID_ROUTING_GEOMETRY", str(exc), component=reference))
    problem = RoutingProblem(pins, obstacles, options)
    detector = CollisionDetector(problem)
    for pin in pins.values():
        lead = WireSegment(pin.net or f"@unwired:{pin.key}", pin.point, pin.escape)
        if not detector.segment_allowed(lead, [], (), allow_crossings=False, escape_pin=pin.key)[0]:
            diagnostics.append(ExportDiagnostic(ERROR, "BLOCKED_PIN_ESCAPE", "Exact outward pin escape is blocked by a component or foreign pin corridor", net=pin.net, component=pin.terminal.component, pin=pin.terminal.pin, actual=pin.point))
    return problem, diagnostics


class CollisionDetector:
    """One policy for candidates, visibility edges, optimization and audit."""
    def __init__(self, problem: RoutingProblem):
        self.problem = problem
        # Placed pin corridors are immutable for this detector's lifetime.
        self.corridors = tuple((pin, WireSegment("@reserved", pin.point, pin.escape))
                               for pin in problem.pins.values())

    def point_allowed(self, point: Point, net: str, occupied: list[WireSegment],
                      crossings: tuple[SafeCrossing, ...] | list[SafeCrossing]) -> bool:
        checkpoint(iterations=1)
        if any(c.point == point for c in crossings):
            return False
        if any(box_contains(o.expanded, point) for o in self.problem.obstacles):
            return False
        for pin in self.problem.pins.values():
            if pin.net != net and on_segment(point, pin.point, pin.escape):
                return False
        return not any(s.net != net and on_segment(point, s.start, s.end) for s in occupied)

    def segment_allowed(self, segment: WireSegment, occupied: list[WireSegment],
                        crossings: tuple[SafeCrossing, ...] | list[SafeCrossing], *,
                        allow_crossings: bool, escape_pin: str | None = None) -> tuple[bool, list[SafeCrossing]]:
        checkpoint(iterations=1)
        if segment.start == segment.end:
            return False, []
        if segment.start[0] != segment.end[0] and segment.start[1] != segment.end[1]:
            return False, []
        if not all(GridSystem.is_point_on_grid(p) for p in (segment.start, segment.end)):
            return False, []
        designated = self.problem.pins.get(escape_pin) if escape_pin else None
        for obstacle in self.problem.obstacles:
            if not hits_box(segment, obstacle.expanded):
                continue
            if (designated is not None and designated.terminal.component == obstacle.component
                    and on_segment(segment.start, designated.point, designated.escape)
                    and on_segment(segment.end, designated.point, designated.escape)):
                continue
            return False, []
        for pin, corridor in self.corridors:
            if pin is designated:
                continue
            if pin.net is None or pin.net != segment.net:
                if intersection(segment, corridor)[0] != "none":
                    return False, []
        for crossing in crossings:
            if on_segment(crossing.point, segment.start, segment.end):
                # Only the two existing unsplit wires may continue through it.
                if segment.net not in crossing.nets or not on_segment(crossing.point, segment.start, segment.end, strict=True):
                    return False, []
                existing = [s for s in occupied if s.net == segment.net and on_segment(crossing.point, s.start, s.end, strict=True)]
                if not any(axis(s) == axis(segment) for s in existing):
                    return False, []
        new: list[SafeCrossing] = []
        for other in occupied:
            if other.net == segment.net:
                continue
            kind, point = intersection(segment, other)
            if kind == "none":
                continue
            if kind != "cross" or not allow_crossings:
                return False, []
            if any(c.point == point for c in crossings):
                # Existing pair is permitted in the final audit, not a third wire.
                if not any(c.point == point and c.nets == tuple(sorted((segment.net, other.net))) for c in crossings):
                    return False, []
            if any(on_segment(point, pin.point, pin.escape) for pin in self.problem.pins.values()):
                return False, []
            if any(point in (s.start, s.end) for s in occupied):
                return False, []
            new.append(SafeCrossing(tuple(sorted((segment.net, other.net))), point))
        return True, new
