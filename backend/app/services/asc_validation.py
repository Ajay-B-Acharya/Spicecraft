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

    @property
    def orientation(self) -> str:
        """Return the Manhattan axis; invalid segments are never routable."""
        if self.start == self.end:
            raise ValueError("A wire segment must have nonzero length")
        if self.start[1] == self.end[1]:
            return "horizontal"
        if self.start[0] == self.end[0]:
            return "vertical"
        raise ValueError("A wire segment must be orthogonal")


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
    circuit: str | None = None
    stage: str | None = None

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
        if self.circuit is not None:
            lines.append(f"Circuit: {self.circuit}")
        if self.stage is not None:
            lines.append(f"Stage: {self.stage}")
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
# Geometry helpers. Invalid segments are diagnosed before connectivity checks.
# A perpendicular crossing strictly inside both wires is NOT conductive in
# LTspice; endpoints, pins, flags, and collinear overlaps ARE conductive.
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

    segments: list[WireSegment] = []
    endpoints: Counter[Point] = Counter()
    raw_vertices: set[Point] = set()
    seen_edges: set[tuple[Point, Point]] = set()
    duplicate_edges: set[tuple[Point, Point]] = set()
    for segment in net.segments:
        raw_vertices.update((segment.start, segment.end))
        valid = segment.net == net.name
        if not valid:
            found.append(ExportDiagnostic(
                ERROR, "WIRE_NET_MISMATCH", "Wire ownership differs from its containing net",
                net=net.name, actual=segment.start,
            ))
        try:
            segment.orientation
        except ValueError as exc:
            valid = False
            found.append(ExportDiagnostic(
                ERROR, "ZERO_LENGTH_WIRE" if segment.start == segment.end else "NON_ORTHOGONAL_WIRE",
                str(exc), net=net.name, actual=segment.start, expected=segment.end,
            ))
        # Malformed records must not provide incidence, terminal attachment,
        # T-junction support, or connectivity. Keep their vertices for errors.
        if not valid or not all(
            GridSystem.is_point_on_grid(p) for p in (segment.start, segment.end)
        ):
            continue
        edge = tuple(sorted((segment.start, segment.end)))
        if edge in seen_edges:
            if edge not in duplicate_edges:
                found.append(ExportDiagnostic(
                    WARNING, "DUPLICATE_WIRE_SEGMENT", "Duplicate undirected wire segment",
                    net=net.name, actual=edge[0], expected=edge[1],
                ))
                duplicate_edges.add(edge)
            continue
        seen_edges.add(edge)
        segments.append(segment)
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
    for point in sorted(raw_vertices | flag_points):
        if not GridSystem.is_point_on_grid(point):
            found.append(
                ExportDiagnostic(
                    ERROR, "OFF_GRID", "Wire/flag vertex is not on the LTspice grid",
                    net=net.name, actual=point, expected=GridSystem.snap_point(point),
                )
            )

    # 2. Degree counts distinct valid physical edges, not WIRE statements.
    unconnected_pins = [pin for pin in net.pins if pin.point not in endpoints]
    for point in sorted(raw_vertices):
        if endpoints[point] >= 2 or point in terminals:
            continue
        # LTspice connects a wire end that lands on the middle of another valid
        # wire of the same net (a T-junction), so that is a valid endpoint too.
        if any(_strictly_inside(point, s.start, s.end) for s in segments):
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

    # 4. Flags must attach to their own wire or directly to a pin. A bare
    # floating label is not an electrically meaningful exported terminal.
    for point in sorted(flag_points):
        if point not in pin_points and not any(
            _on_segment(point, s.start, s.end) for s in segments
        ):
            found.append(ExportDiagnostic(
                ERROR, "FLAG_NOT_CONNECTED", "Flag is not attached to its net's wire or pin",
                net=net.name, actual=point,
            ))

    # 5. Include ALL wire islands, not just components containing terminals.
    # Unsplit interior perpendicular crossings do not join even within a net.
    sets = _DisjointSet()
    for segment in segments:
        sets.union(segment.start, segment.end)
    vertices = {p for s in segments for p in (s.start, s.end)} | terminals
    from app.services.production import checkpoint
    for point in sorted(vertices):
        checkpoint()
        sets.find(point)
        for segment in segments:
            if _on_segment(point, segment.start, segment.end):
                sets.union(point, segment.start)
    roots = {sets.find(point) for point in vertices}
    if len(roots) > 1 and (segments or len(terminals) > 1):
        found.append(ExportDiagnostic(
            ERROR, "NET_DISCONNECTED", f"Net is split into {len(roots)} unconnected pieces",
            net=net.name,
        ))
    attached_roots = {sets.find(point) for point in terminals}
    orphan_roots = {sets.find(s.start) for s in segments} - attached_roots
    for root in sorted(orphan_roots):
        found.append(ExportDiagnostic(
            ERROR, "ORPHAN_WIRE_ISLAND", "Wire island has no pin or flag of its net",
            net=net.name, actual=root,
        ))

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

    from app.services.production import checkpoint
    for a in nets:
        for b in nets:
            checkpoint()
            if a is b:
                continue
            for seg in a.segments:
                checkpoint()
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
                for point in b.flags:
                    if _on_segment(point, seg.start, seg.end):
                        report(
                            WARNING, "NET_SHORT", "Flag of another net touches this wire",
                            ("flag-wire", a.name, b.name, point),
                            net=f"{a.name} / {b.name}", actual=point,
                        )
                for other in b.segments:
                    shared = {seg.start, seg.end} & {other.start, other.end}
                    for point in sorted(shared):
                        report(
                            WARNING, "NET_SHORT", "Wires of different nets share an endpoint",
                            ("shared-end", *sorted((a.name, b.name)), point),
                            net=f"{a.name} / {b.name}", actual=point,
                        )
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


def validate_net_geometry(
    nets: Iterable[NetGeometry], *, reserved_pins: Iterable[PinPoint] = ()
) -> list[ExportDiagnostic]:
    """Check Manhattan geometry and actual LTspice conductive contacts.

    ``reserved_pins`` includes definition pins absent from source wires. Those
    pins must stay singleton nodes; geometry cannot silently wire or flag them.
    Standalone contact diagnostics retain WARNING severity for compatibility;
    the exporter always promotes unsafe contacts to blocking errors.
    """
    net_list = list(nets)
    diagnostics: list[ExportDiagnostic] = []
    for net in net_list:
        diagnostics.extend(_check_net(net))
    # Model reserved pins as independent, unwired nets for collision checking.
    recorded = {(pin.component, pin.pin) for net in net_list for pin in net.pins}
    reserved = [pin for pin in reserved_pins if (pin.component, pin.pin) not in recorded]
    occupied_names = {net.name for net in net_list}
    for index, pin in enumerate(reserved):
        name = f"<unwired:{pin.component}.{pin.pin}:{index}>"
        while name in occupied_names:
            name += "_"
        occupied_names.add(name)
        net_list.append(NetGeometry(name, pins=[pin]))
    diagnostics.extend(_check_between_nets(net_list))
    return diagnostics
