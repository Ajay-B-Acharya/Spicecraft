"""LTspice symbol and pin mapping helpers.

This module centralizes symbol selection and pin-coordinate resolution so the
ASC exporter can route wires against a consistent component model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# LTspice symbols that are currently supported by Export V1.
#
# TODO: add dedicated 8-pin support for NE555 / timer ICs when the export
# validation suite includes timer topologies.
SUPPORTED_KIND_MAP: dict[str, str] = {
    "resistor": "res",
    "res": "res",
    "r": "res",
    "capacitor": "cap",
    "cap": "cap",
    "c": "cap",
    "led": "led",
    "diode": "led",
    "d": "led",
    "transistor": "npn",
    "npn": "npn",
    "bc547": "npn",
    "bjt": "npn",
}

# Supported LTspice symbol placements.
# Coordinates are relative to the symbol anchor passed in the ASC file.
PIN_OFFSETS: dict[str, dict[str, tuple[int, int]]] = {
    "res": {
        "1": (-32, 0),
        "2": (32, 0),
        "a": (-32, 0),
        "k": (32, 0),
    },
    "cap": {
        "1": (-32, 0),
        "2": (32, 0),
        "a": (-32, 0),
        "k": (32, 0),
    },
    "led": {
        "1": (-32, 0),
        "2": (32, 0),
        "a": (-32, 0),
        "k": (32, 0),
    },
    "npn": {
        "b": (-32, 0),
        "c": (32, -16),
        "e": (32, 16),
        "1": (32, -16),
        "2": (-32, 0),
        "3": (32, 16),
    },
}

PIN_ALIASES: dict[str, dict[str, str]] = {
    "res": {
        "anode": "1",
        "pos": "1",
        "plus": "1",
        "cathode": "2",
        "neg": "2",
        "minus": "2",
    },
    "cap": {
        "anode": "1",
        "pos": "1",
        "plus": "1",
        "cathode": "2",
        "neg": "2",
        "minus": "2",
    },
    "led": {
        "anode": "a",
        "pos": "a",
        "plus": "a",
        "cathode": "k",
        "neg": "k",
        "minus": "k",
    },
    "npn": {
        "base": "b",
        "collector": "c",
        "emitter": "e",
    },
}

SYMBOL_NAMES: dict[str, str] = {
    "res": "res",
    "cap": "cap",
    "led": "led",
    "npn": "npn",
}


@dataclass(frozen=True)
class PinCoordinate:
    x: int
    y: int


def _stringify(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def resolve_component_kind(component: dict[str, Any]) -> str:
    """Return the normalized LTspice component kind for a JSON component."""
    raw_type = _stringify(component.get("type")).lower()
    raw_value = _stringify(component.get("value")).lower()

    if raw_value == "bc547":
        return "npn"

    if raw_type in {"ic", "timer", "ne555", "555"} or raw_value == "ne555":
        # Keep the export pipeline working, but full 8-pin support is deferred.
        return "ic"

    if raw_type in SUPPORTED_KIND_MAP:
        return SUPPORTED_KIND_MAP[raw_type]

    if raw_value == "red" and raw_type == "led":
        return "led"

    return SUPPORTED_KIND_MAP.get(raw_value, raw_type or "")


def resolve_symbol_name(component: dict[str, Any]) -> str:
    """Map a component dict to an LTspice symbol name."""
    kind = resolve_component_kind(component)
    return SYMBOL_NAMES.get(kind, "res")


def _normalize_pin_name(pin: str) -> str:
    return _stringify(pin).lower()


def get_pin_coordinate(component: dict[str, Any], pin: str) -> tuple[int, int]:
    """Return the LTspice coordinate for the requested pin.

    The component dict must include the exported anchor position. The exporter
    stores this on the component before calling into this module.
    """
    kind = resolve_component_kind(component)
    if kind == "ic":
        raise ValueError("NE555 / IC pin mapping is not implemented yet")

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

    normalized_pin = _normalize_pin_name(pin)
    aliases = PIN_ALIASES.get(kind, {})
    normalized_pin = aliases.get(normalized_pin, normalized_pin)

    offsets = PIN_OFFSETS.get(kind)
    if not offsets:
        raise ValueError(f"Unsupported LTspice component kind: {kind}")

    offset = offsets.get(normalized_pin)
    if offset is None:
        raise ValueError(f"Unsupported pin '{pin}' for LTspice kind '{kind}'")

    return ax + offset[0], ay + offset[1]
