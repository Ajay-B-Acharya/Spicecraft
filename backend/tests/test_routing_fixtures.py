"""Phase 7 regressions for genuine divider and bridge circuits, not templates.

Expected partitions are explicit frozen data, never inferred from source wires
or routing output. Serialized pin coordinates use test_pin_geometry's independent
stock ASY oracle; electrical integration invokes actual LTspice without mocks.
"""
from __future__ import annotations

from collections import Counter
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import MappingProxyType
import unittest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.asc_validation import ERROR
from app.services.connectivity import build_connectivity, validate_connectivity
from app.services.ltspice_exporter import generate_asc, generate_asc_with_routing
from test_pin_geometry import parse_asc, pin_world_positions
from tools.verify_ltspice import (
    compare_partitions,
    discover_ltspice_executable,
    discover_symbol_roots,
    parse_netlist,
    read_ltspice_text,
    run_ltspice_netlist,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "routing"

# Explicit requested topologies. GND becomes the LTspice node/FLAG "0".
EXPECTED_PARTITIONS = MappingProxyType({
    "voltage_divider.json": MappingProxyType({
        "VIN": frozenset({"R1.1"}),
        "VOUT": frozenset({"R1.2", "R2.1"}),
        "0": frozenset({"R2.2"}),
    }),
    "bridge_rectifier.json": MappingProxyType({
        "AC+": frozenset({"D1.1", "D3.2"}),
        "AC-": frozenset({"D2.1", "D4.2"}),
        "OUT+": frozenset({"D1.2", "D2.2", "R1.1"}),
        "0": frozenset({"D3.1", "D4.1", "R1.2"}),
    }),
})
EXPECTED_SYMBOLS = MappingProxyType({
    "voltage_divider.json": MappingProxyType({"R1": "res", "R2": "res"}),
    "bridge_rectifier.json": MappingProxyType({
        "D1": "diode", "D2": "diode", "D3": "diode", "D4": "diode", "R1": "res",
    }),
})


def load_fixture(filename: str) -> dict:
    return json.loads((FIXTURES_DIR / filename).read_text(encoding="utf-8"))


def asc_pin_nodes(symbols, wires, flags) -> dict[str, str]:
    """Independent ASC connectivity using only parsed text and the ASY oracle.

    Pins, flags and wire endpoints are conductive vertices, including when on a
    wire interior. An unsplit interior/interior X is not a vertex and does not
    join wires. This portable check supplements, never replaces, real LTspice.
    """
    pins = pin_world_positions(symbols)
    points = set(pins.values()) | {point for wire in wires for point in wire}
    points.update(point for point, _ in flags)
    parent = {point: point for point in points}

    def root(point):
        while parent[point] != point:
            point = parent[point]
        return point

    def join(left, right):
        parent[root(right)] = root(left)

    for start, end in wires:
        for point in points:
            x, y = point
            if ((start[0] == end[0] == x and min(start[1], end[1]) <= y <= max(start[1], end[1]))
                    or (start[1] == end[1] == y and min(start[0], end[0]) <= x <= max(start[0], end[0]))):
                join(start, point)
    labels = {}
    for point, name in flags:
        key = name.casefold()
        if key in labels:
            join(labels[key], point)
        else:
            labels[key] = point
    return {f"{ref}.{pin}": str(root(point)) for (ref, pin), point in pins.items()}


class RoutingFixtureTests(unittest.TestCase):
    def assert_source_partition(self, filename: str) -> None:
        source = load_fixture(filename)
        expected = EXPECTED_PARTITIONS[filename]
        model = build_connectivity(source)
        self.assertEqual(model.diagnostics, [])
        self.assertEqual(validate_connectivity(model), [])
        self.assertEqual({net.name: frozenset(pin.key for pin in net.pins)
                          for net in model.nets}, expected)
        self.assertEqual({group.name: frozenset(pin.key for pin in group.pins)
                          for group in model.source_groups}, expected)
        self.assertEqual(set(model.pin_refs), set().union(*expected.values()))
        self.assertEqual(model.unconnected_pins(), [])
        self.assertEqual({comp["reference"]: comp["type"] for comp in source["components"]},
                         {ref: "diode" if symbol == "diode" else "resistor"
                          for ref, symbol in EXPECTED_SYMBOLS[filename].items()})

    def assert_input_immutable(self, filename: str) -> None:
        source = load_fixture(filename)
        before = copy.deepcopy(source)
        build_connectivity(source)
        self.assertEqual(source, before)
        for strict in (False, True):
            with self.subTest(strict=strict):
                asc, diagnostics, routed = generate_asc_with_routing(source, strict=strict)
                self.assertEqual(source, before)
                self.assertEqual([d for d in diagnostics if d.severity == ERROR], [])
                self.assertTrue(asc)
                self.assertIsNotNone(routed)
                self.assertTrue(routed.ok)

    def assert_deterministic_asc(self, filename: str) -> None:
        source = load_fixture(filename)
        first = generate_asc(source, strict=True)
        self.assertTrue(first.startswith("Version 4\nSHEET 1 "))
        self.assertEqual(generate_asc(source, strict=True), first)
        self.assertEqual(generate_asc(load_fixture(filename), strict=False), first)

    def assert_output_partition_and_geometry(self, filename: str) -> None:
        source = load_fixture(filename)
        expected = EXPECTED_PARTITIONS[filename]
        model = build_connectivity(source)
        asc, diagnostics, routed = generate_asc_with_routing(source, strict=True)
        self.assertEqual([d for d in diagnostics if d.severity == ERROR], [], diagnostics)
        self.assertTrue(asc)
        self.assertIsNotNone(routed)
        self.assertTrue(routed.ok)
        self.assertEqual(validate_connectivity(model, routed.net_geometries), [])
        self.assertEqual({net.name: frozenset(f"{pin.component}.{pin.pin}" for pin in net.pins)
                          for net in routed.net_geometries}, expected)
        self.assertEqual(len(routed.net_geometries), len(expected))

        symbols, wires, flags = parse_asc(asc)
        self.assertEqual(Counter((s["inst"], s["symbol"]) for s in symbols),
                         Counter(EXPECTED_SYMBOLS[filename].items()))
        independent_pins = pin_world_positions(symbols)
        self.assertEqual({f"{ref}.{pin}" for ref, pin in independent_pins},
                         set().union(*expected.values()))
        self.assertEqual(Counter(f"{pin.component}.{pin.pin}"
                                 for net in routed.net_geometries for pin in net.pins),
                         Counter(pin for pins in expected.values() for pin in pins))
        for net in routed.net_geometries:
            for pin in net.pins:
                self.assertEqual(pin.point, independent_pins[(pin.component, pin.pin)])
            for segment in net.segments:
                self.assertEqual(segment.net, net.name)

        self.assertEqual(Counter(wires), Counter((s.start, s.end)
                         for net in routed.net_geometries for s in net.segments))
        self.assertEqual(Counter(flags), Counter((point, net.name)
                         for net in routed.net_geometries for point in net.flags))
        self.assertEqual(Counter(flags), Counter((flag.point, flag.name) for flag in routed.flags))
        self.assertEqual(Counter(name for _, name in flags), Counter(expected.keys()))
        endpoints = {point for wire in wires for point in wire}
        for point in independent_pins.values():
            self.assertIn(point, endpoints)
        for start, end in wires:
            self.assertNotEqual(start, end)
            self.assertTrue(start[0] == end[0] or start[1] == end[1], (start, end))
        points = [(s["x"], s["y"]) for s in symbols]
        points += list(independent_pins.values()) + list(endpoints) + [point for point, _ in flags]
        for point in points:
            self.assertTrue(all(coordinate % 16 == 0 for coordinate in point), point)

        report = compare_partitions(expected, asc_pin_nodes(symbols, wires, flags))
        self.assertTrue(report.ok, report.to_dict())

    def test_voltage_divider_source_partition(self) -> None:
        self.assert_source_partition("voltage_divider.json")

    def test_bridge_rectifier_source_partition(self) -> None:
        self.assert_source_partition("bridge_rectifier.json")

    def test_voltage_divider_input_immutability(self) -> None:
        self.assert_input_immutable("voltage_divider.json")

    def test_bridge_rectifier_input_immutability(self) -> None:
        self.assert_input_immutable("bridge_rectifier.json")

    def test_voltage_divider_deterministic_asc(self) -> None:
        self.assert_deterministic_asc("voltage_divider.json")

    def test_bridge_rectifier_deterministic_asc(self) -> None:
        self.assert_deterministic_asc("bridge_rectifier.json")

    def test_voltage_divider_output_partition_and_geometry(self) -> None:
        self.assert_output_partition_and_geometry("voltage_divider.json")

    def test_bridge_rectifier_output_partition_and_geometry(self) -> None:
        self.assert_output_partition_and_geometry("bridge_rectifier.json")


class RealLtspiceRoutingFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.executable = discover_ltspice_executable()
        if cls.executable is None:
            raise unittest.SkipTest("LTspice unavailable; set LTSPICE_EXECUTABLE for electrical integration")
        cls.symbol_roots = discover_symbol_roots(cls.executable)
        if not cls.symbol_roots:
            raise unittest.SkipTest("Stock LTspice symbol library unavailable")

    def assert_real_partition(self, filename: str) -> None:
        source = load_fixture(filename)
        before = copy.deepcopy(source)
        expected = EXPECTED_PARTITIONS[filename]
        asc, diagnostics, routed = generate_asc_with_routing(source, strict=True)
        self.assertEqual(source, before)
        self.assertEqual([d for d in diagnostics if d.severity == ERROR], [], diagnostics)
        self.assertTrue(asc)
        self.assertIsNotNone(routed)
        self.assertTrue(routed.ok)
        with tempfile.TemporaryDirectory(prefix="spicecraft-routing-fixtures-") as directory:
            root = Path(directory)
            input_path = root / f"{Path(filename).stem}.asc"
            input_path.write_text(asc, encoding="utf-8")
            output = run_ltspice_netlist(input_path, root / "outputs",
                                        executable=self.executable, timeout=30)
            text = read_ltspice_text(output)
            actual = parse_netlist(asc, text, symbol_roots=self.symbol_roots)
        report = compare_partitions(expected, actual)
        self.assertTrue(report.ok, f"{report.to_dict()}\n{text}")
        self.assertEqual(len(actual), sum(len(pins) for pins in expected.values()), text)
        for name, pins in expected.items():
            for pin in pins:
                self.assertEqual(actual[pin].casefold(), name.casefold(), text)
        print(f"LTspice routing fixture {filename}: {len(actual)} pins, "
              f"{len(expected)} nets, no shorts/opens")

    def test_voltage_divider_actual_ltspice_partition(self) -> None:
        self.assert_real_partition("voltage_divider.json")

    def test_bridge_rectifier_actual_ltspice_partition(self) -> None:
        self.assert_real_partition("bridge_rectifier.json")


if __name__ == "__main__":
    unittest.main()
