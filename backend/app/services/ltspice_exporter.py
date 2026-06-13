"""
LTspice ASC Exporter Service (Version 1)

Converts the SpiceCraft circuit JSON model into a valid LTspice ASCII schematic
(.asc) file. The exporter keeps component references and values intact while
routing wires against a dedicated pin map so the resulting topology is electrically
meaningful.

Public API
----------
generate_asc(circuit: dict) -> str
    Accepts the raw circuit dict (as stored / returned by the repository) and
    returns the full content of a Version-4 LTspice .asc file as a string.
"""

from __future__ import annotations

from typing import Any

from app.services.ltspice_pin_map import (
    get_pin_coordinate,
    resolve_symbol_name,
)

# ---------------------------------------------------------------------------
# LTspice grid constants
# ---------------------------------------------------------------------------
# LTspice uses a 16-unit internal grid. We space components 256 units apart
# to leave room for net labels and orthogonal routing.
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
    # Passive and transistor symbols are exported horizontally.
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


def _is_ground_node(node: str) -> bool:
    return node.strip().upper() in {"GND", "0", "GROUND"}


def _canonical_special_node(node: str) -> str:
    node_upper = node.strip().upper()
    if node_upper in {"GND", "0", "GROUND"}:
        return "GND"
    if node_upper in {"VCC", "VDD", "PWR"}:
        return "VCC"
    if node_upper in {"VIN", "IN"}:
        return "VIN"
    if node_upper in {"VOUT", "OUT"}:
        return "VOUT"
    return node_upper


def _parse_node(node: str) -> tuple[str, str]:
    raw = node.strip()
    if not raw:
        return "", ""

    if "." in raw:
        ref, pin = raw.split(".", 1)
        return "component", f"{ref.strip()}.{pin.strip()}"

    special = _canonical_special_node(raw)
    return "special", special


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


def _snap(value: float, grid: int = 16) -> int:
    if grid <= 0:
        return int(round(value))
    return int(round(value / grid) * grid)


def _route_wire(start: tuple[int, int], end: tuple[int, int]) -> list[str]:
    if start == end:
        return []

    sx, sy = start
    ex, ey = end

    if sx == ex or sy == ey:
        return [_wire_line(sx, sy, ex, ey)]

    # Route orthogonally using a single elbow.
    elbow_a = (ex, sy)
    if elbow_a != start and elbow_a != end:
        return [
            _wire_line(sx, sy, elbow_a[0], elbow_a[1]),
            _wire_line(elbow_a[0], elbow_a[1], ex, ey),
        ]

    elbow_b = (sx, ey)
    if elbow_b != start and elbow_b != end:
        return [
            _wire_line(sx, sy, elbow_b[0], elbow_b[1]),
            _wire_line(elbow_b[0], elbow_b[1], ex, ey),
        ]

    return [_wire_line(sx, sy, ex, ey)]


def _label_position(
    net_name: str,
    member_points: list[tuple[int, int]],
    bounds: tuple[int, int, int, int],
) -> tuple[int, int]:
    min_x, min_y, max_x, max_y = bounds
    anchor_x, anchor_y = member_points[0]

    if net_name == "GND":
        return min_x - 96, max_y + 96
    if net_name == "VCC":
        return min_x - 96, min_y - 96
    if net_name == "VIN":
        return min_x - 96, _snap(anchor_y)
    if net_name == "VOUT":
        return max_x + 96, _snap(anchor_y)

    return _snap((min_x + max_x) / 2), _snap((min_y + max_y) / 2)


# ---------------------------------------------------------------------------
# Main export function
# ---------------------------------------------------------------------------


def generate_asc(circuit: dict[str, Any]) -> str:
    """Convert a SpiceCraft circuit dict into a LTspice Version-4 ASC string."""
    name: str = str(circuit.get("name", "Circuit"))
    description: str = str(circuit.get("description", ""))
    components: list[dict[str, Any]] = circuit.get("components", [])
    wires: list[dict[str, Any]] = circuit.get("wires", [])

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
    node_points: dict[str, tuple[int, int]] = {}

    for idx, comp in enumerate(components):
        col = idx % COLS_PER_ROW
        row = idx // COLS_PER_ROW
        cx = ORIGIN_X + col * GRID_COL_STEP
        cy = ORIGIN_Y + row * GRID_ROW_STEP

        inst_name = str(comp.get("reference") or comp.get("id") or f"X{idx + 1}")
        raw_type = str(comp.get("type", ""))
        comp_type = _normalise_type(raw_type)
        symbol = resolve_symbol_name(comp)
        if symbol == "res" and comp_type in {"ic", "timer", "ne555", "555"}:
            # TODO: implement dedicated 8-pin placement and symbol mapping for NE555.
            symbol = "res"
        rotation = _rotation(symbol)

        value = comp.get("value")
        value_str = str(value) if value is not None else None

        layout = dict(comp)
        layout["_ltspice_anchor"] = (cx, cy)
        layout["_ltspice_symbol"] = symbol
        component_layouts[inst_name] = layout

        comp_id = str(comp.get("id", "")).strip()
        if comp_id:
            component_layouts[comp_id] = layout

        lines.extend(_symbol_block(symbol, cx, cy, rotation, inst_name, value_str))

    if not wires:
        return "\n".join(lines) + "\n"

    # ---- Connectivity model ----------------------------------------------
    uf = _UnionFind()
    special_nodes_seen: set[str] = set()

    for wire in wires:
        src = str(wire.get("source") or wire.get("from") or "")
        dst = str(wire.get("destination") or wire.get("to") or "")
        src_kind, src_key = _parse_node(src)
        dst_kind, dst_key = _parse_node(dst)

        if not src_key or not dst_key or src_key == dst_key:
            continue

        uf.add(src_key)
        uf.add(dst_key)
        uf.union(src_key, dst_key)

        if src_kind == "special":
            special_nodes_seen.add(src_key)
        if dst_kind == "special":
            special_nodes_seen.add(dst_key)

        if src_kind == "component":
            ref, pin = src_key.split(".", 1)
            component = component_layouts.get(ref)
            if component is not None:
                node_points[src_key] = get_pin_coordinate(component, pin)
        if dst_kind == "component":
            ref, pin = dst_key.split(".", 1)
            component = component_layouts.get(ref)
            if component is not None:
                node_points[dst_key] = get_pin_coordinate(component, pin)

    groups: dict[str, list[str]] = {}
    for node in uf._parent:
        root = uf.find(node)
        groups.setdefault(root, []).append(node)

    emitted_flags: set[str] = set()

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
        net_name = group_specials[0] if group_specials else ""
        hub = (
            _label_position(net_name, member_points, bounds)
            if net_name
            else (
                _snap(sum(x for x, _ in member_points) / len(member_points)),
                _snap(sum(y for _, y in member_points) / len(member_points)),
            )
        )

        if net_name and net_name not in emitted_flags:
            lines.append(
                _flag_line(hub[0], hub[1], "0" if net_name == "GND" else net_name)
            )
            emitted_flags.add(net_name)

        for node in members:
            point = node_points.get(node)
            if point is None or point == hub:
                continue
            lines.extend(_route_wire(point, hub))

    # Safety net for special labels that were not attached to a connected group.
    for special in sorted(special_nodes_seen):
        if special in emitted_flags:
            continue
        point = node_points.get(special)
        if point is None:
            continue
        lines.append(
            _flag_line(point[0], point[1], "0" if special == "GND" else special)
        )

    return "\n".join(lines) + "\n"
