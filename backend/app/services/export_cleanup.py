"""Conservative, export-only cleanup of already validated wire geometry.

This is not routing normalization: interior crossings are never split, vertices
are never snapped, and logical net membership is never inferred from geometry.
"""
from __future__ import annotations

from app.services.asc_validation import NetGeometry, Point, WireSegment
from app.services.grid_system import GridSystem
from app.services.production import checkpoint

EdgeKey = tuple[str, Point, Point]


def _key(segment: WireSegment) -> EdgeKey:
    start, end = sorted((segment.start, segment.end))
    return segment.net, start, end


def _on_segment(point: Point, segment: WireSegment) -> bool:
    a, b = segment.start, segment.end
    return (
        (b[0] - a[0]) * (point[1] - a[1]) == (b[1] - a[1]) * (point[0] - a[0])
        and min(a[0], b[0]) <= point[0] <= max(a[0], b[0])
        and min(a[1], b[1]) <= point[1] <= max(a[1], b[1])
    )


def _collinear(a: WireSegment, b: WireSegment) -> bool:
    return (a.start[0] == a.end[0] == b.start[0] == b.end[0]
            or a.start[1] == a.end[1] == b.start[1] == b.end[1])


def _valid(segment: WireSegment, net: str) -> bool:
    if segment.net != net:
        return False
    try:
        segment.orientation
    except ValueError:
        return False
    return all(GridSystem.is_point_on_grid(p) for p in (segment.start, segment.end))


def _clean_net(net: NetGeometry, protected: set[Point]) -> NetGeometry:
    # Ownership is part of the key. Never relabel a malformed foreign segment.
    edges = {
        _key(segment): WireSegment(*_key(segment))
        for segment in net.segments if segment.start != segment.end
    }
    while True:
        checkpoint(iterations=1, segments=len(edges))
        ordered = sorted(edges)
        incidence: dict[Point, list[EdgeKey]] = {}
        for key in ordered:
            for point in key[1:]:
                incidence.setdefault(point, []).append(key)

        # A single longer edge may already cover a shorter collinear edge.
        # Retain the shorter edge if its removal would erase a terminal or
        # conductive junction endpoint. Do not split the longer edge instead.
        removable = None
        for key in ordered:
            checkpoint(iterations=len(ordered))
            edge = edges[key]
            if not _valid(edge, net.name):
                continue
            if any(
                point in protected and not any(
                    other != key and _valid(edges[other], net.name)
                    for other in incidence[point]
                )
                for point in (edge.start, edge.end)
            ):
                continue
            if any(
                other != key and _valid(edges[other], net.name)
                and _collinear(edge, edges[other])
                and _on_segment(edge.start, edges[other])
                and _on_segment(edge.end, edges[other])
                for other in ordered
            ):
                removable = key
                break
        if removable is not None:
            del edges[removable]
            continue

        merge = None
        for point, incident in sorted(incidence.items()):
            if point in protected or len(incident) != 2:
                continue
            first, second = incident
            a, b = edges[first], edges[second]
            if not (_valid(a, net.name) and _valid(b, net.name) and _collinear(a, b)):
                continue
            outer_a = a.end if a.start == point else a.start
            outer_b = b.end if b.start == point else b.start
            joined = WireSegment(net.name, *sorted((outer_a, outer_b)))
            # Opposite rays only: joining overlapping/backtracking edges by
            # their outer ends could silently discard part of the original run.
            if point in (joined.start, joined.end) or not _on_segment(point, joined):
                continue
            merge = first, second, joined
            break
        if merge is None:
            break
        first, second, joined = merge
        del edges[first]
        del edges[second]
        edges[_key(joined)] = joined
        # Rebuild incidence after each operation. This also deduplicates an
        # existing edge equal to the joined run and permits multi-step chains.

    return NetGeometry(
        name=net.name,
        pins=list(net.pins),
        flags=sorted(set(net.flags)),
        segments=[edges[key] for key in sorted(edges)],
    )


def clean_export_geometry(nets: list[NetGeometry]) -> list[NetGeometry]:
    """Return fresh net/list containers with only topology-safe simplifications.

    The caller MUST validate raw geometry first, block errors (including zero
    length), then clean and validate again. This function removes zero-length
    records and duplicate undirected segments/flags; it is not error recovery.
    Nonzero malformed segments are retained and never used to cover/join wires.

    Net order, names, and every source PinPoint (including order/multiplicity)
    are preserved. Edges have canonical endpoint direction and sorted keys;
    flags are unique and sorted per net. Pins/flags on *any* net and every
    existing conductive T/X endpoint are protected. No new vertices or paths
    are introduced, so unrelated unsplit interior X crossings remain unsplit.
    """
    checkpoint("optimization", segments=sum(len(net.segments) for net in nets))
    protected = {pin.point for net in nets for pin in net.pins}
    protected.update(point for net in nets for point in net.flags)
    segments = [segment for net in nets for segment in net.segments
                if segment.start != segment.end]
    # Degree two alone is insufficient: its boundary may contact the interior
    # of a perpendicular wire. Removing that boundary would turn a conductive
    # junction into an unrelated unsplit X. Include foreign nets too, so this
    # helper cannot hide an existing cross-net contact if called on bad input.
    for segment in segments:
        checkpoint(iterations=len(segments))
        for point in (segment.start, segment.end):
            if point not in protected and any(
                not _collinear(segment, other) and _on_segment(point, other)
                for other in segments if other is not segment
            ):
                protected.add(point)
    return [_clean_net(net, protected) for net in nets]
