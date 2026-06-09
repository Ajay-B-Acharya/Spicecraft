"""
LTspice ASC Exporter Service (Version 1)

Converts the SpiceCraft circuit JSON model into a valid LTspice ASCII schematic
(.asc) file.  The design is intentionally stateless so future improvements
(e.g. proper net-based wire routing, custom symbol paths) can be layered on
without breaking the public interface.

Public API
----------
generate_asc(circuit: dict) -> str
    Accepts the raw circuit dict (as stored / returned by the repository) and
    returns the full content of a Version-4 LTspice .asc file as a string.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# LTspice grid constants
# ---------------------------------------------------------------------------
# LTspice uses a 16-unit internal grid; components are typically placed on
# 64-unit boundaries.  We space components 256 units apart (≈ 4 grid cells)
# to give room for labels and wires.
GRID_COL_STEP = 256
GRID_ROW_STEP = 256
COLS_PER_ROW = 4
ORIGIN_X = 64
ORIGIN_Y = 128

# ---------------------------------------------------------------------------
# Component type → LTspice symbol name
# ---------------------------------------------------------------------------
# The keys are normalised lowercase strings derived from the circuit JSON
# "type" field.  Unknown types fall back to a generic voltage-less symbol.
_SYMBOL_MAP: dict[str, str] = {
    # Passives
    "resistor": "res",
    "res": "res",
    "r": "res",
    "capacitor": "cap",
    "cap": "cap",
    "c": "cap",
    "inductor": "ind",
    "ind": "ind",
    "l": "ind",
    # Sources
    "voltage_source": "voltage",
    "vsource": "voltage",
    "voltage": "voltage",
    "v": "voltage",
    "current_source": "current",
    "isource": "current",
    "current": "current",
    "i": "current",
    # Semiconductors
    "transistor": "npn",   # default NPN when subtype unknown
    "npn": "npn",
    "pnp": "pnp",
    "bjt": "npn",
    "diode": "diode",
    "d": "diode",
    # Ground / power flags  (handled separately — see _is_ground / _is_power)
    "ground": "0",
    "gnd": "0",
}

# Symbol strings that need a vertical rotation to look natural in LTspice
_ROTATE_R90: set[str] = {"voltage", "current"}


def _normalise_type(raw_type: str) -> str:
    """Lower-case and strip the component type string."""
    return raw_type.strip().lower() if raw_type else ""


def _ltspice_symbol(component_type: str) -> str:
    """Map a normalised component type to an LTspice symbol name."""
    return _SYMBOL_MAP.get(component_type, "res")  # safe fallback


def _rotation(symbol: str) -> str:
    """Return the LTspice rotation string for the symbol."""
    return "R90" if symbol in _ROTATE_R90 else "R0"


def _is_ground_node(node: str) -> bool:
    return node.strip().upper() in {"GND", "0", "GROUND"}


def _is_power_node(node: str) -> bool:
    return node.strip().upper() in {"VCC", "VDD", "VIN", "VOUT", "OUT", "IN", "PWR"}


# ---------------------------------------------------------------------------
# ASC line builders
# ---------------------------------------------------------------------------

def _symbol_block(
    symbol: str,
    x: int,
    y: int,
    rotation: str,
    inst_name: str,
    value: str | None,
) -> list[str]:
    """Return the SYMBOL + SYMATTR lines for one component."""
    lines = [f"SYMBOL {symbol} {x} {y} {rotation}"]
    lines.append(f"SYMATTR InstName {inst_name}")
    if value:
        lines.append(f"SYMATTR Value {value}")
    return lines


def _wire_line(x1: int, y1: int, x2: int, y2: int) -> str:
    return f"WIRE {x1} {y1} {x2} {y2}"


def _flag_line(x: int, y: int, net: str) -> str:
    return f"FLAG {x} {y} {net}"


def _text_line(x: int, y: int, text: str) -> str:
    # LTspice TEXT: position, justification (Left), font-size (2), content
    return f"TEXT {x} {y} Left 2 ;{text}"


# ---------------------------------------------------------------------------
# Main export function
# ---------------------------------------------------------------------------

def generate_asc(circuit: dict[str, Any]) -> str:
    """
    Convert a SpiceCraft circuit dict into a LTspice Version-4 ASC string.

    Parameters
    ----------
    circuit:
        The raw circuit dict as returned by ``CircuitRepository``.

    Returns
    -------
    str
        Full text content of a ``.asc`` file, ready to be written to disk or
        streamed as an HTTP response.
    """
    name: str = str(circuit.get("name", "Circuit"))
    description: str = str(circuit.get("description", ""))
    components: list[dict[str, Any]] = circuit.get("components", [])
    wires: list[dict[str, Any]] = circuit.get("wires", [])

    lines: list[str] = []

    # ---- Header -----------------------------------------------------------
    lines.append("Version 4")
    lines.append("SHEET 1 1200 800")

    # ---- Comment header ---------------------------------------------------
    lines.append(_text_line(16, 16, f"{name}"))
    if description:
        lines.append(_text_line(16, 48, description))

    # ---- Components -------------------------------------------------------
    # Map component id → grid position so we can reference them for wires.
    component_positions: dict[str, tuple[int, int]] = {}

    for idx, comp in enumerate(components):
        col = idx % COLS_PER_ROW
        row = idx // COLS_PER_ROW
        cx = ORIGIN_X + col * GRID_COL_STEP
        cy = ORIGIN_Y + row * GRID_ROW_STEP

        raw_type = str(comp.get("type", ""))
        comp_type = _normalise_type(raw_type)
        symbol = _ltspice_symbol(comp_type)
        rotation = _rotation(symbol)

        # Prefer "reference" as the instance name; fall back to "id"
        inst_name = str(
            comp.get("reference") or comp.get("id") or f"X{idx + 1}"
        )
        value = comp.get("value")
        value_str = str(value) if value is not None else None

        lines.extend(_symbol_block(symbol, cx, cy, rotation, inst_name, value_str))

        # Store pin-0 position (top-left of symbol bounding box) for wire gen
        component_positions[inst_name] = (cx, cy)
        # Also index by "id" field for wire lookups
        comp_id = str(comp.get("id", ""))
        if comp_id and comp_id != inst_name:
            component_positions[comp_id] = (cx, cy)

    # ---- Ground / power flags from wires ----------------------------------
    # For V1 we emit FLAG entries for GND and power rails rather than
    # attempting full coordinate-based wire routing.
    emitted_flags: set[str] = set()
    flag_x = ORIGIN_X
    flag_y = ORIGIN_Y + (((len(components) - 1) // COLS_PER_ROW) + 2) * GRID_ROW_STEP

    for wire in wires:
        src = str(wire.get("source") or wire.get("from") or "")
        dst = str(wire.get("destination") or wire.get("to") or "")

        for node in (src, dst):
            node_upper = node.strip().upper()
            if _is_ground_node(node) and node_upper not in emitted_flags:
                lines.append(_flag_line(flag_x, flag_y, "0"))
                emitted_flags.add(node_upper)
                flag_x += 64
            elif _is_power_node(node) and node_upper not in emitted_flags:
                lines.append(_flag_line(flag_x, flag_y, node.strip()))
                emitted_flags.add(node_upper)
                flag_x += 96

    # ---- Wires (V1: horizontal stubs between adjacent components) ---------
    # We emit short connecting wires between consecutive component positions
    # based on the wire adjacency list.  Full net-topology routing is a V2
    # enhancement.
    pin_offsets: dict[str, int] = {
        "res": 16, "cap": 16, "ind": 16,
        "voltage": 0, "current": 0,
        "npn": 32, "pnp": 32,
        "diode": 16,
    }

    def _pin_x(inst: str, symbol: str) -> int:
        pos = component_positions.get(inst)
        if pos:
            return pos[0] + pin_offsets.get(symbol, 16)
        return 0

    def _pin_y(inst: str) -> int:
        pos = component_positions.get(inst)
        return pos[1] if pos else 0

    for wire in wires:
        src = str(wire.get("source") or wire.get("from") or "")
        dst = str(wire.get("destination") or wire.get("to") or "")

        # Skip pure power/ground stubs — already handled as FLAGs
        if _is_ground_node(src) or _is_ground_node(dst):
            continue
        if _is_power_node(src) or _is_power_node(dst):
            continue

        # Parse "REFDES.pin" notation, e.g. "R1.2" → ref="R1", pin="2"
        def _parse_node(node: str) -> tuple[str, str]:
            parts = node.split(".", 1)
            return parts[0], parts[1] if len(parts) > 1 else "1"

        src_ref, _src_pin = _parse_node(src)
        dst_ref, _dst_pin = _parse_node(dst)

        src_pos = component_positions.get(src_ref)
        dst_pos = component_positions.get(dst_ref)

        if src_pos and dst_pos:
            # Draw a simple L-shaped wire: horizontal then vertical
            x1, y1 = src_pos[0] + 16, src_pos[1] + 16
            x2, y2 = dst_pos[0] + 16, dst_pos[1] + 16
            if x1 != x2 or y1 != y2:
                # Horizontal segment
                lines.append(_wire_line(x1, y1, x2, y1))
                # Vertical segment (if needed)
                if y1 != y2:
                    lines.append(_wire_line(x2, y1, x2, y2))

    return "\n".join(lines) + "\n"
