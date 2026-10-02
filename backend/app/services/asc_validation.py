"""Export-time validation of generated LTspice wire geometry.

The exporter records, per electrical net, where its pins are, where its flags
are, and which wire segments it emitted. :func:`validate_net_geometry` then
checks that geometry *structurally*, independently of how the router produced it:

* every wire endpoint is a pin, a flag, or a junction shared by 2+ wires of the
  same net (anything else is a dangling stub -> ``INVALID_WIRE_ENDPOINT``)
* every pin of a net is actually the endpoint of a wire of that net
* every net is one connected piece
* everything is on the LTspice grid
* nets do not touch each other

Errors block the export. Warnings are returned and logged, never swallowed.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from app.services.grid_system import GridSystem

Point = tuple[int, int]

ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class PinPoint:
    """A component pin at its resolved absolute coordinate."""

    component: str
    pin: str
    point: Point


@dataclass(frozen=True)
class WireSegment:
    """One emitted ``WIRE`` statement, tagged with the net it belongs to."""

    net: str
    start: Point
    end: Point


@dataclass
class NetGeometry:
    """Everything the exporter placed for one net."""

    name: str
    pins: list[PinPoint] = field(default_factory=list)
    flags: list[Point] = field(default_factory=list)
    segments: list[WireSegment] = field(default_factory=list)


@dataclass(frozen=True)
class ExportDiagnostic:
    """A single problem found while exporting."""

    severity: str
    code: str
    message: str
    net: str | None = None
    component: str | None = None
    pin: str | None = None
    expected: Point | None = None
    actual: Point | None = None

    def format(self) -> str:
        lines = [f"{self.message} [{self.code}]"]
        if self.net is not None:
            lines.append(f"Net: {self.net}")
        if self.component is not None:
            lines.append(f"Component: {self.component}")
        if self.pin is not None:
            lines.append(f"Pin: {self.pin}")
        if self.expected is not None:
            lines.append(f"Expected: {self.expected}")
        if self.actual is not None:
            lines.append(f"Actual: {self.actual}")
        return "\n".join(lines)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.format()


class AscExportError(Exception):
    """Raised when an export has blocking diagnostics; carries all of them."""

    def __init__(self, diagnostics: Sequence[ExportDiagnostic]):
        self.diagnostics = list(diagnostics)
        errors = [d for d in self.diagnostics if d.severity == ERROR]
        super().__init__(
            f"LTspice export failed with {len(errors)} error(s):\n\n"
            + "\n\n".join(d.format() for d in errors)
        )


# ---------------------------------------------------------------------------
# Geometry helpers (segments are axis-aligned in practice; diagonals are
# handled where it is cheap and skipped where it is not)
# ---------------------------------------------------------------------------


def _manhattan(a: Point, b: Point) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _on_segment(p: Point, a: Point, b: Point) -> bool:
    """True if ``p`` lies on the closed segment ``a``-``b``."""
    cross = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
    if cross != 0:
        return False
    return min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(
        a[1], b[1]
    )


def _strictly_inside(p: Point, a: Point, b: Point) -> bool:
    return p != a and p != b and _on_segment(p, a, b)


def _collinear_overlap(a: WireSegment, b: WireSegment) -> bool:
    """True if two axis-aligned segments share more than a single point."""
    if a.start[1] == a.end[1] == b.start[1] == b.end[1]:  # both horizontal, same row
        lo = max(min(a.start[0], a.end[0]), min(b.start[0], b.end[0]))
        hi = min(max(a.start[0], a.end[0]), max(b.start[0], b.end[0]))
        return hi > lo
    if a.start[0] == a.end[0] == b.start[0] == b.end[0]:  # both vertical, same column
        lo = max(min(a.start[1], a.end[1]), min(b.start[1], b.end[1]))
        hi = min(max(a.start[1], a.end[1]), max(b.start[1], b.end[1]))
        return hi > lo
    return False


class _DisjointSet:
    def __init__(self) -> None:
        self._parent: dict[Point, Point] = {}

    def find(self, item: Point) -> Point:
        self._parent.setdefault(item, item)
        while self._parent[item] != item:
            self._parent[item] = self._parent[self._parent[item]]
            item = self._parent[item]
        return item

    def union(self, a: Point, b: Point) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[rb] = ra


# ---------------------------------------------------------------------------
# Per-net checks
# ---------------------------------------------------------------------------


def _check_net(net: NetGeometry) -> list[ExportDiagnostic]:
    found: list[ExportDiagnostic] = []

    pin_points = {pin.point for pin in net.pins}
    flag_points = set(net.flags)
    terminals = pin_points | flag_points

    endpoints: Counter[Point] = Counter()
    for segment in net.segments:
        endpoints[segment.start] += 1
        endpoints[segment.end] += 1

    # 1. Grid alignment: pins, flags and every wire vertex.
    for pin in net.pins:
        if not GridSystem.is_point_on_grid(pin.point):
            found.append(
                ExportDiagnostic(
                    ERROR, "OFF_GRID", "Pin is not on the LTspice grid",
                    net=net.name, component=pin.component, pin=pin.pin,
                    actual=pin.point, expected=GridSystem.snap_point(pin.point),
                )
            )
    for point in sorted(set(endpoints) | flag_points):
        if not GridSystem.is_point_on_grid(point):
            found.append(
                ExportDiagnostic(
                    ERROR, "OFF_GRID", "Wire/flag vertex is not on the LTspice grid",
                    net=net.name, actual=point, expected=GridSystem.snap_point(point),
                )
            )

    # 2. Every wire endpoint must be a pin, a flag, or a junction (degree >= 2).
    unconnected_pins = [pin for pin in net.pins if pin.point not in endpoints]
    for point, degree in sorted(endpoints.items()):
        if degree >= 2 or point in terminals:
            continue
        # LTspice connects a wire end that lands on the middle of another wire
        # of the same net (a T-junction), so that is a valid endpoint too.
        if any(_strictly_inside(point, s.start, s.end) for s in net.segments):
            continue
        candidates = unconnected_pins or net.pins
        nearest = min(candidates, key=lambda p: _manhattan(p.point, point), default=None)
        found.append(
            ExportDiagnostic(
                ERROR, "INVALID_WIRE_ENDPOINT", "Invalid wire endpoint",
                net=net.name,
                component=nearest.component if nearest else None,
                pin=nearest.pin if nearest else None,
                expected=nearest.point if nearest else None,
                actual=point,
            )
        )

    # 3. Every pin of a net with something to connect to must be wired.
    if len(terminals) >= 2 or net.segments:
        for pin in unconnected_pins:
            nearest_endpoint = min(
                endpoints, key=lambda p: _manhattan(p, pin.point), default=None
            )
            found.append(
                ExportDiagnostic(
                    ERROR, "PIN_NOT_CONNECTED", "Pin is not the endpoint of any wire",
                    net=net.name, component=pin.component, pin=pin.pin,
                    expected=pin.point, actual=nearest_endpoint,
                )
            )

    # 4. The net must be a single connected piece.
    if net.segments and len(terminals) >= 2:
        sets = _DisjointSet()
        for segment in net.segments:
            sets.union(segment.start, segment.end)
        # T-junctions join a wire end to the interior of another segment.
        for segment in net.segments:
            for other in net.segments:
                if other is segment:
                    continue
                for end in (segment.start, segment.end):
                    if _strictly_inside(end, other.start, other.end):
                        sets.union(end, other.start)
        roots = {sets.find(t) for t in terminals if t in endpoints}
        if len(roots) > 1:
            found.append(
                ExportDiagnostic(
                    ERROR, "NET_DISCONNECTED",
                    f"Net is split into {len(roots)} unconnected pieces",
                    net=net.name,
                )
            )

    return found


# ---------------------------------------------------------------------------
# Cross-net checks
# ---------------------------------------------------------------------------


def _check_between_nets(nets: Sequence[NetGeometry]) -> list[ExportDiagnostic]:
    found: list[ExportDiagnostic] = []
    reported: set[tuple] = set()

    def report(severity: str, code: str, message: str, key: tuple, **fields) -> None:
        if key in reported:
            return
        reported.add(key)
        found.append(ExportDiagnostic(severity, code, message, **fields))

    # Terminals (pins + flags) of different nets must never share a coordinate.
    owners: dict[Point, set[str]] = {}
    for net in nets:
        for point in {p.point for p in net.pins} | set(net.flags):
            owners.setdefault(point, set()).add(net.name)
    for point, names in sorted(owners.items()):
        if len(names) > 1:
            report(
                ERROR, "PIN_COLLISION",
                f"Terminals of nets {sorted(names)} occupy the same coordinate",
                ("collision", point), actual=point, net=", ".join(sorted(names)),
            )

    for a in nets:
        for b in nets:
            if a is b:
                continue
            for seg in a.segments:
                # Another net's pin/flag touching this wire.
                for pin in b.pins:
                    if _on_segment(pin.point, seg.start, seg.end):
                        if pin.point in (seg.start, seg.end):
                            report(
                                WARNING, "NET_SHORT",
                                "Wire of one net ends exactly on a pin of another net",
                                ("pin-end", a.name, b.name, pin.point),
                                net=f"{a.name} / {b.name}", component=pin.component,
                                pin=pin.pin, actual=pin.point,
                            )
                        else:
                            report(
                                WARNING, "WIRE_CROSSES_PIN",
                                "Wire of one net passes over a pin of another net",
                                ("pin-over", a.name, b.name, pin.point),
                                net=f"{a.name} / {b.name}", component=pin.component,
                                pin=pin.pin, actual=pin.point,
                            )
                for other in b.segments:
                    if _collinear_overlap(seg, other):
                        report(
                            WARNING, "NET_SHORT", "Wires of different nets overlap",
                            ("overlap", *sorted((a.name, b.name)), seg.start, seg.end),
                            net=f"{a.name} / {b.name}", actual=seg.start,
                        )
                    for end in (seg.start, seg.end):
                        if _strictly_inside(end, other.start, other.end):
                            report(
                                WARNING, "NET_SHORT",
                                "Wire of one net ends on the middle of another net's wire",
                                ("t-junction", a.name, b.name, end),
                                net=f"{a.name} / {b.name}", actual=end,
                            )
    return found


def validate_net_geometry(nets: Iterable[NetGeometry]) -> list[ExportDiagnostic]:
    """Run all structural checks on the exporter's recorded geometry."""
    net_list = list(nets)
    diagnostics: list[ExportDiagnostic] = []
    for net in net_list:
        diagnostics.extend(_check_net(net))
    diagnostics.extend(_check_between_nets(net_list))
    return diagnostics
