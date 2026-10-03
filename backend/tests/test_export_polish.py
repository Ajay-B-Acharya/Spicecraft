"""Final ASC serialization regressions independent of router search heuristics."""
from __future__ import annotations

from collections import Counter
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services.asc_validation import ERROR, AscExportError, WireSegment
from app.services.ltspice_exporter import generate_asc, generate_asc_with_routing
from app.services.routing import route_nets
from test_pin_geometry import parse_asc, pin_world_positions

SOURCES = [*sorted((BACKEND / "circuits").glob("*.json")),
           *sorted((BACKEND / "tests/fixtures/routing").glob("*.json"))]


def coverage(wires):
    """Unit intervals independently identify the exact occupied wire paths."""
    result = set()
    for start, end in wires:
        (x1, y1), (x2, y2) = sorted((start, end))
        if y1 == y2:
            result.update(("h", y1, x) for x in range(x1, x2))
        elif x1 == x2:
            result.update(("v", x1, y) for y in range(y1, y2))
        else:
            raise AssertionError("Non-Manhattan serialized wire")
    return result


class ExportPolishTests(unittest.TestCase):
    def test_seven_exports_preserve_frozen_paths_pins_symbols_values_and_flags(self):
        self.assertEqual(len(SOURCES), 7)
        for path in SOURCES:
            with self.subTest(circuit=path.stem):
                source = json.loads(path.read_text(encoding="utf-8"))
                snapshot = copy.deepcopy(source)
                asc, diagnostics, routed = generate_asc_with_routing(source, strict=True)
                self.assertFalse([d for d in diagnostics if d.severity == ERROR], diagnostics)
                baseline = (BACKEND / "tests/artifacts/phase_8/before" / f"{path.stem}.asc").read_text(encoding="utf-8")
                before_symbols, before_wires, before_flags = parse_asc(baseline)
                symbols, wires, flags = parse_asc(asc)
                self.assertEqual(sorted(symbols, key=lambda s: s["inst"]),
                                 sorted(before_symbols, key=lambda s: s["inst"]))
                self.assertEqual(pin_world_positions(symbols), pin_world_positions(before_symbols))
                self.assertEqual(coverage(wires), coverage(before_wires))
                self.assertEqual(set(flags), set(before_flags))
                self.assertEqual(len(wires), len(set(tuple(sorted(wire)) for wire in wires)))
                self.assertTrue(all(a != b for a, b in wires))
                self.assertLessEqual(len(wires), len(before_wires))
                self.assertEqual(source, snapshot)
                self.assertEqual(asc, generate_asc(source, strict=True))
                self.assertEqual(routed.metrics["segments"], len(wires))

    def test_records_are_grouped_and_symbol_attributes_remain_scoped(self):
        source = json.loads((BACKEND / "circuits/common_emitter_amplifier.json").read_text())
        asc = generate_asc(source)
        lines = asc.splitlines()
        self.assertEqual(lines[0], "Version 4")
        self.assertTrue(lines[1].startswith("SHEET 1 "))
        ranks = {"SYMBOL": 0, "WINDOW": 0, "SYMATTR": 0, "WIRE": 1, "FLAG": 2, "TEXT": 3}
        self.assertEqual([ranks[line.split()[0]] for line in lines[2:]],
                         sorted(ranks[line.split()[0]] for line in lines[2:]))
        self.assertEqual([s["inst"] for s in parse_asc(asc)[0]], ["C1", "C2", "Q1", "R1", "R2", "R3"])
        current = []
        for line in lines[2:] + ["SYMBOL sentinel"]:
            if line.startswith("SYMBOL"):
                if current:
                    keys = [record.split()[1] for record in current if record.startswith("SYMATTR")]
                    windows = [record.split()[1] for record in current if record.startswith("WINDOW")]
                    self.assertEqual(keys, ["InstName", "Value"])
                    self.assertEqual(len(windows), len(set(windows)))
                current = []
            elif line.startswith(("SYMATTR", "WINDOW")):
                current.append(line)

    def test_duplicate_valid_route_records_are_removed_without_rerouting(self):
        source = json.loads((BACKEND / "circuits/common_emitter_amplifier.json").read_text())
        def duplicate(model, layouts):
            routed = route_nets(model, layouts)
            for net in routed.net_geometries:
                net.segments += [WireSegment(s.net, s.end, s.start) for s in list(net.segments)]
                net.flags *= 2
            routed.flags *= 2
            return routed
        with patch("app.services.ltspice_exporter.route_nets", side_effect=duplicate) as mocked:
            asc, diagnostics, routed = generate_asc_with_routing(source)
        mocked.assert_called_once()
        self.assertTrue(asc, diagnostics)
        self.assertFalse([d for d in diagnostics if d.severity == ERROR])
        self.assertEqual(asc, generate_asc(source))
        self.assertEqual(len(routed.flags), len(set(routed.flags)))

    def test_case_insensitive_reference_collision_is_blocked_before_routing(self):
        source = {"name": "Ambiguous refs", "components": [
            {"reference": "R1", "type": "resistor", "value": "1k"},
            {"reference": "r1", "type": "resistor", "value": "2k"}], "wires": []}
        with patch("app.services.ltspice_exporter.route_nets") as mocked:
            asc, diagnostics, _ = generate_asc_with_routing(source)
        self.assertFalse(asc)
        mocked.assert_not_called()
        self.assertIn("INSTANCE_NAME_COLLISION", {d.code for d in diagnostics})
        self.assertTrue(all(d.circuit == "Ambiguous refs" for d in diagnostics))

    def test_record_injection_in_value_or_reference_is_blocked(self):
        for field, value in (("value", "1k\nWIRE 0 0 16 0"), ("reference", "R1 R2")):
            with self.subTest(field=field):
                component = {"reference": "R1", "type": "resistor", "value": "1k", field: value}
                with self.assertRaises(AscExportError):
                    generate_asc({"components": [component]})

    def test_numeric_zero_and_source_value_spelling_are_preserved(self):
        for value in (0, "100k", "10k", "1k", "10uF", "100uF", "10µF"):
            with self.subTest(value=value):
                asc = generate_asc({"components": [{"reference": "R1", "type": "resistor", "value": value}]})
                self.assertIn(f"SYMATTR Value {value}\n", asc)

    def test_invalid_endpoint_reports_circuit_net_component_pin_and_coordinates(self):
        source = json.loads((BACKEND / "circuits/common_emitter_amplifier.json").read_text())
        def broken(model, layouts):
            routed = route_nets(model, layouts)
            net = next(n for n in routed.net_geometries if n.name == "VOUT")
            net.segments = [WireSegment(net.name, (736, 304), (784, 304))]
            return routed
        with patch("app.services.ltspice_exporter.route_nets", side_effect=broken):
            asc, diagnostics, _ = generate_asc_with_routing(source)
        self.assertFalse(asc)
        problem = next(d for d in diagnostics if d.code == "INVALID_WIRE_ENDPOINT")
        self.assertEqual((problem.net, problem.component, problem.pin), ("VOUT", "C2", "2"))
        for label in ("Circuit:", "Net:", "Component:", "Pin:", "Expected:", "Actual:"):
            self.assertIn(label, problem.format())


if __name__ == "__main__":
    unittest.main()
