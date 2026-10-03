"""
Pin geometry and frozen compact placement regression tests (Phase 7.5).

The ground truth below is deliberately duplicated from the stock LTspice
``.asy`` files instead of imported from ``app.services.pin_maps``.  If both
sides were derived from the same table, these tests could never fail.

Coordinate conventions (LTspice): Y grows downward, ``SYMBOL name x y ORIENT``
puts the ``.asy`` origin at ``(x, y)``.  ``R90`` is 90 degrees clockwise on
screen.
"""

from __future__ import annotations

import io
import json
import re
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.asc_validation import (  # noqa: E402
    ERROR,
    WARNING,
    AscExportError,
    NetGeometry,
    PinPoint,
    WireSegment,
    validate_net_geometry,
)
from app.services.connectivity import build_connectivity  # noqa: E402
from app.services.exporter_debugger import ExporterDebugger  # noqa: E402
from app.services.grid_system import GridSystem  # noqa: E402
from app.services.ltspice_exporter import (  # noqa: E402
    generate_asc,
    generate_asc_with_diagnostics,
    place_component,
    place_components,
)
from app.services.pin_maps import (  # noqa: E402
    COMPONENT_LIBRARY,
    PinOrientation,
    PinResolver,
    canonical_pin_id,
    get_pin_coordinate,
)

CIRCUITS_DIR = BACKEND_ROOT / "circuits"

# ---------------------------------------------------------------------------
# Independent ground truth: pin positions in .asy space at R0.
# ---------------------------------------------------------------------------

ASY_PINS: dict[str, dict[str, tuple[int, int]]] = {
    "resistor": {"1": (16, 16), "2": (16, 96)},                     # res.asy
    "capacitor": {"1": (16, 0), "2": (16, 64)},                     # cap.asy
    "bc547": {"C": (64, 0), "B": (0, 48), "E": (64, 96)},           # npn.asy
    "led": {"A": (16, 0), "K": (16, 64)},                           # LED.asy
    "diode": {"1": (16, 0), "2": (16, 64)},                         # diode.asy
    "ne555": {                                                       # Misc\NE555.asy
        "1": (-112, -96), "2": (-112, -32), "3": (-112, 32), "4": (-112, 96),
        "5": (112, 96), "6": (112, 32), "7": (112, -32), "8": (112, -96),
    },
}

SYMBOLS: dict[str, str] = {
    "resistor": "res",
    "capacitor": "cap",
    "bc547": "npn",
    "led": "led",
    "diode": "diode",
    "ne555": "Misc\\NE555",
}

# Symbol name on the SYMBOL line -> kind (for parsing exported text).
KIND_BY_SYMBOL = {symbol: kind for kind, symbol in SYMBOLS.items()}

ORIENTATIONS = ["R0", "R90", "R180", "R270", "M0", "M90", "M180", "M270"]

# Transcribed from tests/artifacts/phase_8/before/*.asc, captured at the
# Phase 7.5 checkpoint, NOT generated from the current exporter. Freeze actual
# compact placement, identity and value, not WINDOW/TEXT/SHEET presentation.
# Each record is (instance, symbol, x, y, orientation, value).
PHASE75_SYMBOL_RECORDS = {
    "555_astable_multivibrator.json": [
        ("U1", "Misc\\NE555", 448, 336, "R0", "NE555"),
        ("R1", "res", 752, 320, "R180", "1k"),
        ("R2", "res", 720, 416, "R0", "10k"),
        ("C1", "cap", 208, 448, "R0", "10uF"),
    ],
    "common_emitter_amplifier.json": [
        ("Q1", "npn", 448, 336, "R0", "BC547"),
        ("R1", "res", 224, 224, "R0", "100k"),
        ("R2", "res", 224, 448, "R0", "10k"),
        ("R3", "res", 528, 256, "R180", "1k"),
        ("C1", "cap", 496, 528, "R0", "10uF"),
        ("C2", "cap", 672, 320, "R270", "100uF"),
    ],
    "led_blinker.json": [
        ("Q1", "npn", 448, 336, "R0", "BC547"),
        ("R1", "res", 224, 224, "R0", "10k"),
        ("R2", "res", 784, 464, "R0", "1k"),
        ("C1", "cap", 224, 464, "R0", "10uF"),
        ("D1", "led", 672, 320, "R270", "RED"),
    ],
    "rc_high_pass_filter.json": [
        ("C1", "cap", 160, 208, "R270", "100nF"),
        ("R1", "res", 304, 176, "R0", "1k"),
    ],
    "rc_low_pass_filter.json": [
        ("R1", "res", 144, 208, "R270", "1k"),
        ("C1", "cap", 320, 192, "R0", "100nF"),
    ],
}


def reference_transform(x: int, y: int, orientation: str) -> tuple[int, int]:
    """Independent implementation of the LTspice orientation transform.

    Rotation is clockwise on screen. ``M`` variants rotate first and then mirror
    X. M90/M270 follow the KiCad LTspice importer table and are unverified
    against a real LTspice install.
    """
    degrees = int(orientation[1:])
    for _ in range(degrees // 90):
        x, y = -y, x
    if orientation[0] == "M":
        x = -x
    return x, y


def parse_asc(asc: str):
    """Return ``(symbols, wires, flags)`` parsed from .asc text.

    symbols: ``[{"symbol", "x", "y", "orient", "inst", "value"}]``
    wires:   ``[((x1, y1), (x2, y2))]``
    flags:   ``[((x, y), name)]``
    """
    symbols: list[dict] = []
    wires: list[tuple[tuple[int, int], tuple[int, int]]] = []
    flags: list[tuple[tuple[int, int], str]] = []
    for line in asc.splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "SYMBOL":
            symbols.append(
                {
                    "symbol": parts[1],
                    "x": int(parts[2]),
                    "y": int(parts[3]),
                    "orient": parts[4],
                    "inst": None,
                    "value": None,
                }
            )
        elif parts[0] == "SYMATTR" and parts[1] == "InstName" and symbols:
            symbols[-1]["inst"] = parts[2]
        elif parts[0] == "SYMATTR" and parts[1] == "Value" and symbols:
            symbols[-1]["value"] = line.split(maxsplit=2)[2]
        elif parts[0] == "WIRE":
            x1, y1, x2, y2 = map(int, parts[1:5])
            wires.append(((x1, y1), (x2, y2)))
        elif parts[0] == "FLAG":
            flags.append(((int(parts[1]), int(parts[2])), parts[3]))
    return symbols, wires, flags


def load_circuit(filename: str) -> dict:
    return json.loads((CIRCUITS_DIR / filename).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Library vs. .asy ground truth
# ---------------------------------------------------------------------------


class SymbolDefinitionTests(unittest.TestCase):
    def test_relative_pin_coordinates_match_asy_files(self) -> None:
        for kind, pins in ASY_PINS.items():
            with self.subTest(kind=kind):
                definition = COMPONENT_LIBRARY[kind]
                self.assertEqual({p.id for p in definition.pins}, set(pins))
                for pin in definition.pins:
                    self.assertEqual((pin.x, pin.y), pins[pin.id], f"{kind}.{pin.id}")

    def test_symbol_names(self) -> None:
        for kind, symbol in SYMBOLS.items():
            with self.subTest(kind=kind):
                self.assertEqual(COMPONENT_LIBRARY[kind].symbol, symbol)

    def test_symbol_names_are_not_duplicated_elsewhere(self) -> None:
        from app.services.pin_maps import PIN_COORDINATE_OFFSETS, SYMBOL_NAMES

        for kind, definition in COMPONENT_LIBRARY.items():
            self.assertEqual(SYMBOL_NAMES[kind], definition.symbol)
            self.assertEqual(
                PIN_COORDINATE_OFFSETS[kind],
                tuple((p.x, p.y) for p in definition.pins),
            )

    def test_every_pin_is_inside_declared_bounds(self) -> None:
        for kind, definition in COMPONENT_LIBRARY.items():
            min_x, min_y, max_x, max_y = definition.bounds
            for pin in definition.pins:
                with self.subTest(kind=kind, pin=pin.id):
                    self.assertTrue(min_x <= pin.x <= max_x)
                    self.assertTrue(min_y <= pin.y <= max_y)

    def test_transistor_pins_are_named_not_numbered(self) -> None:
        names = {p.name for p in COMPONENT_LIBRARY["bc547"].pins}
        self.assertEqual(names, {"Collector", "Base", "Emitter"})


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------


class ResistorOrientationTests(unittest.TestCase):
    """Resistor placed with its anchor at (64, 128), all eight orientations."""

    # orientation -> (pin 1, pin 2)
    EXPECTED = {
        "R0": ((80, 144), (80, 224)),
        "R90": ((48, 144), (-32, 144)),
        "R180": ((48, 112), (48, 32)),
        "R270": ((80, 112), (160, 112)),
        "M0": ((48, 144), (48, 224)),
        # M90 / M270: per KiCad importer table, unverified against real LTspice.
        "M90": ((80, 144), (160, 144)),
        "M180": ((80, 112), (80, 32)),
        "M270": ((48, 112), (-32, 112)),
    }

    def test_resistor_pins_at_every_orientation(self) -> None:
        definition = COMPONENT_LIBRARY["resistor"]
        for orientation, (pin1, pin2) in self.EXPECTED.items():
            with self.subTest(orientation=orientation):
                self.assertEqual(
                    PinResolver.resolve_pin(definition, "1", (64, 128), orientation),
                    pin1,
                )
                self.assertEqual(
                    PinResolver.resolve_pin(definition, "2", (64, 128), orientation),
                    pin2,
                )

    def test_resolver_matches_independent_transform_for_every_kind(self) -> None:
        anchor = (400, 304)
        for kind, pins in ASY_PINS.items():
            definition = COMPONENT_LIBRARY[kind]
            for orientation in ORIENTATIONS:
                for pin_id, (px, py) in pins.items():
                    with self.subTest(kind=kind, orientation=orientation, pin=pin_id):
                        ox, oy = reference_transform(px, py, orientation)
                        self.assertEqual(
                            PinResolver.resolve_pin(
                                definition, pin_id, anchor, orientation
                            ),
                            (anchor[0] + ox, anchor[1] + oy),
                        )

    def test_rotation_by_90_four_times_is_identity(self) -> None:
        for x, y in [(16, 16), (64, 0), (-112, 96)]:
            rx, ry = x, y
            for _ in range(4):
                rx, ry = PinResolver.transform_offset(rx, ry, 90, False)
            self.assertEqual((rx, ry), (x, y))

    def test_transistor_pins_at_known_anchor(self) -> None:
        definition = COMPONENT_LIBRARY["bc547"]
        anchor = (256, 160)
        self.assertEqual(PinResolver.resolve_pin(definition, "C", anchor), (320, 160))
        self.assertEqual(PinResolver.resolve_pin(definition, "B", anchor), (256, 208))
        self.assertEqual(PinResolver.resolve_pin(definition, "E", anchor), (320, 256))

    def test_led_pins_at_known_anchor(self) -> None:
        definition = COMPONENT_LIBRARY["led"]
        anchor = (128, 128)
        self.assertEqual(PinResolver.resolve_pin(definition, "A", anchor), (144, 128))
        self.assertEqual(PinResolver.resolve_pin(definition, "K", anchor), (144, 192))

    def test_capacitor_pins_at_known_anchor(self) -> None:
        definition = COMPONENT_LIBRARY["capacitor"]
        anchor = (128, 128)
        self.assertEqual(PinResolver.resolve_pin(definition, "1", anchor), (144, 128))
        self.assertEqual(PinResolver.resolve_pin(definition, "2", anchor), (144, 192))

    def test_ne555_pins_at_known_anchor(self) -> None:
        definition = COMPONENT_LIBRARY["ne555"]
        anchor = (512, 256)
        expected = {
            "1": (400, 160), "2": (400, 224), "3": (400, 288), "4": (400, 352),
            "5": (624, 352), "6": (624, 288), "7": (624, 224), "8": (624, 160),
        }
        self.assertEqual(PinResolver.resolve_all_pins(definition, anchor), expected)

    def test_orientation_string(self) -> None:
        self.assertEqual(PinResolver.orientation_string("R90"), "R90")
        self.assertEqual(PinResolver.orientation_string("R90", True), "M90")
        self.assertEqual(PinResolver.orientation_string("m180"), "M180")

    def test_unknown_orientation_raises(self) -> None:
        for bad in ["R45", "X0", "", "R", "90", "R360"]:
            with self.subTest(value=bad):
                with self.assertRaises(ValueError):
                    PinResolver.parse_orientation(bad)
        with self.assertRaises(ValueError):
            PinResolver.resolve_pin(COMPONENT_LIBRARY["resistor"], "1", (0, 0), "R45")

    def test_unknown_pin_raises(self) -> None:
        with self.assertRaises(ValueError):
            PinResolver.resolve_pin(COMPONENT_LIBRARY["resistor"], "9", (0, 0))

    def test_pin_facing_follows_rotation(self) -> None:
        definition = COMPONENT_LIBRARY["resistor"]

        def facing(orientation: str) -> PinOrientation:
            return PinResolver.resolve_pin_geometry(
                definition, "1", (0, 0), orientation
            ).facing

        self.assertIs(facing("R0"), PinOrientation.UP)
        self.assertIs(facing("R90"), PinOrientation.RIGHT)
        self.assertIs(facing("R180"), PinOrientation.DOWN)
        self.assertIs(facing("R270"), PinOrientation.LEFT)
        # Mirror swaps left and right only.
        self.assertIs(facing("M0"), PinOrientation.UP)
        self.assertIs(facing("M90"), PinOrientation.LEFT)
        self.assertIs(facing("M270"), PinOrientation.RIGHT)

    def test_facing_matches_pin_direction_from_body(self) -> None:
        """A pin must face away from the symbol body for every orientation."""
        definition = COMPONENT_LIBRARY["resistor"]
        away = {
            PinOrientation.UP: (0, -1),
            PinOrientation.DOWN: (0, 1),
            PinOrientation.LEFT: (-1, 0),
            PinOrientation.RIGHT: (1, 0),
        }
        for orientation in ORIENTATIONS:
            p1 = PinResolver.resolve_pin_geometry(definition, "1", (0, 0), orientation)
            p2 = PinResolver.resolve_pin_geometry(definition, "2", (0, 0), orientation)
            for near, far in ((p1, p2), (p2, p1)):
                with self.subTest(orientation=orientation, pin=near.pin_id):
                    dx = near.absolute[0] - far.absolute[0]
                    dy = near.absolute[1] - far.absolute[1]
                    # The pin faces the same way as (this pin - the other pin).
                    fx, fy = away[near.facing]
                    self.assertGreater(dx * fx + dy * fy, 0)

    def test_get_pin_coordinate_reads_the_placement_fields(self) -> None:
        component = {
            "type": "transistor",
            "_ltspice_anchor": (256, 160),
            "_ltspice_rotation": "R0",
            "_ltspice_mirror": False,
        }
        self.assertEqual(get_pin_coordinate(component, "B"), (256, 208))
        self.assertEqual(get_pin_coordinate(component, "base"), (256, 208))
        self.assertEqual(canonical_pin_id(component, "Collector"), "C")


# ---------------------------------------------------------------------------
# Grid
# ---------------------------------------------------------------------------


class GridTests(unittest.TestCase):
    def test_snap_basics(self) -> None:
        self.assertEqual(GridSystem.snap(0), 0)
        self.assertEqual(GridSystem.snap(7), 0)
        self.assertEqual(GridSystem.snap(9), 16)
        self.assertEqual(GridSystem.snap(-9), -16)
        self.assertEqual(GridSystem.snap_point((17, 31)), (16, 32))
        self.assertTrue(GridSystem.is_on_grid(48))
        self.assertFalse(GridSystem.is_on_grid(50))
        self.assertTrue(GridSystem.is_point_on_grid((32, -64)))
        self.assertFalse(GridSystem.is_point_on_grid((32, 5)))

    def test_snap_is_idempotent(self) -> None:
        for value in range(-200, 200, 7):
            once = GridSystem.snap(value)
            self.assertEqual(GridSystem.snap(once), once)

    def test_every_pin_of_every_kind_is_on_the_grid_at_every_orientation(self) -> None:
        anchor = GridSystem.snap_point((200, 300))
        for kind, definition in COMPONENT_LIBRARY.items():
            for orientation in ORIENTATIONS:
                for pin in definition.pins:
                    with self.subTest(kind=kind, orientation=orientation, pin=pin.id):
                        point = PinResolver.resolve_pin(
                            definition, pin.id, anchor, orientation
                        )
                        self.assertTrue(GridSystem.is_point_on_grid(point))
                        # Snapping a pin must not move it, so a wire that ends
                        # on the snapped value still ends exactly on the pin.
                        self.assertEqual(GridSystem.snap_point(point), point)

    def test_exporter_placement_is_on_grid(self) -> None:
        circuit = load_circuit("common_emitter_amplifier.json")
        for idx, comp in enumerate(circuit["components"]):
            _, layout = place_component(idx, comp)
            self.assertTrue(GridSystem.is_point_on_grid(layout["_ltspice_anchor"]))


# ---------------------------------------------------------------------------
# Validator unit tests (hand-built geometry)
# ---------------------------------------------------------------------------


class ValidatorTests(unittest.TestCase):
    @staticmethod
    def _codes(diagnostics, severity=None) -> set[str]:
        return {d.code for d in diagnostics if severity is None or d.severity == severity}

    def test_clean_net_has_no_diagnostics(self) -> None:
        net = NetGeometry(
            name="N1",
            pins=[PinPoint("R1", "2", (32, 64)), PinPoint("R2", "1", (96, 64))],
            segments=[WireSegment("N1", (32, 64), (96, 64))],
        )
        self.assertEqual(validate_net_geometry([net]), [])

    def test_dangling_stub_is_an_invalid_endpoint(self) -> None:
        net = NetGeometry(
            name="N1",
            pins=[PinPoint("R1", "2", (32, 64)), PinPoint("R2", "1", (96, 64))],
            segments=[
                WireSegment("N1", (32, 64), (96, 64)),
                WireSegment("N1", (48, 64), (48, 128)),  # stub into nowhere
            ],
        )
        diagnostics = validate_net_geometry([net])
        invalid = [d for d in diagnostics if d.code == "INVALID_WIRE_ENDPOINT"]
        self.assertTrue(invalid)
        self.assertEqual(invalid[0].severity, ERROR)
        self.assertEqual(invalid[0].actual, (48, 128))
        text = invalid[0].format()
        self.assertIn("Invalid wire endpoint", text)
        self.assertIn("N1", text)

    def test_wire_that_stops_short_of_a_pin(self) -> None:
        net = NetGeometry(
            name="N3",
            pins=[PinPoint("R1", "2", (32, 64)), PinPoint("R2", "1", (96, 64))],
            segments=[WireSegment("N3", (32, 64), (80, 64))],  # 16 short
        )
        codes = self._codes(validate_net_geometry([net]))
        self.assertIn("INVALID_WIRE_ENDPOINT", codes)
        self.assertIn("PIN_NOT_CONNECTED", codes)
        diagnostic = next(
            d for d in validate_net_geometry([net]) if d.code == "INVALID_WIRE_ENDPOINT"
        )
        self.assertEqual(diagnostic.component, "R2")
        self.assertEqual(diagnostic.pin, "1")
        self.assertEqual(diagnostic.expected, (96, 64))
        self.assertEqual(diagnostic.actual, (80, 64))

    def test_off_grid_vertex(self) -> None:
        net = NetGeometry(
            name="N1",
            pins=[PinPoint("R1", "2", (32, 64)), PinPoint("R2", "1", (96, 64))],
            segments=[
                WireSegment("N1", (32, 64), (50, 64)),
                WireSegment("N1", (50, 64), (96, 64)),
            ],
        )
        diagnostics = validate_net_geometry([net])
        off = [d for d in diagnostics if d.code == "OFF_GRID"]
        self.assertTrue(off)
        self.assertEqual(off[0].actual, (50, 64))
        self.assertEqual(off[0].expected, (48, 64))

    def test_off_grid_pin(self) -> None:
        net = NetGeometry(
            name="N1",
            pins=[PinPoint("R1", "2", (33, 64)), PinPoint("R2", "1", (96, 64))],
            segments=[WireSegment("N1", (33, 64), (96, 64))],
        )
        self.assertIn("OFF_GRID", self._codes(validate_net_geometry([net])))

    def test_net_split_in_two_pieces(self) -> None:
        net = NetGeometry(
            name="N1",
            pins=[PinPoint("R1", "2", (0, 0)), PinPoint("R2", "1", (64, 0))],
            segments=[
                WireSegment("N1", (0, 0), (16, 0)),
                WireSegment("N1", (48, 0), (64, 0)),
            ],
        )
        self.assertIn("NET_DISCONNECTED", self._codes(validate_net_geometry([net])))

    def test_crossing_different_nets_is_a_short_warning(self) -> None:
        a = NetGeometry(
            name="N1",
            pins=[PinPoint("R1", "1", (0, 64)), PinPoint("R2", "1", (128, 64))],
            segments=[WireSegment("N1", (0, 64), (128, 64))],
        )
        # N2's wire ends in the middle of N1's wire: a T-junction short.
        b = NetGeometry(
            name="N2",
            pins=[PinPoint("R3", "1", (64, 0)), PinPoint("R4", "1", (64, 64))],
            segments=[WireSegment("N2", (64, 0), (64, 64))],
        )
        diagnostics = validate_net_geometry([a, b])
        shorts = [d for d in diagnostics if d.code == "NET_SHORT"]
        self.assertTrue(shorts)
        self.assertTrue(all(d.severity == WARNING for d in shorts))

    def test_wire_passing_over_another_nets_pin(self) -> None:
        a = NetGeometry(
            name="N1",
            pins=[PinPoint("R1", "1", (0, 64)), PinPoint("R2", "1", (128, 64))],
            segments=[WireSegment("N1", (0, 64), (128, 64))],
        )
        b = NetGeometry(
            name="N2",
            pins=[PinPoint("R3", "1", (64, 64)), PinPoint("R4", "1", (64, 128))],
            segments=[WireSegment("N2", (64, 64), (64, 128))],
        )
        self.assertIn("WIRE_CROSSES_PIN", self._codes(validate_net_geometry([a, b])))

    def test_two_nets_on_the_same_pin_coordinate_is_an_error(self) -> None:
        a = NetGeometry(name="N1", pins=[PinPoint("R1", "1", (16, 16))])
        b = NetGeometry(name="N2", pins=[PinPoint("R2", "1", (16, 16))])
        diagnostics = validate_net_geometry([a, b])
        collision = [d for d in diagnostics if d.code == "PIN_COLLISION"]
        self.assertTrue(collision)
        self.assertEqual(collision[0].severity, ERROR)


class Phase7ValidatorTests(unittest.TestCase):
    def test_orientation_rejects_diagonal_and_zero_length(self) -> None:
        self.assertEqual(WireSegment("N", (0, 0), (16, 0)).orientation, "horizontal")
        self.assertEqual(WireSegment("N", (0, 0), (0, 16)).orientation, "vertical")
        for end, code in [((16, 16), "NON_ORTHOGONAL_WIRE"), ((0, 0), "ZERO_LENGTH_WIRE")]:
            segment = WireSegment("N", (0, 0), end)
            with self.subTest(end=end):
                with self.assertRaises(ValueError):
                    _ = segment.orientation
                self.assertIn(code, {d.code for d in validate_net_geometry([NetGeometry("N", segments=[segment])])})

    def test_foreign_wire_shared_endpoint_is_short_without_pin_there(self) -> None:
        a = NetGeometry("A", segments=[WireSegment("A", (0, 0), (64, 0))])
        b = NetGeometry("B", segments=[WireSegment("B", (64, 0), (64, 64))])
        shorts = [d for d in validate_net_geometry([a, b]) if d.code == "NET_SHORT"]
        self.assertTrue(shorts)
        self.assertTrue(all(d.severity == WARNING for d in shorts))

    def test_flag_on_foreign_wire_is_a_short(self) -> None:
        a = NetGeometry("A", segments=[WireSegment("A", (0, 0), (128, 0))])
        b = NetGeometry("B", flags=[(64, 0)])
        diagnostics = validate_net_geometry([a, b])
        self.assertIn("NET_SHORT", {d.code for d in diagnostics})
        self.assertIn("FLAG_NOT_CONNECTED", {d.code for d in diagnostics})

    def test_unwired_reserved_pin_cannot_be_crossed_or_flagged(self) -> None:
        reserved = PinPoint("R99", "1", (64, 0))
        for net in [NetGeometry("A", segments=[WireSegment("A", (0, 0), (128, 0))]),
                    NetGeometry("A", flags=[(64, 0)])]:
            with self.subTest(net=net):
                diagnostics = validate_net_geometry([net], reserved_pins=[reserved])
                self.assertTrue({"WIRE_CROSSES_PIN", "PIN_COLLISION"} & {d.code for d in diagnostics})

    def test_closed_orphan_island_is_not_mistaken_for_connected_net(self) -> None:
        net = NetGeometry("N", pins=[PinPoint("R1", "1", (0, 0)), PinPoint("R2", "1", (64, 0))],
                          segments=[WireSegment("N", (0, 0), (64, 0)),
                                    WireSegment("N", (128, 0), (160, 0)),
                                    WireSegment("N", (160, 0), (160, 32)),
                                    WireSegment("N", (160, 32), (128, 32)),
                                    WireSegment("N", (128, 32), (128, 0))])
        codes = {d.code for d in validate_net_geometry([net])}
        self.assertTrue({"NET_DISCONNECTED", "ORPHAN_WIRE_ISLAND"}.issubset(codes))

    def test_unsplit_interior_perpendicular_crossing_is_nonconductive(self) -> None:
        a = NetGeometry("A", pins=[PinPoint("R1", "1", (0, 64)), PinPoint("R2", "1", (128, 64))],
                        segments=[WireSegment("A", (0, 64), (128, 64))])
        b = NetGeometry("B", pins=[PinPoint("R3", "1", (64, 0)), PinPoint("R4", "1", (64, 128))],
                        segments=[WireSegment("B", (64, 0), (64, 128))])
        self.assertEqual(validate_net_geometry([a, b]), [])
        # Splitting one wire creates a real conductive endpoint/interior contact.
        a.segments = [WireSegment("A", (0, 64), (64, 64)), WireSegment("A", (64, 64), (128, 64))]
        self.assertIn("NET_SHORT", {d.code for d in validate_net_geometry([a, b])})

    def test_unsplit_interior_crossing_does_not_repair_disconnected_same_net(self) -> None:
        net = NetGeometry("N", pins=[PinPoint("R1", "1", (0, 64)), PinPoint("R2", "1", (128, 64)),
                                     PinPoint("R3", "1", (64, 0)), PinPoint("R4", "1", (64, 128))],
                          segments=[WireSegment("N", (0, 64), (128, 64)),
                                    WireSegment("N", (64, 0), (64, 128))])
        self.assertIn("NET_DISCONNECTED", {d.code for d in validate_net_geometry([net])})
        net.segments = [WireSegment("N", (0, 64), (64, 64)),
                        WireSegment("N", (64, 64), (128, 64)), net.segments[1]]
        self.assertEqual(validate_net_geometry([net]), [])

    def test_flag_at_own_wire_interior_attaches_but_floating_flag_errors(self) -> None:
        net = NetGeometry("A", pins=[PinPoint("R1", "1", (0, 0)), PinPoint("R2", "1", (128, 0))],
                          flags=[(64, 0)], segments=[WireSegment("A", (0, 0), (128, 0))])
        self.assertEqual(validate_net_geometry([net]), [])
        net.flags = [(64, 16)]
        self.assertIn("FLAG_NOT_CONNECTED", {d.code for d in validate_net_geometry([net])})


# ---------------------------------------------------------------------------
# End-to-end export
# ---------------------------------------------------------------------------


def pin_world_positions(symbols: list[dict]) -> dict[tuple[str, str], tuple[int, int]]:
    """``{(inst, pin_id): (x, y)}`` computed only from .asc text + ASY_PINS."""
    positions: dict[tuple[str, str], tuple[int, int]] = {}
    for sym in symbols:
        kind = KIND_BY_SYMBOL.get(sym["symbol"])
        if kind is None:
            continue
        for pin_id, (px, py) in ASY_PINS[kind].items():
            ox, oy = reference_transform(px, py, sym["orient"])
            positions[(sym["inst"], pin_id)] = (sym["x"] + ox, sym["y"] + oy)
    return positions


# JSON pin spelling -> .asy pin id, per symbol (test-local; not from pin_maps).
JSON_PIN_TO_ASY = {
    "npn": {"C": "C", "B": "B", "E": "E"},
    "res": {"1": "1", "2": "2"},
    "cap": {"1": "1", "2": "2"},
}


class EndToEndExportTests(unittest.TestCase):
    def test_common_emitter_every_json_pin_lands_on_a_wire_endpoint(self) -> None:
        circuit = load_circuit("common_emitter_amplifier.json")
        asc = generate_asc(circuit)
        symbols, wires, _ = parse_asc(asc)
        positions = pin_world_positions(symbols)
        endpoints = {point for wire in wires for point in wire}

        self.assertEqual(
            sorted(s["inst"] for s in symbols), ["C1", "C2", "Q1", "R1", "R2", "R3"]
        )

        checked = 0
        for wire in circuit["wires"]:
            for key in ("from", "to"):
                node = wire[key]
                if "." not in node:
                    continue  # VCC / GND / OUT are flags, checked below
                inst, pin = node.split(".", 1)
                sym = next(s for s in symbols if s["inst"] == inst)
                pin_id = JSON_PIN_TO_ASY[sym["symbol"]][pin]
                with self.subTest(node=node):
                    self.assertIn(
                        positions[(inst, pin_id)],
                        endpoints,
                        f"{node} is not on any wire endpoint",
                    )
                checked += 1
        # 10 wires; 15 component-pin references (13 distinct pins: Q1.B and
        # Q1.C are each referenced twice).
        self.assertEqual(checked, 15)

    def test_common_emitter_symbol_lines_match_phase75_placement(self) -> None:
        filename = "common_emitter_amplifier.json"
        symbols, _, _ = parse_asc(generate_asc(load_circuit(filename)))
        self.assertEqual(
            sorted((s["inst"], s["symbol"], s["x"], s["y"], s["orient"]) for s in symbols),
            sorted(record[:5] for record in PHASE75_SYMBOL_RECORDS[filename]),
        )

    def test_common_emitter_has_no_error_diagnostics(self) -> None:
        _, diagnostics = generate_asc_with_diagnostics(
            load_circuit("common_emitter_amplifier.json")
        )
        errors = [d for d in diagnostics if d.severity == ERROR]
        self.assertEqual(errors, [], "\n\n".join(d.format() for d in errors))

    def test_flags_sit_on_a_wire_endpoint(self) -> None:
        for filename in ["common_emitter_amplifier.json", "rc_low_pass_filter.json"]:
            with self.subTest(circuit=filename):
                asc = generate_asc(load_circuit(filename))
                _, wires, flags = parse_asc(asc)
                endpoints = {point for wire in wires for point in wire}
                self.assertTrue(flags)
                for point, name in flags:
                    self.assertIn(point, endpoints, f"FLAG {name} not on a wire")

    def test_every_coordinate_in_the_asc_is_on_the_grid(self) -> None:
        for path in sorted(CIRCUITS_DIR.glob("*.json")):
            with self.subTest(circuit=path.name):
                symbols, wires, flags = parse_asc(generate_asc(load_circuit(path.name)))
                points = [(s["x"], s["y"]) for s in symbols]
                points += [p for wire in wires for p in wire]
                points += [p for p, _ in flags]
                for point in points:
                    self.assertTrue(GridSystem.is_point_on_grid(point), point)

    def test_rc_filters_pins_land_on_wire_endpoints(self) -> None:
        for filename in ["rc_low_pass_filter.json", "rc_high_pass_filter.json"]:
            with self.subTest(circuit=filename):
                circuit = load_circuit(filename)
                symbols, wires, _ = parse_asc(generate_asc(circuit))
                positions = pin_world_positions(symbols)
                endpoints = {point for wire in wires for point in wire}
                referenced = {
                    node
                    for wire in circuit["wires"]
                    for node in (wire["from"], wire["to"])
                    if "." in node
                }
                self.assertTrue(referenced)
                for node in referenced:
                    inst, pin = node.split(".", 1)
                    sym = next(s for s in symbols if s["inst"] == inst)
                    pin_id = JSON_PIN_TO_ASY[sym["symbol"]][pin]
                    self.assertIn(positions[(inst, pin_id)], endpoints, node)

    def test_all_bundled_circuits_have_structurally_valid_wires(self) -> None:
        blocking = {"INVALID_WIRE_ENDPOINT", "PIN_NOT_CONNECTED", "OFF_GRID"}
        for path in sorted(CIRCUITS_DIR.glob("*.json")):
            with self.subTest(circuit=path.name):
                _, diagnostics = generate_asc_with_diagnostics(load_circuit(path.name))
                bad = [d for d in diagnostics if d.code in blocking]
                self.assertEqual(bad, [], "\n\n".join(d.format() for d in bad))
                errors = [d for d in diagnostics if d.severity == ERROR]
                self.assertEqual(errors, [])

    def test_exported_pin_positions_match_debugger_numbers(self) -> None:
        """Shared bulk placement agrees with frozen placement + stock ASY offsets."""
        for filename, records in PHASE75_SYMBOL_RECORDS.items():
            with self.subTest(circuit=filename):
                circuit = load_circuit(filename)
                layouts = place_components(circuit["components"], build_connectivity(circuit))
                symbols, _, _ = parse_asc(generate_asc(circuit))
                frozen_symbols = [
                    {"inst": ref, "symbol": symbol, "x": x, "y": y, "orient": orient}
                    for ref, symbol, x, y, orient, _ in records
                ]
                # Neither expected placement nor pin IDs/offsets come from
                # pin_maps, the layout algorithm, or today's exported symbols.
                independent = pin_world_positions(frozen_symbols)
                self.assertEqual(pin_world_positions(symbols), independent)
                for (ref, pin_id), point in independent.items():
                    with self.subTest(component=ref, pin=pin_id):
                        self.assertEqual(get_pin_coordinate(layouts[ref], pin_id), point)

    def test_strict_mode_accepts_phase7_common_emitter_routing(self) -> None:
        """Phase7 replaces the centroid routes that shorted five nets on ground.

        The old ASC remains the negative fixture in tests/artifacts/phase_6_5;
        its real LTspice test must continue reporting that known short. The
        current router must pass BOTH default and strict collision gates.
        """
        circuit = load_circuit("common_emitter_amplifier.json")
        for strict in (False, True):
            with self.subTest(strict=strict):
                asc, diagnostics = generate_asc_with_diagnostics(circuit, strict=strict)
                self.assertTrue(asc)
                self.assertEqual([d for d in diagnostics if d.severity == ERROR], [])
                self.assertFalse(any(d.code in {"NET_SHORT", "WIRE_CROSSES_PIN"} for d in diagnostics))
                self.assertEqual(generate_asc(circuit, strict=strict), asc)

    def test_non_strict_export_returns_safe_text(self) -> None:
        asc = generate_asc(load_circuit("common_emitter_amplifier.json"))
        self.assertTrue(asc.startswith("Version 4\nSHEET 1 "))

    def test_export_is_deterministic(self) -> None:
        circuit = load_circuit("common_emitter_amplifier.json")
        self.assertEqual(generate_asc(circuit), generate_asc(circuit))


# ---------------------------------------------------------------------------
# Debugger
# ---------------------------------------------------------------------------


class DebuggerTests(unittest.TestCase):
    def test_geometry_listing_for_transistor(self) -> None:
        comp = {"reference": "Q1", "type": "transistor", "value": "BC547"}
        _, layout = place_component(0, comp)
        text = ExporterDebugger.format_geometry(layout)
        anchor = layout["_ltspice_anchor"]

        self.assertIn("Q1", text)
        self.assertIn("npn", text)
        self.assertIn(f"Position:   ({anchor[0]}, {anchor[1]})", text)
        self.assertIn("Rotation:   R0", text)
        self.assertIn("Mirror:     False", text)
        for name in ("Collector (C)", "Base (B)", "Emitter (E)"):
            self.assertIn(name, text)
        self.assertIn("relative = (64, 0)", text)
        self.assertIn("relative = (0, 48)", text)
        self.assertIn(f"absolute = ({anchor[0]}, {anchor[1] + 48})", text)

    def test_geometry_listing_for_unplaced_component(self) -> None:
        text = ExporterDebugger.format_geometry({"reference": "R9", "type": "resistor"})
        self.assertIn("not been placed", text)

    def test_geometry_listing_for_unknown_kind(self) -> None:
        text = ExporterDebugger.format_geometry({"reference": "X1", "type": "flux"})
        self.assertIn("no symbol definition", text)

    def test_circuit_geometry_lists_every_component(self) -> None:
        circuit = load_circuit("common_emitter_amplifier.json")
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            text = ExporterDebugger.print_circuit_geometry(circuit)
        self.assertEqual(buffer.getvalue().strip(), text.strip())
        for ref in ("Q1", "R1", "R2", "R3", "C1", "C2"):
            self.assertRegex(text, rf"(?m)^{ref}$")

    def test_connections_unify_pin_aliases(self) -> None:
        circuit = {
            "components": [
                {"reference": "Q1", "type": "transistor", "value": "BC547", "id": "Q1"},
                {"reference": "R1", "type": "resistor", "value": "1k", "id": "R1"},
                {"reference": "R2", "type": "resistor", "value": "1k", "id": "R2"},
            ],
            "wires": [
                {"from": "R1.2", "to": "Q1.B"},
                {"from": "Q1.base", "to": "R2.1"},
            ],
        }
        text = ExporterDebugger.format_connections(circuit)
        self.assertEqual(text.count("Net N"), 1)
        self.assertRegex(text, re.compile(r"Q1\.", re.M))


if __name__ == "__main__":
    unittest.main()
