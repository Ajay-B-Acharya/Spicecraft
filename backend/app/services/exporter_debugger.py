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

from typing import Any

from app.services.pin_maps import (
    COMPONENT_LIBRARY,
    get_pin_coordinate,
    resolve_component_kind,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _inst_name(comp: dict[str, Any], idx: int) -> str:
    return str(comp.get("reference") or comp.get("id") or f"X{idx + 1}")


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


def _parse_node(node_str: str) -> tuple[str, str] | None:
    """Split 'REF.pin' into (ref, pin).  Returns None for special nodes."""
    raw = node_str.strip()
    if "." in raw:
        ref, pin = raw.split(".", 1)
        return ref.strip(), pin.strip()
    return None


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
        components_raw: list[dict[str, Any]] = circuit.get("components", [])
        wires: list[dict[str, Any]] = circuit.get("wires", [])

        # Build a lookup: inst_name → component dict
        comp_map: dict[str, dict[str, Any]] = {}
        for idx, comp in enumerate(components_raw):
            name = _inst_name(comp, idx)
            comp_map[name] = comp
            # Also index by id if different
            comp_id = str(comp.get("id", "")).strip()
            if comp_id and comp_id != name:
                comp_map[comp_id] = comp

        # Build nets via union-find (mirrors exporter logic)
        parent: dict[str, str] = {}

        def _find(x: str) -> str:
            if parent.setdefault(x, x) != x:
                parent[x] = _find(parent[x])
            return parent[x]

        def _union(a: str, b: str) -> None:
            ra, rb = _find(a), _find(b)
            if ra != rb:
                parent[rb] = ra

        for wire in wires:
            src = str(wire.get("source") or wire.get("from") or "")
            dst = str(wire.get("destination") or wire.get("to") or "")
            if not src or not dst or src == dst:
                continue
            _union(src, dst)

        # Group nodes into nets
        net_groups: dict[str, list[str]] = {}
        for node in list(parent.keys()):
            root = _find(node)
            net_groups.setdefault(root, []).append(node)

        lines: list[str] = ["Electrical Nets", "───────────────", ""]

        if not net_groups:
            lines.append("  <no connections>")
            return "\n".join(lines)

        for net_idx, (_, members) in enumerate(sorted(net_groups.items()), 1):
            lines.append(f"Net N{net_idx}")

            sorted_members = sorted(members)
            for i, member in enumerate(sorted_members):
                parsed = _parse_node(member)
                arrow = "  " if i == 0 else "  ↓ "

                if parsed:
                    ref, raw_pin = parsed
                    comp = comp_map.get(ref)
                    coord = None
                    pin_label = raw_pin
                    if comp is not None:
                        try:
                            coord = get_pin_coordinate(comp, raw_pin)
                        except ValueError:
                            pass
                        # Resolve display name
                        kind = resolve_component_kind(comp)
                        comp_def = COMPONENT_LIBRARY.get(kind)
                        if comp_def:
                            pin_def = next((p for p in comp_def.pins if p.id == raw_pin), None)
                            if pin_def:
                                pin_label = f"{pin_def.name} ({pin_def.id})"

                    coord_str = f"  → ({coord[0]}, {coord[1]})" if coord else ""
                    lines.append(f"  {arrow}{ref}.{pin_label}{coord_str}")
                else:
                    # Special node (VCC, GND, etc.)
                    lines.append(f"  {arrow}[{member}]")

            lines.append("")

        return "\n".join(lines).rstrip()

    @staticmethod
    def print_connections(circuit: dict[str, Any]) -> str:
        """Print and return the formatted net listing for a circuit."""
        output = ExporterDebugger.format_connections(circuit)
        print(output)
        return output
