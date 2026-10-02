"""
LTspice Export Debugger.

Provides human-readable inspection of component pins and electrical nets as
they will appear in an exported .asc file.  Use these helpers to diagnose
incorrect wire connections, missing pin definitions, or invalid connectivity
before running a full export.

Usage
-----
    from app.services.exporter_debugger import ExporterDebugger

    ExporterDebugger.print_pins(component_layout)
    ExporterDebugger.print_connections(circuit_dict)
    ExporterDebugger.print_geometry(component_layout)   # symbol + pin geometry
    ExporterDebugger.print_circuit_geometry(circuit_dict)

Output examples
---------------
R1
  Pin 1   (128, 96)
  Pin 2   (192, 96)

Net N1
  R1.Pin2  → (192, 96)
  ↓ Q1.B   → (320, 128)
  ↓ C1.1   → (448, 128)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from app.services.asc_validation import ExportDiagnostic

if TYPE_CHECKING:
    from app.services.routing import RoutingResult

from app.services.connectivity import (
    ConnectivityModel,
    build_connectivity,
    component_identity,
    validate_connectivity,
)
from app.services.pin_maps import (
    COMPONENT_LIBRARY,
    PinResolver,
    get_pin_coordinate,
    resolve_component_kind,
    resolve_symbol_name,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _inst_name(comp: dict[str, Any], idx: int) -> str:
    return component_identity(comp, idx)


def _all_pin_coords(comp: dict[str, Any]) -> list[tuple[str, str, tuple[int, int] | None]]:
    """Return [(pin_id, pin_name, (abs_x, abs_y))] for every pin on comp."""
    kind = resolve_component_kind(comp)
    comp_def = COMPONENT_LIBRARY.get(kind)
    if comp_def is None:
        return []

    result: list[tuple[str, str, tuple[int, int] | None]] = []
    for pin in comp_def.pins:
        try:
            coord: tuple[int, int] | None = get_pin_coordinate(comp, pin.id)
        except ValueError:
            coord = None
        result.append((pin.id, pin.name, coord))

    return result


# ---------------------------------------------------------------------------
# ExporterDebugger
# ---------------------------------------------------------------------------


class ExporterDebugger:
    """Static helpers for inspecting the pin-resolved export state."""

    @staticmethod
    def format_pins(component: dict[str, Any], index: int = 0) -> str:
        """Return a formatted string showing every pin with its absolute coord.

        Args:
            component: Component dict that has ``_ltspice_anchor`` set.
            index:     Position of the component in the circuit list (for naming).

        Returns:
            Multi-line string.  Example::

                R1
                  Pin 1   (128, 96)
                  Pin 2   (192, 96)
        """
        inst = _inst_name(component, index)
        lines = [inst]
        entries = _all_pin_coords(component)

        if not entries:
            kind = resolve_component_kind(component)
            lines.append(f"  <no pin definitions for kind '{kind}'>")
        else:
            for pin_id, pin_name, coord in entries:
                coord_str = f"({coord[0]}, {coord[1]})" if coord else "<unresolvable>"
                lines.append(f"  {pin_name:<12}  {pin_id:<6}  {coord_str}")

        return "\n".join(lines)

    @staticmethod
    def print_pins(component: dict[str, Any], index: int = 0) -> str:
        """Print and return the formatted pin listing for a single component."""
        output = ExporterDebugger.format_pins(component, index)
        print(output)
        return output

    @staticmethod
    def format_geometry(component: dict[str, Any], index: int = 0) -> str:
        """Return the symbol placement and per-pin geometry of one component.

        Every number comes from ``PinResolver.resolve_pin_geometry``, i.e. the
        same code path the exporter uses for wire endpoints.

        Args:
            component: Component dict that has been through ``place_component``
                       (needs ``_ltspice_anchor``).
            index:     Position in the circuit list (used for naming only).

        Example::

            Q1
              Symbol:     npn  (npn.asy)
              Position:   (500, 300)
              Rotation:   R0
              Mirror:     False
              Bounds:     64 x 96
              Collector (C)
                relative = (64, 0)
                oriented = (64, 0)
                absolute = (564, 300)
        """
        inst = _inst_name(component, index)
        kind = resolve_component_kind(component)
        comp_def = COMPONENT_LIBRARY.get(kind)
        lines = [inst]

        if comp_def is None:
            lines.append(f"  <no symbol definition for kind '{kind}'>")
            return "\n".join(lines)

        anchor = component.get("_ltspice_anchor")
        rotation = str(component.get("_ltspice_rotation", "R0"))
        mirrored = bool(component.get("_ltspice_mirror", False))

        if not anchor:
            lines.append("  <component has not been placed: no _ltspice_anchor>")
            return "\n".join(lines)

        anchor_xy = (int(anchor[0]), int(anchor[1]))
        try:
            orientation = PinResolver.orientation_string(rotation, mirrored)
        except ValueError as exc:
            lines.append(f"  <{exc}>")
            return "\n".join(lines)

        asy = f"  ({comp_def.asy_file})" if comp_def.asy_file else ""
        lines.append(f"  Symbol:     {resolve_symbol_name(component)}{asy}")
        lines.append(f"  Position:   ({anchor_xy[0]}, {anchor_xy[1]})")
        lines.append(f"  Rotation:   {rotation}")
        lines.append(f"  Mirror:     {mirrored}")
        lines.append(f"  SYMBOL:     {orientation}")
        lines.append(f"  Bounds:     {comp_def.width} x {comp_def.height}")

        for pin in comp_def.pins:
            try:
                geo = PinResolver.resolve_pin_geometry(
                    comp_def, pin.id, anchor_xy, rotation, mirrored
                )
            except ValueError as exc:
                lines.append(f"  {pin.name} ({pin.id})")
                lines.append(f"    <unresolvable: {exc}>")
                continue
            lines.append(f"  {geo.name} ({geo.pin_id})  facing {geo.facing.value}")
            lines.append(f"    relative = ({geo.relative[0]}, {geo.relative[1]})")
            lines.append(f"    oriented = ({geo.oriented[0]}, {geo.oriented[1]})")
            lines.append(f"    absolute = ({geo.absolute[0]}, {geo.absolute[1]})")

        return "\n".join(lines)

    @staticmethod
    def print_geometry(component: dict[str, Any], index: int = 0) -> str:
        """Print and return the geometry listing for a single component."""
        output = ExporterDebugger.format_geometry(component, index)
        print(output)
        return output

    @staticmethod
    def format_circuit_geometry(circuit: dict[str, Any]) -> str:
        """Geometry listing for every component of a raw circuit dict.

        Runs the exporter's own placement step so the numbers match what an
        export of this circuit would write.
        """
        # Imported lazily so this debugging module never forces the exporter
        # (and its logging setup) to load for callers that only need pins.
        from app.services.ltspice_exporter import place_components
        from app.services.connectivity import component_identity

        components = circuit.get("components", [])
        layouts = place_components(components, build_connectivity(circuit))
        blocks: list[str] = []
        for idx, comp in enumerate(components):
            layout = layouts[component_identity(comp, idx)]
            blocks.append(ExporterDebugger.format_geometry(layout, idx))
        return "\n\n".join(blocks) if blocks else "<no components>"

    @staticmethod
    def print_circuit_geometry(circuit: dict[str, Any]) -> str:
        """Print and return the geometry listing for a whole circuit."""
        output = ExporterDebugger.format_circuit_geometry(circuit)
        print(output)
        return output

    @staticmethod
    def format_connections(circuit: dict[str, Any]) -> str:
        """Return a formatted string describing every electrical net.

        The circuit dict must have gone through the exporter's component
        placement step (i.e., each component dict must have ``_ltspice_anchor``).

        Args:
            circuit: Raw circuit dict or one that already has ``_ltspice_anchor``
                     stamped onto each component.

        Returns:
            Multi-line string.  Example::

                Net N1
                  R1.Pin2  → (192, 96)
                  ↓ Q1.B   → (320, 128)
        """
        model = build_connectivity(circuit)
        lines: list[str] = ["Electrical Nets (explicit source model)", "───────────────", ""]
        if not model.nets:
            lines.append("  <no connections>")
        for net in model.nets:
            lines.extend(ExporterDebugger._format_net(model, net.name))
            lines.append("")
        diagnostics = validate_connectivity(model)
        if diagnostics:
            lines.append("Connectivity Diagnostics")
            for diagnostic in diagnostics:
                lines.append(f"  {diagnostic.severity.upper()}: {diagnostic.format()}")
        return "\n".join(lines).rstrip()

    @staticmethod
    def _format_net(model: ConnectivityModel, node_or_name: str) -> list[str]:
        net = model.trace_net(node_or_name)
        if net is None:
            return [f"<no explicit net for {node_or_name}>"]
        lines = [f"Net {net.name}"]
        for member in net.members:
            pin = model.pin_refs.get(member)
            if pin is None:
                lines.append(f"  [{member}]")
                continue
            component = model.components[pin.component]
            definition = COMPONENT_LIBRARY.get(resolve_component_kind(component))
            pin_def = definition.pin(pin.pin) if definition else None
            label = f"{pin_def.name} ({pin.pin})" if pin_def else pin.pin
            try:
                coord = get_pin_coordinate(component, pin.pin)
                suffix = f"  → ({coord[0]}, {coord[1]})"
            except ValueError:
                suffix = ""  # raw circuits need no layout for logical traces
            lines.append(f"  {pin.key}  {label}{suffix}")
        for wire in model.wires_for_net(node_or_name):
            lines.append(f"  {wire.format()} => {wire.source} -> {wire.destination}")
        return lines

    @staticmethod
    def trace_net(circuit: dict[str, Any], node_or_name: str) -> str:
        """Inspect an actual named/anonymous net with canonical pins and source edges."""
        model = build_connectivity(circuit)
        return "\n".join(ExporterDebugger._format_net(model, node_or_name))

    @staticmethod
    def trace_pin(circuit: dict[str, Any], component: str, pin: str | None = None) -> str:
        """Trace REF.pin (or component, pin), accepting existing identity/pin aliases."""
        key = f"{component}.{pin}" if pin is not None else component
        return ExporterDebugger.trace_net(circuit, key)

    @staticmethod
    def format_routing(
        routed: RoutingResult | None, diagnostics: Sequence[ExportDiagnostic] | None = None
    ) -> str:
        """Inspect the exact ``generate_asc_with_routing`` result, without routing again.

        ``routed`` is a RoutingResult (or None after an early logical failure).
        Pass the export's diagnostics to include shared collision/membership gates.
        """
        lines = ["Routed Geometry"]
        if routed is None:
            lines.append("  <routing not produced>")
        else:
            for net in routed.net_geometries:
                lines.append(f"Net {net.name}")
                for pin in net.pins:
                    lines.append(f"  Pin {pin.component}.{pin.pin} -> {pin.point}")
                for point in net.flags:
                    lines.append(f"  FLAG {point} {net.name}")
                for segment in net.segments:
                    lines.append(f"  WIRE {segment.start} -> {segment.end}")
                for point in routed.junctions.get(net.name, ()):
                    lines.append(f"  Junction {point}")
            for crossing in routed.crossings:
                lines.append(f"Safe crossing {crossing.nets} at {crossing.point} (nonconductive)")
            lines.append("Routing Metrics")
            for name, value in sorted(routed.metrics.items()):
                lines.append(f"  {name}: {value}")
        found = diagnostics if diagnostics is not None else (routed.diagnostics if routed else [])
        if found:
            lines.append("Export Diagnostics")
            for diagnostic in found:
                lines.append(f"  {diagnostic.severity.upper()}: {diagnostic.format()}")
        return "\n".join(lines)

    @staticmethod
    def print_routing(
        routed: RoutingResult | None, diagnostics: Sequence[ExportDiagnostic] | None = None
    ) -> str:
        """Print and return a previously computed routing inspection."""
        output = ExporterDebugger.format_routing(routed, diagnostics)
        print(output)
        return output

    @staticmethod
    def print_connections(circuit: dict[str, Any]) -> str:
        """Print and return the formatted net listing for a circuit."""
        output = ExporterDebugger.format_connections(circuit)
        print(output)
        return output
