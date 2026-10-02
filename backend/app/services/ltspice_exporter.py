"""
LTspice ASC Exporter Service (Version 1)

Converts the SpiceCraft circuit JSON model into a valid LTspice ASCII schematic
(.asc) file. The exporter keeps component references and values intact, validates
explicit source connectivity, and routes against the existing dedicated pin map.
Logical model validation does not establish electrical correctness of ASC routing.

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
It reaches the intended pin coordinates but can electrically short distinct nets.
In the installed-LTspice Common Emitter baseline, five intended nets collapse to
ground. Geometry overlap checks report ``NET_SHORT`` / ``WIRE_CROSSES_PIN``
warnings (errors with ``strict=True``), but do not replace LTspice netlisting.
Fixing those physical shorts belongs to Phase 7, not logical connectivity.
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
from app.services.connectivity import (
    build_connectivity,
    component_identity,
    validate_connectivity,
)
from app.services.grid_system import GridSystem
from app.services.pin_maps import (
    COMPONENT_LIBRARY,
    PinResolver,
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

    inst_name = component_identity(comp, idx)
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

    Never raises for validation problems. Logical errors return empty text
    before placement/routing; geometry errors return inspectable but unusable
    text. With ``strict=True`` wires that short or cross other nets are reported
    as errors instead of warnings.
    """
    connectivity = build_connectivity(circuit)
    diagnostics = validate_connectivity(connectivity)
    # Fail before placement/routing; diagnostic mode never returns usable text
    # for logically invalid source and generate_asc raises AscExportError.
    if any(d.severity == ERROR for d in diagnostics):
        return "", diagnostics

    name: str = str(circuit.get("name", "Circuit"))
    description: str = str(circuit.get("description", ""))
    components: list[dict[str, Any]] = circuit.get("components", [])
    lines: list[str] = []

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

    # ---- Validated connectivity model -------------------------------------
    # Coordinates do not participate in logical grouping. Resolve geometry
    # only after the source model passed validation, preserving member order.
    for net in connectivity.nets:
        for pin in net.pins:
            try:
                node_points[pin.key] = get_pin_coordinate(
                    component_layouts[pin.component], pin.pin
                )
            except ValueError as exc:
                diagnostics.append(ExportDiagnostic(
                    ERROR, "UNRESOLVED_PIN", str(exc), net=net.name,
                    component=pin.component, pin=pin.pin,
                ))
    if any(d.severity == ERROR for d in diagnostics):
        return "", diagnostics

    emitted_flags: set[str] = set()
    net_geometries: list[NetGeometry] = []

    for net in connectivity.nets:
        members = net.members
        member_points = [node_points[node] for node in members if node in node_points]
        if not member_points:
            continue

        min_x = min(x for x, _ in member_points)
        min_y = min(y for _, y in member_points)
        max_x = max(x for x, _ in member_points)
        max_y = max(y for _, y in member_points)
        bounds = (min_x, min_y, max_x, max_y)

        net_name = net.special
        hub = (
            _label_position(net_name, member_points, bounds)
            if net_name
            else (
                GridSystem.snap(sum(x for x, _ in member_points) / len(member_points)),
                GridSystem.snap(sum(y for _, y in member_points) / len(member_points)),
            )
        )

        geometry_name = net.name
        geometry = NetGeometry(name=geometry_name)

        for pin in net.pins:
            geometry.pins.append(PinPoint(pin.component, pin.pin, node_points[pin.key]))

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
    # Compare recorded pins with immutable explicit source groups. This does
    # NOT prove LTspice's physical wire interpretation matches those groups.
    diagnostics = validate_connectivity(connectivity, net_geometries)
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
