"""Centralized component pin maps for LTspice export.

PIN_MAPS stores the public, component-oriented pin ordering. Coordinate offsets
are kept beside it so the exporter can convert JSON connections into ASC wires
without embedding component pin assumptions in the export pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PIN_MAPS: dict[str, dict[str, int]] = {
    "resistor": {"1": 0, "2": 1},
    "capacitor": {"1": 0, "2": 1},
    "bc547": {"B": 0, "C": 1, "E": 2},
    "led": {"A": 0, "K": 1},
    "ne555": {
        "1": 0,
        "2": 1,
        "3": 2,
        "4": 3,
        "5": 4,
        "6": 5,
        "7": 6,
        "8": 7,
    },
}

PIN_COORDINATE_OFFSETS: dict[str, tuple[tuple[int, int], ...]] = {
    "resistor": ((-32, 0), (32, 0)),
    "capacitor": ((-32, 0), (32, 0)),
    "bc547": ((-32, 0), (32, -16), (32, 16)),
    "led": ((-32, 0), (32, 0)),
    "ne555": (
        (-48, -48),
        (-48, -16),
        (-48, 16),
        (-48, 48),
        (48, 48),
        (48, 16),
        (48, -16),
        (48, -48),
    ),
}

COMPONENT_KIND_ALIASES: dict[str, str] = {
    "resistor": "resistor",
    "res": "resistor",
    "r": "resistor",
    "capacitor": "capacitor",
    "cap": "capacitor",
    "c": "capacitor",
    "led": "led",
    "diode": "led",
    "d": "led",
    "transistor": "bc547",
    "npn": "bc547",
    "bc547": "bc547",
    "bjt": "bc547",
    "ic": "ne555",
    "timer": "ne555",
    "ne555": "ne555",
    "555": "ne555",
}

PIN_ALIASES: dict[str, dict[str, str]] = {
    "resistor": {
        "A": "1",
        "ANODE": "1",
        "POS": "1",
        "PLUS": "1",
        "K": "2",
        "CATHODE": "2",
        "NEG": "2",
        "MINUS": "2",
    },
    "capacitor": {
        "A": "1",
        "ANODE": "1",
        "POS": "1",
        "PLUS": "1",
        "K": "2",
        "CATHODE": "2",
        "NEG": "2",
        "MINUS": "2",
    },
    "bc547": {
        "BASE": "B",
        "COLLECTOR": "C",
        "EMITTER": "E",
        "1": "C",
        "2": "B",
        "3": "E",
    },
    "led": {
        "1": "A",
        "2": "K",
        "ANODE": "A",
        "POS": "A",
        "PLUS": "A",
        "CATHODE": "K",
        "NEG": "K",
        "MINUS": "K",
    },
}

SYMBOL_NAMES: dict[str, str] = {
    "resistor": "res",
    "capacitor": "cap",
    "led": "led",
    "bc547": "npn",
    "ne555": "res",
}


@dataclass(frozen=True)
class PinCoordinate:
    x: int
    y: int


def _stringify(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def resolve_component_kind(component: dict[str, Any]) -> str:
    """Return the canonical pin-map kind for a circuit component."""
    raw_type = _stringify(component.get("type")).lower()
    raw_value = _stringify(component.get("value")).lower()

    if raw_value == "bc547":
        return "bc547"
    if raw_value == "ne555":
        return "ne555"

    if raw_type in COMPONENT_KIND_ALIASES:
        return COMPONENT_KIND_ALIASES[raw_type]

    return COMPONENT_KIND_ALIASES.get(raw_value, raw_type or "")


def resolve_symbol_name(component: dict[str, Any]) -> str:
    """Map a component dict to an LTspice symbol name."""
    kind = resolve_component_kind(component)
    return SYMBOL_NAMES.get(kind, "res")


def _normalize_pin_name(kind: str, pin: str) -> str:
    pin_name = _stringify(pin).upper()
    return PIN_ALIASES.get(kind, {}).get(pin_name, pin_name)


def get_pin_coordinate(component: dict[str, Any], pin: str) -> tuple[int, int]:
    """Return the LTspice coordinate for a component pin."""
    kind = resolve_component_kind(component)

    anchor = component.get("_ltspice_anchor")
    if not anchor:
        raise ValueError("Component is missing LTspice anchor coordinates")

    if not isinstance(anchor, (tuple, list)) or len(anchor) != 2:
        raise ValueError("Invalid LTspice anchor coordinates")

    try:
        ax = int(anchor[0])
        ay = int(anchor[1])
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid LTspice anchor coordinates") from exc

    pin_name = _normalize_pin_name(kind, pin)
    pin_map = PIN_MAPS.get(kind)
    if not pin_map:
        raise ValueError(f"Unsupported LTspice component kind: {kind}")

    pin_index = pin_map.get(pin_name)
    if pin_index is None:
        raise ValueError(f"Unsupported pin '{pin}' for LTspice kind '{kind}'")

    offsets = PIN_COORDINATE_OFFSETS[kind]
    try:
        offset_x, offset_y = offsets[pin_index]
    except IndexError as exc:
        raise ValueError(f"Pin map index is out of range for kind '{kind}'") from exc

    return ax + offset_x, ay + offset_y
