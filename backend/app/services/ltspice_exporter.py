"""LTspice ASC serialization with source-only connectivity and Manhattan routing.

Symbol definitions, placement, orientation, and headers retain Phase 6 geometry.
The dedicated ``routing`` service owns all wires and label placement; coordinates
never infer logical membership. Shared validation blocks unsafe conductive
contacts for ALL exports, including ``strict=False``. Unsplit perpendicular
interior crossings are nonconductive, as verified with real LTspice netlisting.

``generate_asc_with_routing`` returns the same routed result used to serialize
and validate, so debugging requires neither duplicate routing nor symbol tables.
Diagnostic exports return empty text on any blocking failure; the routed result
still remains inspectable. ``generate_asc`` raises ``AscExportError`` rather than
returning an unsafe or only partially connected artifact.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.asc_validation import (
    ERROR,
    WARNING,
    AscExportError,
    ExportDiagnostic,
    PinPoint,
    validate_net_geometry,
)
from app.services.connectivity import (
    build_connectivity,
    component_identity,
    validate_connectivity,
)
from app.services.grid_system import GridSystem
from app.services.routing import RoutingResult, route_nets
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
    """Unsafe LTspice conductive contacts block export in every mode."""
    promoted_codes = {"NET_SHORT", "WIRE_CROSSES_PIN"}
    return [
        ExportDiagnostic(
            ERROR, d.code, d.message, d.net, d.component, d.pin, d.expected, d.actual
        )
        if d.severity == WARNING and d.code in promoted_codes
        else d
        for d in diagnostics
    ]


def generate_asc_with_routing(
    circuit: dict[str, Any], strict: bool = False
) -> tuple[str, list[ExportDiagnostic], RoutingResult | None]:
    """Export once and expose the exact router result for inspection.

    ``strict`` remains a compatibility argument: unsafe contacts are always
    errors. Blocking failures return empty ASC text, never a plausible partial
    schematic; the routed object and all diagnostics remain inspectable.
    """
    connectivity = build_connectivity(circuit)
    diagnostics = validate_connectivity(connectivity)
    # Fail before placement/routing; diagnostic mode never returns usable text
    # for logically invalid source and generate_asc raises AscExportError.
    if any(d.severity == ERROR for d in diagnostics):
        return "", diagnostics, None

    # LTspice names nodes case-insensitively. Preserve explicit source nets,
    # but never emit labels that would silently merge two distinct groups.
    labels: dict[str, str] = {}
    for group in connectivity.source_groups:
        if not group.pins or not group.labels:
            continue
        key = group.name.casefold()
        if key in labels and labels[key] != group.name:
            diagnostics.append(ExportDiagnostic(
                ERROR, "NET_LABEL_COLLISION",
                "Distinct source nets have case-insensitively identical LTspice FLAG names",
                net=f"{labels[key]} / {group.name}",
            ))
        labels[key] = group.name
    if any(d.severity == ERROR for d in diagnostics):
        return "", diagnostics, None

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

    # ---- Route immutable explicit memberships -----------------------------
    # Reserve ALL definition pins, including unwired singleton pins. Routing
    # cannot claim those pins or let a foreign wire accidentally contact them.
    reserved_pins: list[PinPoint] = []
    for pin in connectivity.pin_refs.values():
        try:
            point = get_pin_coordinate(component_layouts[pin.component], pin.pin)
        except ValueError as exc:
            diagnostics.append(ExportDiagnostic(
                ERROR, "UNRESOLVED_PIN", str(exc), component=pin.component, pin=pin.pin,
            ))
        else:
            reserved_pins.append(PinPoint(pin.component, pin.pin, point))
    if any(d.severity == ERROR for d in diagnostics):
        return "", diagnostics, None

    try:
        # A completely unwired schematic needs no geometry. Preserve Phase6's
        # warning-only generic symbol serialization in that case; unknown
        # symbols still cannot be substituted as obstacles in an active route.
        routed = (route_nets(connectivity, component_layouts)
                  if any(group.pins for group in connectivity.source_groups)
                  else RoutingResult())
    except AscExportError as exc:
        return "", diagnostics + list(exc.diagnostics), None
    diagnostics.extend(d for d in _promote_shorts(routed.diagnostics) if d not in diagnostics)
    if any(d.severity == ERROR for d in diagnostics):
        return "", diagnostics, routed

    net_geometries = routed.net_geometries
    # Check both the router's input model and output against captured source;
    # mutable logical lists must never redefine the immutable source partition.
    diagnostics.extend(d for d in validate_connectivity(connectivity) if d not in diagnostics)
    diagnostics.extend(d for d in validate_connectivity(connectivity, net_geometries)
                       if d not in diagnostics)
    expected_points = {(p.component, p.pin): p.point for p in reserved_pins}
    source_groups = {group.name: group for group in connectivity.source_groups}
    for net in net_geometries:
        for pin in net.pins:
            expected = expected_points.get((pin.component, pin.pin))
            if expected is not None and pin.point != expected:
                diagnostics.append(ExportDiagnostic(
                    ERROR, "PIN_POSITION_MISMATCH", "Routed pin differs from the serialized symbol pin",
                    net=net.name, component=pin.component, pin=pin.pin,
                    expected=expected, actual=pin.point,
                ))
        group = source_groups.get(net.name)
        if group and bool(group.labels) != bool(net.flags):
            diagnostics.append(ExportDiagnostic(
                ERROR, "NET_FLAG_MISMATCH", "Routed flags do not match explicit source label presence",
                net=net.name,
            ))
    expected_flags = sorted((net.name, point, net.name)
                            for net in net_geometries for point in net.flags)
    actual_flags = sorted((flag.net, flag.point, flag.name) for flag in routed.flags)
    if expected_flags != actual_flags:
        diagnostics.append(ExportDiagnostic(
            ERROR, "NET_FLAG_MISMATCH", "Router flags differ from canonical net geometry flags",
        ))
    if any(d.severity == ERROR for d in diagnostics):
        return "", diagnostics, routed

    diagnostics.extend(_promote_shorts(validate_net_geometry(
        net_geometries, reserved_pins=reserved_pins,
    )))
    if any(d.severity == ERROR for d in diagnostics):
        return "", diagnostics, routed

    # Serialize route-owned points only; never guess a hub, label location,
    # membership, or replacement path. SYMBOL/header blocks above are unchanged.
    for net in net_geometries:
        for point in net.flags:
            lines.append(_flag_line(point[0], point[1], net.name))
        for segment in net.segments:
            lines.append(_wire_line(*segment.start, *segment.end))
    return "\n".join(lines) + "\n", diagnostics, routed


def generate_asc_with_diagnostics(
    circuit: dict[str, Any], strict: bool = False
) -> tuple[str, list[ExportDiagnostic]]:
    """Return text and diagnostics, without raising for validation failures."""
    asc, diagnostics, _ = generate_asc_with_routing(circuit, strict=strict)
    return asc, diagnostics


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
