"""Canonical LTspice symbol geometry and pin resolution.

This module is the single source of truth for *physical* pin positions in an
exported ``.asc`` file. Everything that needs to know where a pin is - the
exporter, the debugger, tests, and any future router - must go through here.

Coordinate model
----------------
Every symbol is defined in its own ``.asy`` coordinate space (Y grows downward).
The ``SYMBOL <name> <x> <y> <orientation>`` line in an ``.asc`` file places the
``.asy`` origin ``(0, 0)`` at ``(x, y)``. That origin is the symbol *anchor*; it
is generally NOT the visual centre of the drawing, so ``bounds`` is recorded
separately.

    absolute = anchor + orient(relative)

where ``orient`` applies the LTspice orientation:

    R0   (x, y)          R90  (-y, x)         R180 (-x, -y)       R270 (y, -x)
    M<n> = R<n>, then mirror X:  (x, y) -> (-x, y)

``R90`` is a 90 degree *clockwise* turn as seen on screen (Y is down).

Provenance of the numbers
-------------------------
Pin coordinates below are copied from the stock LTspice symbol files named in
each definition's ``asy_file``. They are NOT estimates. If you add a component,
copy its ``PIN`` lines from the real ``.asy`` rather than choosing offsets.

Public API
----------
COMPONENT_LIBRARY, PinResolver, get_pin_coordinate, resolve_symbol_name,
resolve_component_kind, canonical_pin_id.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Pin and component definition dataclasses
# ---------------------------------------------------------------------------


class PinOrientation(Enum):
    """Direction a pin faces, i.e. the side of the body it leaves from."""

    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"


@dataclass(frozen=True)
class PinDefinition:
    """One pin, positioned in the symbol's own ``.asy`` coordinate space."""

    id: str              # Canonical pin ID - e.g. "1", "B", "A"
    name: str            # Human-readable name - e.g. "Base", "Anode"
    x: int               # X in .asy space, relative to the symbol anchor
    y: int               # Y in .asy space, relative to the symbol anchor
    orientation: PinOrientation  # Direction the pin faces at R0


ROTATION_DEGREES: dict[str, int] = {"R0": 0, "R90": 90, "R180": 180, "R270": 270}
SUPPORTED_ROTATIONS: tuple[str, ...] = tuple(ROTATION_DEGREES)


@dataclass(frozen=True)
class ComponentDefinition:
    """Complete definition of a placeable LTspice symbol."""

    kind: str             # Canonical kind key - e.g. "resistor", "bc547"
    symbol: str           # Name written on the SYMBOL line - e.g. "res", "npn"
    prefix: str           # Reference prefix - e.g. "R", "Q", "U"
    default_rotation: str # Orientation used when exporting - "R0", "R90", ...
    default_value: str | None
    pins: tuple[PinDefinition, ...]
    asy_file: str = ""    # Stock LTspice file the geometry was copied from
    anchor: tuple[int, int] = (0, 0)  # .asy origin; SYMBOL x y lands here
    # Extent of the drawn symbol incl. pins, in .asy space: (min_x, min_y, max_x, max_y)
    bounds: tuple[int, int, int, int] = (0, 0, 0, 0)
    supported_rotations: tuple[str, ...] = SUPPORTED_ROTATIONS
    supports_mirror: bool = True

    @property
    def width(self) -> int:
        return self.bounds[2] - self.bounds[0]

    @property
    def height(self) -> int:
        return self.bounds[3] - self.bounds[1]

    def pin(self, pin_id: str) -> PinDefinition | None:
        return next((p for p in self.pins if p.id == pin_id), None)


# ---------------------------------------------------------------------------
# Component library (geometry copied from stock LTspice .asy files)
# ---------------------------------------------------------------------------

_U, _D, _L, _R = (
    PinOrientation.UP,
    PinOrientation.DOWN,
    PinOrientation.LEFT,
    PinOrientation.RIGHT,
)

COMPONENT_LIBRARY: dict[str, ComponentDefinition] = {
    # res.asy: PIN 16 16 (A, order 1), PIN 16 96 (B, order 2). Vertical at R0.
    "resistor": ComponentDefinition(
        kind="resistor",
        symbol="res",
        prefix="R",
        default_rotation="R0",
        default_value=None,
        pins=(
            PinDefinition(id="1", name="Pin 1", x=16, y=16, orientation=_U),
            PinDefinition(id="2", name="Pin 2", x=16, y=96, orientation=_D),
        ),
        asy_file="res.asy",
        bounds=(0, 16, 32, 96),
    ),
    # cap.asy: PIN 16 0 (A, order 1), PIN 16 64 (B, order 2). Vertical at R0.
    "capacitor": ComponentDefinition(
        kind="capacitor",
        symbol="cap",
        prefix="C",
        default_rotation="R0",
        default_value=None,
        pins=(
            PinDefinition(id="1", name="Pin 1", x=16, y=0, orientation=_U),
            PinDefinition(id="2", name="Pin 2", x=16, y=64, orientation=_D),
        ),
        asy_file="cap.asy",
        bounds=(0, 0, 32, 64),
    ),
    # npn.asy: PIN 64 0 (C, order 1), PIN 0 48 (B, order 2), PIN 64 96 (E, order 3).
    "bc547": ComponentDefinition(
        kind="bc547",
        symbol="npn",
        prefix="Q",
        default_rotation="R0",
        default_value=None,
        pins=(
            PinDefinition(id="C", name="Collector", x=64, y=0, orientation=_U),
            PinDefinition(id="B", name="Base", x=0, y=48, orientation=_L),
            PinDefinition(id="E", name="Emitter", x=64, y=96, orientation=_D),
        ),
        asy_file="npn.asy",
        bounds=(0, 0, 64, 96),
    ),
    # LED.asy: PIN 16 0 (+, order 1), PIN 16 64 (-, order 2).
    "led": ComponentDefinition(
        kind="led",
        symbol="led",
        prefix="D",
        default_rotation="R0",
        default_value=None,
        pins=(
            PinDefinition(id="A", name="Anode", x=16, y=0, orientation=_U),
            PinDefinition(id="K", name="Cathode", x=16, y=64, orientation=_D),
        ),
        asy_file="LED.asy",
        bounds=(0, 0, 72, 64),
    ),
    # Misc\NE555.asy (RECTANGLE -112 -128 112 128). Pin number == SpiceOrder.
    "ne555": ComponentDefinition(
        kind="ne555",
        symbol="Misc\\NE555",
        prefix="U",
        default_rotation="R0",
        default_value="NE555",
        pins=(
            PinDefinition(id="1", name="GND", x=-112, y=-96, orientation=_L),
            PinDefinition(id="2", name="TRIG", x=-112, y=-32, orientation=_L),
            PinDefinition(id="3", name="OUT", x=-112, y=32, orientation=_L),
            PinDefinition(id="4", name="RESET", x=-112, y=96, orientation=_L),
            PinDefinition(id="5", name="CTRL", x=112, y=96, orientation=_R),
            PinDefinition(id="6", name="THR", x=112, y=32, orientation=_R),
            PinDefinition(id="7", name="DIS", x=112, y=-32, orientation=_R),
            PinDefinition(id="8", name="VCC", x=112, y=-96, orientation=_R),
        ),
        asy_file="Misc/NE555.asy",
        bounds=(-112, -128, 112, 128),
    ),
    # diode.asy: PIN 16 0 (+, order 1), PIN 16 64 (-, order 2).
    "diode": ComponentDefinition(
        kind="diode",
        symbol="diode",
        prefix="D",
        default_rotation="R0",
        default_value="1N4148",
        pins=(
            PinDefinition(id="1", name="Anode", x=16, y=0, orientation=_U),
            PinDefinition(id="2", name="Cathode", x=16, y=64, orientation=_D),
        ),
        asy_file="diode.asy",
        bounds=(0, 0, 32, 64),
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

# Per-kind pin aliases: maps raw pin strings -> canonical pin ID
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
        # Canonical: C, B, E
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

# Derived from COMPONENT_LIBRARY so there is exactly one copy of the symbol names.
SYMBOL_NAMES: dict[str, str] = {
    kind: definition.symbol for kind, definition in COMPONENT_LIBRARY.items()
}

# ---------------------------------------------------------------------------
# Legacy lookup tables (kept for consumers that still import them directly).
# Both are DERIVED from COMPONENT_LIBRARY - never edit numbers here.
# ---------------------------------------------------------------------------

PIN_MAPS: dict[str, dict[str, int]] = {
    kind: {pin.id: index for index, pin in enumerate(definition.pins)}
    for kind, definition in COMPONENT_LIBRARY.items()
}

PIN_COORDINATE_OFFSETS: dict[str, tuple[tuple[int, int], ...]] = {
    kind: tuple((pin.x, pin.y) for pin in definition.pins)
    for kind, definition in COMPONENT_LIBRARY.items()
}


@dataclass(frozen=True)
class PinCoordinate:
    x: int
    y: int


# ---------------------------------------------------------------------------
# Pin resolver: the ONE implementation of the orientation transform
# ---------------------------------------------------------------------------

# Clockwise order (as seen on screen, Y down): UP -> RIGHT -> DOWN -> LEFT.
_FACING_CLOCKWISE = (
    PinOrientation.UP,
    PinOrientation.RIGHT,
    PinOrientation.DOWN,
    PinOrientation.LEFT,
)


@dataclass(frozen=True)
class ResolvedPinGeometry:
    """Everything known about one placed pin, for debugging and validation."""

    pin_id: str
    name: str
    relative: tuple[int, int]   # as defined in the .asy file
    oriented: tuple[int, int]   # after rotation / mirror, still relative to anchor
    absolute: tuple[int, int]   # anchor + oriented
    facing: PinOrientation


class PinResolver:
    """Resolves absolute pin coordinates for a placed symbol.

    Orientation semantics (see module docstring): rotate clockwise by the given
    angle, then - for ``M`` variants - mirror X. For R0/R90/R180/R270 and for
    M0/M180 the order is irrelevant. For M90/M270 the order matters; the order
    used here follows KiCad's LTspice importer table (M90 -> (y, x),
    M270 -> (-y, -x)). That has not been confirmed against an LTspice install,
    and the exporter never emits M90/M270.
    """

    @staticmethod
    def parse_orientation(rotation: str, mirrored: bool = False) -> tuple[int, bool]:
        """Return ``(degrees, mirrored)`` for ``"R90"``, ``"M270"`` etc.

        Raises:
            ValueError: for anything that is not R0/R90/R180/R270/M0/M90/M180/M270.
                Unknown orientations are never silently treated as R0.
        """
        text = str(rotation).strip().upper()
        if len(text) >= 2 and text[0] in "RM" and text[1:].isdigit():
            degrees = int(text[1:])
            if degrees in (0, 90, 180, 270):
                return degrees, bool(mirrored) or text[0] == "M"
        raise ValueError(
            f"Unsupported LTspice orientation '{rotation}'. "
            "Expected R0, R90, R180, R270, M0, M90, M180 or M270."
        )

    @classmethod
    def orientation_string(cls, rotation: str, mirrored: bool = False) -> str:
        """The exact token to write on the SYMBOL line (e.g. ``"R90"``, ``"M0"``)."""
        degrees, is_mirrored = cls.parse_orientation(rotation, mirrored)
        return f"{'M' if is_mirrored else 'R'}{degrees}"

    @staticmethod
    def transform_offset(x: int, y: int, degrees: int, mirrored: bool) -> tuple[int, int]:
        """Apply the LTspice orientation to a symbol-space offset."""
        if degrees == 0:
            rx, ry = x, y
        elif degrees == 90:
            rx, ry = -y, x
        elif degrees == 180:
            rx, ry = -x, -y
        elif degrees == 270:
            rx, ry = y, -x
        else:  # parse_orientation guards this; keep the function safe standalone
            raise ValueError(f"Unsupported rotation: {degrees}")
        if mirrored:
            rx = -rx
        return rx, ry

    @staticmethod
    def transform_facing(
        facing: PinOrientation, degrees: int, mirrored: bool
    ) -> PinOrientation:
        """Rotate/mirror the direction a pin faces, consistent with transform_offset."""
        index = _FACING_CLOCKWISE.index(facing)
        index = (index + degrees // 90) % 4
        result = _FACING_CLOCKWISE[index]
        if mirrored:
            if result is PinOrientation.LEFT:
                result = PinOrientation.RIGHT
            elif result is PinOrientation.RIGHT:
                result = PinOrientation.LEFT
        return result

    @classmethod
    def resolve_pin_geometry(
        cls,
        component_def: ComponentDefinition,
        pin_id: str,
        anchor: tuple[int, int],
        rotation: str = "R0",
        mirrored: bool = False,
    ) -> ResolvedPinGeometry:
        """Full geometry for one pin on a placed component.

        Raises:
            ValueError: if the pin or the orientation is not valid for this symbol.
        """
        pin_def = component_def.pin(pin_id)
        if pin_def is None:
            valid = [p.id for p in component_def.pins]
            raise ValueError(
                f"Pin '{pin_id}' not found in component '{component_def.kind}'. "
                f"Valid pins: {valid}"
            )

        degrees, is_mirrored = cls.parse_orientation(rotation, mirrored)
        if f"R{degrees}" not in component_def.supported_rotations:
            raise ValueError(
                f"Rotation R{degrees} is not supported by '{component_def.kind}'."
            )
        if is_mirrored and not component_def.supports_mirror:
            raise ValueError(f"Mirroring is not supported by '{component_def.kind}'.")

        ox, oy = cls.transform_offset(pin_def.x, pin_def.y, degrees, is_mirrored)
        return ResolvedPinGeometry(
            pin_id=pin_def.id,
            name=pin_def.name,
            relative=(pin_def.x, pin_def.y),
            oriented=(ox, oy),
            absolute=(
                anchor[0] + component_def.anchor[0] + ox,
                anchor[1] + component_def.anchor[1] + oy,
            ),
            facing=cls.transform_facing(pin_def.orientation, degrees, is_mirrored),
        )

    @classmethod
    def resolve_pin(
        cls,
        component_def: ComponentDefinition,
        pin_id: str,
        anchor: tuple[int, int],
        rotation: str = "R0",
        mirrored: bool = False,
    ) -> tuple[int, int]:
        """Absolute ``(x, y)`` of a pin on a placed component."""
        return cls.resolve_pin_geometry(
            component_def, pin_id, anchor, rotation, mirrored
        ).absolute

    @classmethod
    def resolve_all_pins(
        cls,
        component_def: ComponentDefinition,
        anchor: tuple[int, int],
        rotation: str = "R0",
        mirrored: bool = False,
    ) -> dict[str, tuple[int, int]]:
        """Absolute coordinates for every pin: ``{pin_id: (x, y)}``."""
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

    # Value-based override takes precedence (e.g. "BC547" -> "bc547")
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
    canonical = PIN_ALIASES.get(kind, {}).get(pin_upper)
    if canonical:
        return canonical
    return pin_upper  # already canonical, or unknown (resolver reports unknown)


def canonical_pin_id(component: dict[str, Any], pin: str) -> str:
    """Canonical pin id for a raw pin reference, so ``Q1.B`` and ``Q1.base`` match."""
    return _normalize_pin_name(resolve_component_kind(component), pin)


def get_pin_coordinate(component: dict[str, Any], pin: str) -> tuple[int, int]:
    """Absolute LTspice coordinate for a component pin.

    The component dict must contain ``_ltspice_anchor`` (set by the exporter
    during placement) and optionally ``_ltspice_rotation`` / ``_ltspice_mirror``.
    These are the same fields the exporter writes onto the SYMBOL line, so the
    symbol placement and the pin coordinate cannot drift apart.

    Raises:
        ValueError: for missing anchor, unsupported kind, bad orientation, or
            invalid pin.
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
        raise ValueError(f"Unsupported component kind '{kind}'")

    pin_id = _normalize_pin_name(kind, pin)
    return PinResolver.resolve_pin(comp_def, pin_id, (ax, ay), rotation, mirrored)
