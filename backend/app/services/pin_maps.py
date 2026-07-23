"""Centralized component pin maps for LTspice export.

This module is the single source of truth for component pin definitions on the
backend. Every subsystem that needs to know where a component's pins are —
the LTspice exporter, future ERC checker, or simulation netlist builder — should
import from here.

Public API
----------
COMPONENT_LIBRARY
    Dict mapping canonical kind → ComponentDefinition with full pin data.

PinResolver
    Converts component-relative pin coords to absolute LTspice coords,
    accounting for rotation and horizontal mirror.

get_pin_coordinate(component, pin)
    Convenience wrapper used by ltspice_exporter; returns (x, y) tuple.

resolve_symbol_name(component)
    Returns the LTspice symbol name string for a component dict.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Pin and Component Definition dataclasses
# ---------------------------------------------------------------------------


class PinOrientation(Enum):
    """Direction that a pin faces for electrical connection."""

    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"


@dataclass(frozen=True)
class PinDefinition:
    """Complete definition of a single component pin."""

    id: str              # Canonical pin ID  — e.g. "1", "B", "A"
    name: str            # Human-readable name — e.g. "Base", "Anode"
    x: int               # Relative X offset from component anchor
    y: int               # Relative Y offset from component anchor
    orientation: PinOrientation  # Direction the pin faces


@dataclass(frozen=True)
class ComponentDefinition:
    """Complete definition of a component type for LTspice export."""

    kind: str             # Canonical kind key — e.g. "resistor", "bc547"
    symbol: str           # LTspice symbol name — e.g. "res", "npn"
    prefix: str           # Reference prefix   — e.g. "R", "Q", "U"
    default_rotation: str # Default LTspice rotation — "R0", "R90", etc.
    default_value: str | None
    pins: tuple[PinDefinition, ...]


# ---------------------------------------------------------------------------
# Component Library
# ---------------------------------------------------------------------------
# Pin coordinates match the LTspice symbol origin (anchor point) with the
# default rotation applied. These must stay in sync with the frontend
# definitions in frontend/lib/circuit/library/*.ts.

COMPONENT_LIBRARY: dict[str, ComponentDefinition] = {
    "resistor": ComponentDefinition(
        kind="resistor",
        symbol="res",
        prefix="R",
        default_rotation="R0",
        default_value=None,
        pins=(
            PinDefinition(id="1", name="Pin 1", x=-32, y=0, orientation=PinOrientation.LEFT),
            PinDefinition(id="2", name="Pin 2", x=32,  y=0, orientation=PinOrientation.RIGHT),
        ),
    ),
    "capacitor": ComponentDefinition(
        kind="capacitor",
        symbol="cap",
        prefix="C",
        default_rotation="R0",
        default_value=None,
        pins=(
            PinDefinition(id="1", name="Pin 1", x=-32, y=0, orientation=PinOrientation.LEFT),
            PinDefinition(id="2", name="Pin 2", x=32,  y=0, orientation=PinOrientation.RIGHT),
        ),
    ),
    "bc547": ComponentDefinition(
        kind="bc547",
        symbol="npn",
        prefix="Q",
        default_rotation="R0",
        default_value=None,
        pins=(
            # Pin IDs match frontend transistor.ts: C, B, E
            PinDefinition(id="C", name="Collector", x=0,   y=-32, orientation=PinOrientation.UP),
            PinDefinition(id="B", name="Base",      x=-32, y=0,   orientation=PinOrientation.LEFT),
            PinDefinition(id="E", name="Emitter",   x=0,   y=32,  orientation=PinOrientation.DOWN),
        ),
    ),
    "led": ComponentDefinition(
        kind="led",
        symbol="led",
        prefix="D",
        default_rotation="R0",
        default_value=None,
        pins=(
            PinDefinition(id="A", name="Anode",   x=-32, y=0, orientation=PinOrientation.LEFT),
            PinDefinition(id="K", name="Cathode", x=32,  y=0, orientation=PinOrientation.RIGHT),
        ),
    ),
    "ne555": ComponentDefinition(
        kind="ne555",
        symbol="555timer",
        prefix="U",
        default_rotation="R0",
        default_value="NE555",
        pins=(
            # Standard DIP-8 pinout; coords match frontend ne555.ts
            PinDefinition(id="1", name="GND",   x=-48, y=48,  orientation=PinOrientation.LEFT),
            PinDefinition(id="2", name="TRIG",  x=-48, y=16,  orientation=PinOrientation.LEFT),
            PinDefinition(id="3", name="OUT",   x=48,  y=16,  orientation=PinOrientation.RIGHT),
            PinDefinition(id="4", name="RESET", x=-48, y=-48, orientation=PinOrientation.LEFT),
            PinDefinition(id="5", name="CTRL",  x=48,  y=-16, orientation=PinOrientation.RIGHT),
            PinDefinition(id="6", name="THR",   x=-48, y=-16, orientation=PinOrientation.LEFT),
            PinDefinition(id="7", name="DIS",   x=48,  y=-48, orientation=PinOrientation.RIGHT),
            PinDefinition(id="8", name="VCC",   x=48,  y=48,  orientation=PinOrientation.RIGHT),
        ),
    ),
    "diode": ComponentDefinition(
        kind="diode",
        symbol="diode",
        prefix="D",
        default_rotation="R0",
        default_value="1N4148",
        pins=(
            PinDefinition(id="1", name="Anode",   x=-32, y=0, orientation=PinOrientation.LEFT),
            PinDefinition(id="2", name="Cathode", x=32,  y=0, orientation=PinOrientation.RIGHT),
        ),
    ),
}

# ---------------------------------------------------------------------------
# Alias tables (backward compat + flexible input)
# ---------------------------------------------------------------------------

COMPONENT_KIND_ALIASES: dict[str, str] = {
    "resistor": "resistor",
    "res": "resistor",
    "r": "resistor",
    "capacitor": "capacitor",
    "cap": "capacitor",
    "c": "capacitor",
    "led": "led",
    "diode": "diode",
    "d": "diode",
    "transistor": "bc547",
    "npn": "bc547",
    "bc547": "bc547",
    "bjt": "bc547",
    "ic": "ne555",
    "timer": "ne555",
    "ne555": "ne555",
    "555": "ne555",
    "555timer": "ne555",
}

# Per-kind pin aliases: maps raw pin strings → canonical pin ID
PIN_ALIASES: dict[str, dict[str, str]] = {
    "resistor": {
        "A": "1", "ANODE": "1", "POS": "1", "PLUS": "1", "LEFT": "1",
        "K": "2", "CATHODE": "2", "NEG": "2", "MINUS": "2", "RIGHT": "2",
    },
    "capacitor": {
        "A": "1", "ANODE": "1", "POS": "1", "PLUS": "1", "LEFT": "1",
        "K": "2", "CATHODE": "2", "NEG": "2", "MINUS": "2", "RIGHT": "2",
    },
    "bc547": {
        # Canonical: C, B, E  (matching frontend transistor.ts)
        "COLLECTOR": "C", "BASE": "B", "EMITTER": "E",
        # Numeric per BJT standard: 1=C, 2=B, 3=E
        "1": "C", "2": "B", "3": "E",
    },
    "led": {
        "1": "A", "2": "K",
        "ANODE": "A", "POS": "A", "PLUS": "A", "POSITIVE": "A",
        "CATHODE": "K", "NEG": "K", "MINUS": "K", "NEGATIVE": "K",
    },
    "diode": {
        "A": "1", "ANODE": "1", "POS": "1", "PLUS": "1",
        "K": "2", "CATHODE": "2", "NEG": "2", "MINUS": "2",
    },
    "ne555": {
        # Numeric aliases match pin IDs directly
        "GND": "1", "GROUND": "1",
        "TRIG": "2", "TRIGGER": "2",
        "OUT": "3", "OUTPUT": "3",
        "RESET": "4", "RST": "4",
        "CTRL": "5", "CONTROL": "5", "CV": "5",
        "THR": "6", "THRESH": "6", "THRESHOLD": "6",
        "DIS": "7", "DISCHARGE": "7",
        "VCC": "8", "VDD": "8", "PWR": "8", "POWER": "8",
    },
}

SYMBOL_NAMES: dict[str, str] = {
    "resistor": "res",
    "capacitor": "cap",
    "led": "led",
    "diode": "diode",
    "bc547": "npn",
    "ne555": "555timer",
}

# ---------------------------------------------------------------------------
# Legacy lookup tables (kept for any consumers that still import them directly)
# ---------------------------------------------------------------------------

PIN_MAPS: dict[str, dict[str, int]] = {
    "resistor":  {"1": 0, "2": 1},
    "capacitor": {"1": 0, "2": 1},
    "bc547":     {"C": 0, "B": 1, "E": 2},
    "led":       {"A": 0, "K": 1},
    "diode":     {"1": 0, "2": 1},
    "ne555": {
        "1": 0, "2": 1, "3": 2, "4": 3,
        "5": 4, "6": 5, "7": 6, "8": 7,
    },
}

PIN_COORDINATE_OFFSETS: dict[str, tuple[tuple[int, int], ...]] = {
    "resistor":  ((-32, 0), (32, 0)),
    "capacitor": ((-32, 0), (32, 0)),
    "bc547":     ((0, -32), (-32, 0), (0, 32)),   # C, B, E
    "led":       ((-32, 0), (32, 0)),
    "diode":     ((-32, 0), (32, 0)),
    "ne555": (
        (-48, 48), (-48, 16), (48, 16), (-48, -48),
        (48, -16), (-48, -16), (48, -48), (48, 48),
    ),
}


# ---------------------------------------------------------------------------
# Pin coordinate dataclass (public, used by callers that want structured data)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PinCoordinate:
    x: int
    y: int


# ---------------------------------------------------------------------------
# Pin Resolver: rotation and mirror transformations
# ---------------------------------------------------------------------------


class PinResolver:
    """Resolves absolute pin coordinates accounting for rotation and mirror.

    LTspice rotation strings:
        R0   →   0° (identity)
        R90  →  90° counter-clockwise
        R180 → 180°
        R270 → 270° counter-clockwise (= 90° clockwise)

    Mirror (horizontal flip) is applied before rotation, which matches how
    LTspice handles the MIRROR attribute.
    """

    @staticmethod
    def _rotate(x: int, y: int, rotation: str) -> tuple[int, int]:
        if rotation == "R0":
            return x, y
        if rotation == "R90":
            return -y, x
        if rotation == "R180":
            return -x, -y
        if rotation == "R270":
            return y, -x
        return x, y  # unknown rotation → identity

    @staticmethod
    def _mirror(x: int, y: int, mirrored: bool) -> tuple[int, int]:
        return (-x, y) if mirrored else (x, y)

    @classmethod
    def resolve_pin(
        cls,
        component_def: ComponentDefinition,
        pin_id: str,
        anchor: tuple[int, int],
        rotation: str = "R0",
        mirrored: bool = False,
    ) -> tuple[int, int]:
        """Return the absolute (x, y) coordinate for a pin on a placed component.

        Args:
            component_def: Component definition containing pin geometry.
            pin_id:        Canonical pin ID (already normalized by caller).
            anchor:        Component anchor position in LTspice coordinates.
            rotation:      LTspice rotation string.
            mirrored:      Whether the symbol is horizontally mirrored.

        Raises:
            ValueError: If pin_id is not found in the component definition.
        """
        pin_def = next((p for p in component_def.pins if p.id == pin_id), None)
        if pin_def is None:
            valid = [p.id for p in component_def.pins]
            raise ValueError(
                f"Pin '{pin_id}' not found in component '{component_def.kind}'. "
                f"Valid pins: {valid}"
            )

        rel_x, rel_y = cls._mirror(pin_def.x, pin_def.y, mirrored)
        rel_x, rel_y = cls._rotate(rel_x, rel_y, rotation)

        return anchor[0] + rel_x, anchor[1] + rel_y

    @classmethod
    def resolve_all_pins(
        cls,
        component_def: ComponentDefinition,
        anchor: tuple[int, int],
        rotation: str = "R0",
        mirrored: bool = False,
    ) -> dict[str, tuple[int, int]]:
        """Return absolute coordinates for every pin on a placed component.

        Returns:
            Dict mapping pin ID → (abs_x, abs_y).
        """
        return {
            pin.id: cls.resolve_pin(component_def, pin.id, anchor, rotation, mirrored)
            for pin in component_def.pins
        }


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def _stringify(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def resolve_component_kind(component: dict[str, Any]) -> str:
    """Return the canonical kind key for a component dict."""
    raw_type = _stringify(component.get("type")).lower()
    raw_value = _stringify(component.get("value")).lower()

    # Value-based override takes precedence (e.g. "BC547" → "bc547")
    if raw_value in COMPONENT_KIND_ALIASES:
        return COMPONENT_KIND_ALIASES[raw_value]
    if raw_type in COMPONENT_KIND_ALIASES:
        return COMPONENT_KIND_ALIASES[raw_type]

    return raw_type or raw_value or ""


def resolve_symbol_name(component: dict[str, Any]) -> str:
    """Return the LTspice symbol name for a component dict."""
    kind = resolve_component_kind(component)
    return SYMBOL_NAMES.get(kind, "res")


def _normalize_pin_name(kind: str, pin: str) -> str:
    """Normalize a raw pin reference to the canonical pin ID for this kind."""
    pin_upper = _stringify(pin).upper()
    # Check per-kind alias table first
    canonical = PIN_ALIASES.get(kind, {}).get(pin_upper)
    if canonical:
        return canonical
    # If the raw pin matches a canonical ID directly, return it as-is
    comp_def = COMPONENT_LIBRARY.get(kind)
    if comp_def:
        if any(p.id == pin_upper for p in comp_def.pins):
            return pin_upper
    return pin_upper  # return as-is for unknown pins


def get_pin_coordinate(component: dict[str, Any], pin: str) -> tuple[int, int]:
    """Return the absolute LTspice coordinate for a component pin.

    This is the primary interface used by ltspice_exporter.  The component dict
    must contain ``_ltspice_anchor`` (set by the exporter during placement) and
    optionally ``_ltspice_rotation`` and ``_ltspice_mirror``.

    Raises:
        ValueError: For missing anchor, unsupported kind, or invalid pin.
    """
    kind = resolve_component_kind(component)

    anchor = component.get("_ltspice_anchor")
    if not anchor:
        raise ValueError("Component is missing '_ltspice_anchor' coordinates")
    if not isinstance(anchor, (tuple, list)) or len(anchor) != 2:
        raise ValueError("'_ltspice_anchor' must be a 2-element sequence")
    try:
        ax, ay = int(anchor[0]), int(anchor[1])
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid '_ltspice_anchor' coordinates") from exc

    rotation = str(component.get("_ltspice_rotation", "R0"))
    mirrored = bool(component.get("_ltspice_mirror", False))

    comp_def = COMPONENT_LIBRARY.get(kind)
    if comp_def is None:
        # Graceful fallback: return anchor when the kind is unknown
        raise ValueError(f"Unsupported component kind '{kind}'")

    pin_id = _normalize_pin_name(kind, pin)

    return PinResolver.resolve_pin(comp_def, pin_id, (ax, ay), rotation, mirrored)
