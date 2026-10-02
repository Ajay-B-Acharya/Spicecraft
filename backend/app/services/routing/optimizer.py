"""Topology-preserving normalization, never splitting unrelated X crossings."""
from __future__ import annotations

from collections import Counter

from app.services.asc_validation import WireSegment
from app.services.grid_system import Point
from .geometry import axis, intersection, manhattan, on_segment


def normalize_segments(segments: list[WireSegment], protected: set[Point],
                       crossing_points: set[Point]) -> tuple[list[WireSegment], tuple[Point, ...]]:
    if not segments:
        return [], ()
    net = segments[0].net
    vertices = {p for s in segments for p in (s.start, s.end)} | protected
    for i, a in enumerate(segments):
        for b in segments[i + 1:]:
            kind, point = intersection(a, b)
            if kind in ("cross", "touch") and point not in crossing_points:
                vertices.add(point)
    pieces: set[tuple[Point, Point]] = set()
    for segment in segments:
        cuts = sorted({segment.start, segment.end} | {
            p for p in vertices if p not in crossing_points and on_segment(p, segment.start, segment.end)
        })
        for start, end in zip(cuts, cuts[1:]):
            if start != end:
                pieces.add((start, end))
    # Merge only a collinear degree-two vertex, never a protected terminal/port.
    while True:
        incidence: dict[Point, list[tuple[Point, Point]]] = {}
        for piece in sorted(pieces):
            for point in piece:
                incidence.setdefault(point, []).append(piece)
        merge = None
        for point, edges in sorted(incidence.items()):
            if point in protected or point in crossing_points or len(edges) != 2:
                continue
            a, b = edges
            outer_a = a[1] if a[0] == point else a[0]
            outer_b = b[1] if b[0] == point else b[0]
            if outer_a[0] == point[0] == outer_b[0] or outer_a[1] == point[1] == outer_b[1]:
                merge = (a, b, tuple(sorted((outer_a, outer_b))))
                break
        if merge is None:
            break
        pieces.remove(merge[0])
        pieces.remove(merge[1])
        pieces.add(merge[2])
    result = [WireSegment(net, a, b) for a, b in sorted(pieces)]
    degree = Counter(p for s in result for p in (s.start, s.end))
    junctions = tuple(sorted(p for p, count in degree.items() if count >= 3))
    return result, junctions


def path_segments(net: str, points: list[Point]) -> list[WireSegment]:
    """Remove search-grid degree-two collinear nodes before accepting a route."""
    compact: list[Point] = []
    for point in points:
        if compact and point == compact[-1]:
            continue
        while len(compact) >= 2 and (
            compact[-2][0] == compact[-1][0] == point[0]
            or compact[-2][1] == compact[-1][1] == point[1]
        ):
            compact.pop()
        compact.append(point)
    return [WireSegment(net, a, b) for a, b in zip(compact, compact[1:]) if a != b]
