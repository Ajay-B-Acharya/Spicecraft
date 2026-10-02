"""
LTspice ASC Exporter Service (Version 1)

Converts the SpiceCraft circuit JSON model into a valid LTspice ASCII schematic
(.asc) file. The exporter keeps component references and values intact while
routing wires against a dedicated pin map so the resulting topology is electrically
meaningful.

Geometry rules (see ``pin_maps`` for the full model):

* the SYMBOL line and every pin coordinate are derived from the same
  ``_ltspice_anchor`` / ``_ltspice_rotation`` / ``_ltspice_mirror`` fields, so a
  symbol can never be drawn in one orientation while its pins are wired as if it
  were in another;
* all coordinates are snapped through ``GridSystem`` (the only grid utility);
* before anything is returned, ``asc_validation`` checks every wire endpoint.

Public API
----------
generate_asc(circuit: dict) -> str
    Returns the full content of a Version-4 LTspice .asc file. Raises
    ``AscExportError`` if the geometry has blocking problems.
generate_asc_with_diagnostics(circuit: dict) -> tuple[str, list[ExportDiagnostic]]
    Same output plus every diagnostic (errors and warnings); never raises on
    geometry problems.
place_component(idx, component) / place_components(components)
    The placement step on its own, for debugging.

Known limitation: wire *routing* is still the original single-elbow hub router.
It connects every pin correctly but can draw one net across another net's pins.
Those cases are reported as ``NET_SHORT`` / ``WIRE_CROSSES_PIN`` warnings (or
errors with ``strict=True``) rather than hidden; fixing them is the routing
phase, not this module's geometry layer.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.asc_validation import (
    ERROR,
    WARNING,
    AscExportError,
    ExportDiagnostic,
    NetGeometry,
    PinPoint,
    WireSegment,
    validate_net_geometry,
)
from app.services.grid_system import GridSystem
from app.services.pin_maps import (
    COMPONENT_LIBRARY,
    PinResolver,
    canonical_pin_id,
    get_pin_coordinate,
    resolve_component_kind,
    resolve_symbol_name,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
# Components are spaced 256 units apart to leave room for net labels and
# orthogonal routing. All values are multiples of the 16-unit LTspice grid.
GRID_COL_STEP = 256
GRID_ROW_STEP = 256
COLS_PER_ROW = 4
ORIGIN_X = 64
ORIGIN_Y = 128

SPECIAL_NODE_FLAGS: dict[str, str] = {
    "0": "0",
    "GND": "0",
    "GROUND": "0",
    "VCC": "VCC",
    "VDD": "VCC",
    "PWR": "VCC",
    "VIN": "VIN",
    "IN": "VIN",
    "VOUT": "VOUT",
    "OUT": "VOUT",
}

SPECIAL_NODE_ORDER = {"GND": 0, "VCC": 1, "VIN": 2, "VOUT": 3}

Point = tuple[int, int]


# ---------------------------------------------------------------------------
# Component / net helpers
# ---------------------------------------------------------------------------


def _normalise_type(raw_type: str) -> str:
    return raw_type.strip().lower() if raw_type else ""


def _rotation(symbol: str) -> str:
    # Fallback for symbols that have no ComponentDefinition.
    return "R90" if symbol in {"voltage", "current"} else "R0"


def _ltspice_rotation_for_symbol(symbol: str) -> str:
    """Return the LTspice rotation string for a symbol with no definition."""
    return "R90" if symbol in {"voltage", "current"} else "R0"


def _text_line(x: int, y: int, text: str) -> str:
    return f"TEXT {x} {y} Left 2 ;{text}"


def _wire_line(x1: int, y1: int, x2: int, y2: int) -> str:
    return f"WIRE {x1} {y1} {x2} {y2}"


def _flag_line(x: int, y: int, net: str) -> str:
    return f"FLAG {x} {y} {net}"


def _flag_net_name(special_node: str) -> str:
    return "0" if special_node == "GND" else special_node


def _symbol_block(
    symbol: str,
    x: int,
    y: int,
    rotation: str,
    inst_name: str,
    value: str | None,
) -> list[str]:
    lines = [f"SYMBOL {symbol} {x} {y} {rotation}"]
    lines.append(f"SYMATTR InstName {inst_name}")
    if value:
        lines.append(f"SYMATTR Value {value}")
    return lines


def _canonical_special_node(node: str) -> str | None:
    node_upper = node.strip().upper()
    flag = SPECIAL_NODE_FLAGS.get(node_upper)
    if flag == "0":
        return "GND"
    return flag


def _choose_special_node(nodes: list[str]) -> str:
    return sorted(nodes, key=lambda node: SPECIAL_NODE_ORDER.get(node, 99))[0]


def _parse_node(node: str) -> tuple[str, str]:
    raw = node.strip()
    if not raw:
        return "", ""

    if "." in raw:
        ref, pin = raw.split(".", 1)
        return "component", f"{ref.strip()}.{pin.strip()}"

    special = _canonical_special_node(raw)
    if special:
        return "special", special

    return "net", raw


class _UnionFind:
    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def add(self, item: str) -> None:
        if item and item not in self._parent:
            self._parent[item] = item

    def find(self, item: str) -> str:
        parent = self._parent.get(item)
        if parent is None:
            self._parent[item] = item
            return item
        if parent != item:
            self._parent[item] = self.find(parent)
        return self._parent[item]

    def union(self, left: str, right: str) -> None:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left != root_right:
            self._parent[root_right] = root_left


def _snap(value: float, grid: int = GridSystem.SIZE) -> int:
    """Kept for compatibility; delegates to the shared GridSystem."""
    if grid != GridSystem.SIZE:
        if grid <= 0:
            return int(round(value))
        return int(round(value / grid) * grid)
    return GridSystem.snap(value)


def _route_points(start: Point, end: Point) -> list[tuple[Point, Point]]:
    """Orthogonal route from ``start`` to ``end`` as ``(a, b)`` segments."""
    if start == end:
        return []

    sx, sy = start
    ex, ey = end

    if sx == ex or sy == ey:
        return [(start, end)]

    # Route orthogonally using a single elbow.
    elbow_a = (ex, sy)
    if elbow_a != start and elbow_a != end:
        return [(start, elbow_a), (elbow_a, end)]

    elbow_b = (sx, ey)
    if elbow_b != start and elbow_b != end:
        return [(start, elbow_b), (elbow_b, end)]

    return [(start, end)]


def _route_wire(start: Point, end: Point) -> list[str]:
    return [_wire_line(a[0], a[1], b[0], b[1]) for a, b in _route_points(start, end)]


def _label_position(
    net_name: str,
    member_points: list[Point],
    bounds: tuple[int, int, int, int],
) -> Point:
    min_x, min_y, max_x, max_y = bounds
    anchor_x, anchor_y = member_points[0]

    if net_name == "GND":
        return min_x - 96, max_y + 96
    if net_name == "VCC":
        return min_x - 96, min_y - 96
    if net_name == "VIN":
        return min_x - 96, GridSystem.snap(anchor_y)
    if net_name == "VOUT":
        return max_x + 96, GridSystem.snap(anchor_y)

    return GridSystem.snap((min_x + max_x) / 2), GridSystem.snap((min_y + max_y) / 2)


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------


def place_component(idx: int, comp: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Place one component and return ``(inst_name, layout)``.

    ``layout`` carries the three fields every consumer (SYMBOL line, pin
    resolver, debugger) reads: ``_ltspice_anchor``, ``_ltspice_rotation`` and
    ``_ltspice_mirror``.
    """
    col = idx % COLS_PER_ROW
    row = idx // COLS_PER_ROW
    anchor = GridSystem.snap_point(
        (ORIGIN_X + col * GRID_COL_STEP, ORIGIN_Y + row * GRID_ROW_STEP)
    )

    inst_name = str(comp.get("reference") or comp.get("id") or f"X{idx + 1}")
    symbol = resolve_symbol_name(comp)
    definition = COMPONENT_LIBRARY.get(resolve_component_kind(comp))
    rotation = (
        definition.default_rotation
        if definition is not None
        else _ltspice_rotation_for_symbol(symbol)
    )

    layout = dict(comp)
    layout["_inst_name"] = inst_name
    layout["_ltspice_anchor"] = anchor
    layout["_ltspice_symbol"] = symbol
    layout["_ltspice_rotation"] = rotation
    layout["_ltspice_mirror"] = False  # future: read from comp dict
    return inst_name, layout


def place_components(components: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Placement step on its own: ``{inst_name: layout}`` (also keyed by ``id``)."""
    layouts: dict[str, dict[str, Any]] = {}
    for idx, comp in enumerate(components):
        inst_name, layout = place_component(idx, comp)
        layouts[inst_name] = layout
        comp_id = str(comp.get("id", "")).strip()
        if comp_id:
            layouts[comp_id] = layout
    return layouts


def _symbol_orientation(layout: dict[str, Any]) -> str:
    """The orientation token for the SYMBOL line, from the same fields the
    pin resolver reads."""
    return PinResolver.orientation_string(
        str(layout.get("_ltspice_rotation", "R0")),
        bool(layout.get("_ltspice_mirror", False)),
    )


# ---------------------------------------------------------------------------
# Main export function
# ---------------------------------------------------------------------------


def _promote_shorts(diagnostics: list[ExportDiagnostic]) -> list[ExportDiagnostic]:
    """Turn routing-overlap warnings into errors (``strict`` mode)."""
    promoted_codes = {"NET_SHORT", "WIRE_CROSSES_PIN"}
    return [
        ExportDiagnostic(
            ERROR, d.code, d.message, d.net, d.component, d.pin, d.expected, d.actual
        )
        if d.severity == WARNING and d.code in promoted_codes
        else d
        for d in diagnostics
    ]


def generate_asc_with_diagnostics(
    circuit: dict[str, Any], strict: bool = False
) -> tuple[str, list[ExportDiagnostic]]:
    """Convert a circuit dict into ``(asc_text, diagnostics)``.

    Never raises for geometry problems; inspect ``diagnostics`` (errors mean the
    text should not be used as-is). With ``strict=True`` wires that short or
    cross other nets are reported as errors instead of warnings.
    """
    name: str = str(circuit.get("name", "Circuit"))
    description: str = str(circuit.get("description", ""))
    components: list[dict[str, Any]] = circuit.get("components", [])
    wires: list[dict[str, Any]] = circuit.get("wires", [])

    lines: list[str] = []
    diagnostics: list[ExportDiagnostic] = []

    # ---- Header -----------------------------------------------------------
    lines.append("Version 4")
    lines.append("SHEET 1 1200 800")

    # ---- Comment header ---------------------------------------------------
    lines.append(_text_line(16, 16, name))
    if description:
        lines.append(_text_line(16, 48, description))

    # ---- Components -------------------------------------------------------
    component_layouts: dict[str, dict[str, Any]] = {}
    node_points: dict[str, Point] = {}

    for idx, comp in enumerate(components):
        inst_name, layout = place_component(idx, comp)
        component_layouts[inst_name] = layout

        comp_id = str(comp.get("id", "")).strip()
        if comp_id:
            component_layouts[comp_id] = layout

        if resolve_component_kind(comp) not in COMPONENT_LIBRARY:
            diagnostics.append(
                ExportDiagnostic(
                    WARNING, "UNKNOWN_COMPONENT_KIND",
                    "Unknown component kind; exported as a generic 'res' symbol "
                    "and its pins cannot be wired",
                    component=inst_name,
                )
            )

        value = comp.get("value")
        value_str = str(value) if value is not None else None
        anchor = layout["_ltspice_anchor"]
        lines.extend(
            _symbol_block(
                layout["_ltspice_symbol"],
                anchor[0],
                anchor[1],
                _symbol_orientation(layout),
                inst_name,
                value_str,
            )
        )

    if not wires:
        return "\n".join(lines) + "\n", diagnostics

    # ---- Connectivity model ----------------------------------------------
    uf = _UnionFind()
    special_nodes_seen: set[str] = set()
    pin_refs: dict[str, tuple[str, str]] = {}  # node key -> (inst_name, pin id)

    def resolve_endpoint(kind: str, key: str, wire_label: str) -> str:
        """Canonicalise ``REF.pin`` keys and record the pin's coordinate."""
        if kind != "component":
            return key
        ref, pin = key.split(".", 1)
        component = component_layouts.get(ref)
        if component is None:
            diagnostics.append(
                ExportDiagnostic(
                    ERROR, "MISSING_COMPONENT",
                    f"Wire {wire_label} references a component that does not exist",
                    component=ref, pin=pin,
                )
            )
            return key
        inst = component["_inst_name"]
        pin_id = canonical_pin_id(component, pin)
        canonical_key = f"{inst}.{pin_id}"
        try:
            node_points[canonical_key] = get_pin_coordinate(component, pin_id)
            pin_refs[canonical_key] = (inst, pin_id)
        except ValueError as exc:
            diagnostics.append(
                ExportDiagnostic(
                    ERROR, "UNRESOLVED_PIN", str(exc), component=inst, pin=pin,
                )
            )
        return canonical_key

    for wire_index, wire in enumerate(wires, start=1):
        src = str(wire.get("source") or wire.get("from") or "")
        dst = str(wire.get("destination") or wire.get("to") or "")
        src_kind, src_key = _parse_node(src)
        dst_kind, dst_key = _parse_node(dst)

        if not src_key or not dst_key or src_key == dst_key:
            continue

        wire_label = f"#{wire_index} ({src} -> {dst})"
        src_key = resolve_endpoint(src_kind, src_key, wire_label)
        dst_key = resolve_endpoint(dst_kind, dst_key, wire_label)

        if src_key == dst_key:
            continue

        uf.add(src_key)
        uf.add(dst_key)
        uf.union(src_key, dst_key)

        if src_kind == "special":
            special_nodes_seen.add(src_key)
        if dst_kind == "special":
            special_nodes_seen.add(dst_key)

    groups: dict[str, list[str]] = {}
    for node in uf._parent:
        root = uf.find(node)
        groups.setdefault(root, []).append(node)

    emitted_flags: set[str] = set()
    net_geometries: list[NetGeometry] = []
    anonymous_nets = 0

    for members in groups.values():
        member_points = [node_points[node] for node in members if node in node_points]
        if not member_points:
            continue

        min_x = min(x for x, _ in member_points)
        min_y = min(y for _, y in member_points)
        max_x = max(x for x, _ in member_points)
        max_y = max(y for _, y in member_points)
        bounds = (min_x, min_y, max_x, max_y)

        group_specials = [node for node in members if node in special_nodes_seen]
        net_name = _choose_special_node(group_specials) if group_specials else ""
        hub = (
            _label_position(net_name, member_points, bounds)
            if net_name
            else (
                GridSystem.snap(sum(x for x, _ in member_points) / len(member_points)),
                GridSystem.snap(sum(y for _, y in member_points) / len(member_points)),
            )
        )

        if net_name:
            geometry_name = _flag_net_name(net_name)
        else:
            anonymous_nets += 1
            geometry_name = f"N{anonymous_nets}"
        geometry = NetGeometry(name=geometry_name)

        for node in members:
            if node in pin_refs and node in node_points:
                inst, pin_id = pin_refs[node]
                geometry.pins.append(PinPoint(inst, pin_id, node_points[node]))

        if net_name and net_name not in emitted_flags:
            lines.append(_flag_line(hub[0], hub[1], _flag_net_name(net_name)))
            emitted_flags.add(net_name)
            geometry.flags.append(hub)

        for node in members:
            point = node_points.get(node)
            if point is None or point == hub:
                continue
            for start, end in _route_points(point, hub):
                lines.append(_wire_line(start[0], start[1], end[0], end[1]))
                geometry.segments.append(WireSegment(geometry_name, start, end))

        net_geometries.append(geometry)

    # ---- Validate before returning ---------------------------------------
    geometry_diagnostics = validate_net_geometry(net_geometries)
    if strict:
        geometry_diagnostics = _promote_shorts(geometry_diagnostics)
    diagnostics.extend(geometry_diagnostics)

    return "\n".join(lines) + "\n", diagnostics


def generate_asc(circuit: dict[str, Any], strict: bool = False) -> str:
    """Convert a SpiceCraft circuit dict into a LTspice Version-4 ASC string.

    Raises:
        AscExportError: if validation found blocking problems. Warnings are
            logged (one summary line; details at DEBUG), not raised.
    """
    asc, diagnostics = generate_asc_with_diagnostics(circuit, strict=strict)

    warnings = [d for d in diagnostics if d.severity == WARNING]
    if warnings:
        by_code: dict[str, int] = {}
        for diagnostic in warnings:
            by_code[diagnostic.code] = by_code.get(diagnostic.code, 0) + 1
            logger.debug("LTspice export warning:\n%s", diagnostic.format())
        logger.warning(
            "LTspice export of %r produced %d geometry warning(s): %s. "
            "Use generate_asc_with_diagnostics() for details.",
            circuit.get("name", "circuit"),
            len(warnings),
            ", ".join(f"{code} x{count}" for code, count in sorted(by_code.items())),
        )

    if any(d.severity == ERROR for d in diagnostics):
        raise AscExportError(diagnostics)

    return asc
