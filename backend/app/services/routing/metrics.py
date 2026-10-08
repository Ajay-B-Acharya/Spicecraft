"""Measurement-only summaries of fixed routing geometry; never optimize or repair.

Lengths are LTspice coordinate units and areas are squared coordinate units.
Graph contacts follow the validator's geometry semantics: existing wire
endpoints, pins and flags can join wires; an unsplit interior X cannot. No
cross-net electrical edges or component-body edges are inferred.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from heapq import heappop, heappush
from math import fsum
from typing import Any

from app.services.asc_validation import NetGeometry
from app.services.grid_system import Point
from app.services.production import checkpoint
from app.services.pin_maps import COMPONENT_LIBRARY, PinResolver, resolve_component_kind
from .geometry import manhattan, on_segment
from .models import SafeCrossing


DETOUR_RATIO_THRESHOLD = 1.5
DETOUR_EXCESS_THRESHOLD = 64

_Graph = dict[Point, dict[Point, int]]


def _conductive_graph(net: NetGeometry) -> _Graph:
    """Split a private measurement graph at actual contacts, not arbitrary Xs.

    Collinear overlaps/duplicates become unique graph edges. Original wire
    records remain untouched (and still contribute their recorded lengths).
    Zero-length records do not create edges or new contacts.
    """
    segments = [segment for segment in net.segments if segment.start != segment.end]
    for segment in segments:
        # Reject diagonals rather than silently reporting Manhattan graph paths
        # for geometry that is not a rectilinear route. No snapping is performed.
        _ = segment.orientation
    vertices = {point for segment in segments for point in (segment.start, segment.end)}
    vertices.update(pin.point for pin in net.pins)
    vertices.update(net.flags)
    graph: _Graph = {point: {} for point in vertices}
    for segment in segments:
        checkpoint(iterations=len(vertices))
        cuts = sorted(point for point in vertices if on_segment(point, segment.start, segment.end))
        for start, end in zip(cuts, cuts[1:]):
            distance = manhattan(start, end)
            graph[start][end] = distance
            graph[end][start] = distance
    return graph


def _shortest_distances(graph: _Graph, start: Point) -> dict[Point, int]:
    """Nonnegative weighted shortest paths; absent destinations are unreachable."""
    distances = {start: 0}
    pending = [(0, start)]
    while pending:
        checkpoint(iterations=1)
        distance, point = heappop(pending)
        if distance != distances[point]:
            continue
        for neighbor, weight in graph[point].items():
            candidate = distance + weight
            previous = distances.get(neighbor)
            if previous is None or candidate < previous:
                distances[neighbor] = candidate
                heappush(pending, (candidate, neighbor))
    return distances


def _symbol_points(layouts: Mapping[str, Mapping[str, Any]]) -> Iterable[Point]:
    """Use canonical symbol definitions and ONLY PinResolver orientation math."""
    for reference, layout in sorted(layouts.items()):
        definition = COMPONENT_LIBRARY.get(resolve_component_kind(dict(layout)))
        if definition is None:
            raise ValueError(f"Unsupported component kind for layout '{reference}'")
        anchor = layout.get("_ltspice_anchor")
        if (not isinstance(anchor, (tuple, list)) or len(anchor) != 2
                or any(type(value) is not int for value in anchor)):
            raise ValueError(f"Layout '{reference}' needs a two-integer '_ltspice_anchor'")
        rotation = str(layout.get("_ltspice_rotation", "R0"))
        mirrored = bool(layout.get("_ltspice_mirror", False))
        # Also validates this definition's rotation/mirror support. These are
        # occupied pins, not additional members of any electrical routing net.
        yield from PinResolver.resolve_all_pins(definition, tuple(anchor), rotation, mirrored).values()
        degrees, mirror = PinResolver.parse_orientation(rotation, mirrored)
        x0, y0, x1, y1 = definition.bounds
        for x in (x0, x1):
            for y in (y0, y1):
                ox, oy = PinResolver.transform_offset(x, y, degrees, mirror)
                yield (anchor[0] + definition.anchor[0] + ox,
                       anchor[1] + definition.anchor[1] + oy)


def measure_routing(
    net_geometries: Iterable[NetGeometry],
    layouts: Mapping[str, Mapping[str, Any]] | None = None,
    crossings: Iterable[SafeCrossing] = (),
) -> dict[str, Any]:
    """Return deterministic, JSON-safe metrics without changing any inputs.

    Input is integer-coordinate NetGeometry data, optionally accompanied by the
    router/exporter's placed-layout mapping and recorded SafeCrossing objects.
    Iterables are consumed once. NetGeometry objects are measured independently;
    this helper does not validate ownership, infer missing nets, or route them.

    Output semantics
    ----------------
    total_length, segment_count:
        Sum of recorded wire Manhattan lengths and number of wire records.
        Duplicates/overlaps count as supplied, as do zero-length records (with
        zero length). Nonzero diagonals raise ValueError. No normalization,
        snapping, or route topology changes are applied to the inputs.
    bend_count, junction_count:
        Counts of vertices in each private conductive graph. A bend is a
        degree-two vertex with one horizontal and one vertical edge. Collinear
        subdivisions are not bends. Degree >= 3 is one junction, not a bend:
        choosing turns through a branch would require an arbitrary traversal.
        Duplicate edges do not inflate degrees. Pin bodies add no edges.
    crossing_count:
        Number of distinct supplied (unordered net pair, coordinate) crossing
        records. No crossing detection or validation is performed here; callers
        with recorded crossings must pass them. Crossings never join graphs.
    terminal_pair_count, evaluated_pair_count, disconnected_pair_count,
    coincident_pair_count:
        All unordered pairs of distinct pin records within each net (exact
        duplicate PinPoint records are deduplicated). Distinct pins at the same
        coordinate are coincident and excluded from ratios. Unreachable pairs
        are counted separately, not assigned infinity or treated as detours.
        Evaluated pairs are reachable and have positive Manhattan separation.
        These last three counts partition terminal_pair_count. Flags establish
        local conductive contacts but are not pin-pair endpoints, and labels
        never provide zero-cost shortcuts between physically separate islands.
    detour_count, detour_ratio, max_detour_ratio:
        Dijkstra shortest routed pin-pair length / Manhattan separation for
        every evaluated pair. detour_ratio is the arithmetic MEAN of those
        ratios, NOT detour_count / pair count or total net wirelength / distance.
        A detour requires ratio > 1.5 AND excess length >= 64 units. The maximum
        and mean are 0.0 when no pairs can be evaluated (straight pairs are 1.0).
    bounding_box, area:
        [min_x, min_y, max_x, max_y] over all segment endpoints, recorded pins,
        and optional placed symbols' canonical bounds/pins; None if empty.
        Area is envelope width * height (not wire ink/union area). A point or
        line has zero area. Flags/text/clearance margins are not occupied bounds.
        Supplied layouts must be placed, supported canonical symbols: missing
        anchors, unknown definitions or invalid orientations raise ValueError;
        no fallback symbol geometry is invented.
    reference_length, routing_efficiency:
        Sum of per-net PIN half-perimeter wirelength (HPWL: x-span + y-span),
        divided by total_length. HPWL is a lower bound for a connected
        rectilinear network even with Steiner branches, unlike a terminal MST.
        It is not an obstacle-aware optimum or an exact tree-length estimate.
        Efficiency is None if any pin pair is disconnected (the reference's
        connected-network premise is false), otherwise 0.0 for zero wirelength.
        For connected routes it is in [0, 1]; no artificial clamping is done.

    Graph construction is O(S*V + S*V*log(V)) in the simple worst case, then
    Dijkstra per distinct pin coordinate and O(P^2) terminal-pair comparisons.
    This is a fixture/reporting measurement, not a router search heuristic.
    """
    total_length = segment_count = bend_count = junction_count = 0
    terminal_pair_count = disconnected_pair_count = coincident_pair_count = 0
    detour_count = reference_length = 0
    pair_ratios: list[float] = []
    occupied: list[Point] = []

    for net in net_geometries:
        checkpoint(iterations=1, segments=segment_count + len(net.segments))
        segment_count += len(net.segments)
        total_length += sum(manhattan(segment.start, segment.end) for segment in net.segments)
        occupied.extend(point for segment in net.segments for point in (segment.start, segment.end))
        occupied.extend(pin.point for pin in net.pins)
        graph = _conductive_graph(net)
        for point, neighbors in graph.items():
            if len(neighbors) >= 3:
                junction_count += 1
            elif len(neighbors) == 2:
                axes = {"h" if neighbor[1] == point[1] else "v" for neighbor in neighbors}
                bend_count += len(axes) == 2

        pins = sorted(set(net.pins), key=lambda pin: (pin.component, pin.pin, pin.point))
        if pins:
            xs = [pin.point[0] for pin in pins]
            ys = [pin.point[1] for pin in pins]
            reference_length += max(xs) - min(xs) + max(ys) - min(ys)
        terminal_pair_count += len(pins) * (len(pins) - 1) // 2
        distance_cache: dict[Point, dict[Point, int]] = {}
        for index, source in enumerate(pins[:-1]):
            checkpoint(iterations=len(pins) - index)
            if source.point not in distance_cache:
                distance_cache[source.point] = _shortest_distances(graph, source.point)
            distances = distance_cache[source.point]
            for target in pins[index + 1:]:
                direct = manhattan(source.point, target.point)
                if direct == 0:
                    coincident_pair_count += 1
                    continue
                routed = distances.get(target.point)
                if routed is None:
                    disconnected_pair_count += 1
                    continue
                pair_ratios.append(routed / direct)
                # Integer arithmetic makes the strict 1.5 boundary exact.
                if 2 * routed > 3 * direct and routed - direct >= DETOUR_EXCESS_THRESHOLD:
                    detour_count += 1

    if layouts is not None:
        occupied.extend(_symbol_points(layouts))
    bounding_box = None
    area = 0
    if occupied:
        xs, ys = zip(*occupied)
        bounding_box = [min(xs), min(ys), max(xs), max(ys)]
        area = (bounding_box[2] - bounding_box[0]) * (bounding_box[3] - bounding_box[1])
    crossing_count = len({(tuple(sorted(crossing.nets)), crossing.point) for crossing in crossings})
    evaluated_pair_count = len(pair_ratios)
    return {
        "total_length": total_length,
        "segment_count": segment_count,
        "bend_count": bend_count,
        "junction_count": junction_count,
        "crossing_count": crossing_count,
        "terminal_pair_count": terminal_pair_count,
        "evaluated_pair_count": evaluated_pair_count,
        "disconnected_pair_count": disconnected_pair_count,
        "coincident_pair_count": coincident_pair_count,
        "detour_count": detour_count,
        "detour_ratio": fsum(sorted(pair_ratios)) / evaluated_pair_count if evaluated_pair_count else 0.0,
        "max_detour_ratio": max(pair_ratios, default=0.0),
        "bounding_box": bounding_box,
        "area": area,
        "reference_length": reference_length,
        "routing_efficiency": (None if disconnected_pair_count else
                               reference_length / total_length if total_length else 0.0),
    }


__all__ = ["measure_routing"]
