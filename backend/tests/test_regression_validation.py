"""Dependency-free Phase 9 adversarial checks; only small hand-built fixtures."""
from __future__ import annotations

import copy
from itertools import permutations
import json
from pathlib import Path
import subprocess
import sys
import unittest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.asc_validation import ExportDiagnostic, NetGeometry, PinPoint, WireSegment
from app.services.connectivity import build_connectivity
from app.services.pin_maps import COMPONENT_LIBRARY, PinResolver
from app.services.regression_validation import (
    canonical_topology, compare_metrics, compare_topology, parse_asc_semantics,
    validate_routing,
)
from app.services.routing.models import RoutedFlag, RoutingOptions, RoutingResult, SafeCrossing


def codes(issues):
    return {issue["code"] for issue in issues}


def symbol(reference="R1", name="res", x=0, y=0, orientation="R0"):
    return f"SYMBOL {name} {x} {y} {orientation}\nSYMATTR InstName {reference}\n"


def empty_model():
    return build_connectivity({"components": [], "wires": []})


def wire_net(name, start, end):
    return NetGeometry(name, flags=[start, end], segments=[WireSegment(name, start, end)])


def lead_fixture(*, reverse=False):
    model = build_connectivity({"components": [{"reference": "R1", "type": "resistor"}],
                                "wires": [{"from": "R1.1", "to": "signal"}]})
    layouts = {"R1": {"type": "resistor", "_ltspice_anchor": (0, 0), "_ltspice_rotation": "R0"}}
    name = model.nets[0].name
    start, end = (16, 16), (16, -96)
    if reverse:
        start, end = end, start
    net = NetGeometry(name, pins=[PinPoint("R1", "1", (16, 16))], flags=[(16, -96)],
                      segments=[WireSegment(name, start, end)])
    return model, layouts, RoutingResult(net_geometries=[net])


class AscParserTests(unittest.TestCase):
    def parse(self, text):
        return parse_asc_semantics(text, "fixture", require_headers=False)

    def test_required_headers_and_order_for_complete_schematics(self):
        self.assertEqual(codes(parse_asc_semantics("")["diagnostics"]), {"MISSING_VERSION", "MISSING_SHEET"})
        self.assertIn("MISSING_VERSION", codes(parse_asc_semantics("SHEET 1 800 600")["diagnostics"]))
        self.assertIn("MISSING_SHEET", codes(parse_asc_semantics("Version 4")["diagnostics"]))
        for text in ("SHEET 1 800 600\nVersion 4", "WIRE 0 0 16 0\nVersion 4\nSHEET 1 800 600",
                     "Version 4\nTEXT 0 0 Left 2 ;note\nSHEET 1 800 600"):
            self.assertIn("HEADER_ORDER", codes(parse_asc_semantics(text)["diagnostics"]))
        for text in ("Version 4\nSHEET 1 800 600", "\n Version 4\n\n SHEET 1 800 600\n",
                     "Version 4\nSHEET 1 800 600\nWIRE 0 0 16 0\n" + symbol()):
            self.assertEqual(parse_asc_semantics(text)["diagnostics"], [])
        self.assertEqual(parse_asc_semantics("", require_headers=False)["diagnostics"], [])

    def test_empty_and_absent_record_types_are_not_errors(self):
        for text in ("", " \n\t", "Version 4\nSHEET 1 880 680\n", symbol(),
                     "WIRE 0 0 16 0", "FLAG 0 0 signal", "TEXT 1 3 Left 2 ;note"):
            with self.subTest(text=text):
                self.assertEqual(self.parse(text)["diagnostics"], [])
        self.assertIsNone(self.parse("")["version"])

    def test_complete_shape_preserves_payload_and_off_grid_annotations(self):
        text = ("Version 4\nSHEET 1 881 681\n" + symbol()
                + "WINDOW 0 3 -7 Left 2\nWINDOW 3 -9 11 VRight 0\n"
                + "SYMATTR Value {Rbase * 2}  \nSYMATTR SpiceLine foo=1  bar=2\n"
                + "WIRE 16 16 16 -16\nFLAG 16 -16 Vout\n"
                + "TEXT -3 7 Left 1 ;original  comment  \nTEXT 7 -9 Right 2 !.tran 0 1m\n")
        result = self.parse(text)
        self.assertEqual(result["diagnostics"], [])
        self.assertEqual(set(result), {"version", "sheet", "components", "wires", "flags", "text", "windows", "diagnostics"})
        component = result["components"][0]
        self.assertEqual(result["sheet"], dict(index=1, width=881, height=681, line=2))
        self.assertEqual(component["value"], "{Rbase * 2}  ")
        self.assertEqual(component["attributes"]["SpiceLine"], "foo=1  bar=2")
        self.assertEqual(component["pins"], {"1": [16, 16], "2": [16, 96]})
        self.assertEqual(result["text"][0]["value"], ";original  comment  ")
        self.assertEqual(result["text"][1]["value"], "!.tran 0 1m")
        self.assertEqual(result["windows"][0]["component"], "R1")
        json.dumps(result, allow_nan=False)

    def test_canonical_pins_all_native_symbols_and_orientations(self):
        for definition in COMPONENT_LIBRARY.values():
            for orientation in ("R0", "R90", "R180", "R270", "M0", "M90", "M180", "M270"):
                with self.subTest(kind=definition.kind, orientation=orientation):
                    result = self.parse(symbol(definition.prefix + "1", definition.symbol.swapcase().replace("\\", "/"),
                                               -32, 64, orientation))
                    self.assertEqual(result["diagnostics"], [])
                    self.assertEqual(result["components"][0]["pins"],
                                     {key: list(value) for key, value in PinResolver.resolve_all_pins(
                                         definition, (-32, 64), orientation).items()})
                    self.assertIsNone(result["components"][0]["value"])

    def test_scope_requires_immediately_preceding_symbol_block(self):
        for attr in ("WINDOW 0 1 3 Left 2", "SYMATTR Value 1k"):
            code = "ORPHAN_" + attr.split()[0]
            for breaker in ("WIRE 0 0 16 0", "TEXT 1 3 Left 2 ;note", "FLAG 0 0 n",
                            "WIRE invalid", "SYMBOL res broken", "SHEET 1 800 600", "UNKNOWN record"):
                with self.subTest(attr=attr, breaker=breaker):
                    result = self.parse(symbol() + breaker + "\n" + attr)
                    self.assertIn(code, codes(result["diagnostics"]))
                    self.assertIsNone(result["components"][0]["value"])
            self.assertIn(code, codes(self.parse(attr)["diagnostics"]))

    def test_new_symbol_owns_attributes_and_windows(self):
        result = self.parse(symbol() + "WINDOW 0 1 2 Left 2\n" + symbol("C1", "cap", 160)
                            + "WINDOW 0 1 2 Left 2\nSYMATTR Value 10u")
        self.assertEqual(result["diagnostics"], [])
        self.assertEqual([window["component"] for window in result["windows"]], ["R1", "C1"])
        self.assertEqual([component["value"] for component in result["components"]], [None, "10u"])

    def test_duplicate_predicates(self):
        fixtures = {
            "DUPLICATE_VERSION": "Version 4\nVersion 4",
            "DUPLICATE_SHEET": "SHEET 1 16 16\nSHEET 1 32 32",
            "DUPLICATE_SYMBOL": symbol() + symbol("R2", "RES"),
            "DUPLICATE_REFERENCE": symbol() + symbol("r1", x=160),
            "DUPLICATE_WIRE": "WIRE 0 0 32 0\nWIRE 32 0 0 0",
            "DUPLICATE_FLAG": "FLAG 0 0 VOUT\nFLAG 0 0 vout",
            "DUPLICATE_ATTRIBUTE": symbol() + "SYMATTR Value 1k\nSYMATTR value 2k",
            "DUPLICATE_WINDOW": symbol() + "WINDOW 0 1 2 Left 2\nWINDOW 0 3 4 Right 1",
            "DUPLICATE_TEXT": "TEXT 1 3 Left 2 ;note\nTEXT 1 3 Left 2 ;note",
        }
        for code, text in fixtures.items():
            with self.subTest(code=code):
                self.assertIn(code, codes(self.parse(text)["diagnostics"]))
        self.assertEqual(self.parse(fixtures["DUPLICATE_ATTRIBUTE"])["components"][0]["value"], "1k")
        for text in ("FLAG 0 0 a\nFLAG 16 0 a", "TEXT 0 0 Left 2 ;a\nTEXT 1 0 Left 2 ;a",
                     "TEXT 0 0 Left 2 ;a\nTEXT 0 0 Left 2 ;b", symbol() + symbol("R2", x=160)):
            self.assertEqual(self.parse(text)["diagnostics"], [])

    def test_invalid_reference_and_missing_reference(self):
        for value in ("", " ", "R 1", "R1.2", "1R", "R1;bad", "R1\tbad", "R1 "):
            with self.subTest(value=value):
                issues = self.parse(symbol(value))["diagnostics"]
                self.assertTrue(codes(issues) & {"MISSING_REFERENCE", "INVALID_REFERENCE"})
        for value in ("R_a-1$", "U1", "DLED"):
            self.assertEqual(self.parse(symbol(value))["diagnostics"], [])
        self.assertIn("MISSING_REFERENCE", codes(self.parse("SYMBOL res 0 0 R0")["diagnostics"]))

    def test_wrong_grid_exact_integer_unknown_symbol_and_orientation(self):
        for text in (symbol(x=1), "WIRE 0 0 17 0", "FLAG -1 0 n"):
            self.assertIn("OFF_GRID", codes(self.parse(text)["diagnostics"]))
        for token in ("0.0", "1e2", "nan", "inf", "0x10", "True", "１６"):
            for text in (symbol(x=token), f"WIRE 0 0 {token} 0", f"FLAG {token} 0 n",
                         symbol() + f"WINDOW 0 {token} 0 Left 2", f"TEXT {token} 0 Left 2 ;note"):
                with self.subTest(token=token, text=text):
                    self.assertIn("INVALID_INTEGER", codes(self.parse(text)["diagnostics"]))
        result = self.parse(symbol(name="resistor"))
        self.assertIn("UNKNOWN_SYMBOL", codes(result["diagnostics"]))
        self.assertEqual(result["components"][0]["pins"], {})
        for orientation in ("R45", "R360", "R090", "r0", "Q0"):
            self.assertIn("INVALID_ORIENTATION", codes(self.parse(symbol(orientation=orientation))["diagnostics"]))

    def test_headers_wire_and_annotation_validity(self):
        cases = [("Version 3", "INVALID_VERSION"), ("Version 4 extra", "MALFORMED_RECORD"),
                 ("SHEET 0 1 1", "INVALID_SHEET"), ("SHEET 2 1 1", "INVALID_SHEET"),
                 ("SHEET 1 0 16", "INVALID_SHEET"), ("SHEET 1 16 -1", "INVALID_SHEET"),
                 ("WIRE 0 0 0 0", "ZERO_LENGTH_WIRE"), ("WIRE 0 0 16 16", "NON_ORTHOGONAL_WIRE"),
                 (symbol() + "WINDOW -1 0 0 Left 2", "INVALID_WINDOW"),
                 (symbol() + "WINDOW 0 0 0 Bad 2", "INVALID_WINDOW"),
                 (symbol() + "WINDOW 0 0 0 Left 8", "INVALID_WINDOW"),
                 ("TEXT 0 0 Bad 2 ;note", "INVALID_TEXT"), ("TEXT 0 0 Left -1 ;note", "INVALID_TEXT"),
                 ("TEXT 0 0 Left 2 plain", "MALFORMED_RECORD"),
                 (symbol() + "SYMATTR Value", "EMPTY_ATTRIBUTE"), ("BOGUS anything", "UNKNOWN_RECORD")]
        for text, code in cases:
            with self.subTest(text=text):
                self.assertIn(code, codes(self.parse(text)["diagnostics"]))

    def test_malformed_input_is_diagnostic_and_parser_recovers(self):
        lines = ["Version", "SHEET 1", "SYMBOL", "WIRE", "FLAG", "TEXT", "WINDOW", "SYMATTR",
                 "WIRE 1 2 3 4 5", "FLAG 0 0 a b", "SYMBOL res 0 0 R0 extra", "\x00"]
        for line in lines:
            with self.subTest(line=line):
                result = self.parse(line + "\n" + symbol("R_OK", x=160))
                self.assertTrue(result["diagnostics"])
                self.assertEqual(result["components"][-1]["reference"], "R_OK")
        self.assertEqual(codes(self.parse(None)["diagnostics"]), {"INVALID_ASC"})

    def test_actionable_diagnostic_context(self):
        issues = self.parse(symbol(x=3) + "SYMATTR Value 1k\nSYMATTR VALUE 2k")["diagnostics"]
        for issue in issues:
            self.assertTrue({"circuit", "component", "pin", "net", "expected", "actual", "error", "code", "severity", "line"} <= issue.keys())
            self.assertEqual(issue["circuit"], "fixture")
            self.assertEqual(issue["component"], "R1")
            self.assertEqual(issue["severity"], "error")
            self.assertTrue(issue["error"])
        json.dumps(issues, allow_nan=False)


class TopologyTests(unittest.TestCase):
    def test_permutation_and_anonymous_names_do_not_matter(self):
        expected = {"N1": ["R1.1", "C1.2"], "N2": ["R1.2"], "empty": []}
        target = [("C1.2", "R1.1"), ("R1.2",)]
        self.assertEqual(canonical_topology(expected), target)
        for groups in permutations([["R1.2"], ["C1.2", "R1.1"]]):
            actual = {f"arbitrary-{i}": list(reversed(pins)) for i, pins in enumerate(groups)}
            self.assertEqual(canonical_topology(actual), target)
            self.assertEqual(compare_topology(expected, actual), [])
        self.assertEqual(canonical_topology({}), [])
        self.assertEqual(compare_topology({}, {}), [])

    def test_named_labels_are_optional_and_case_insensitive_not_aliases(self):
        before = {"VCC": ["R1.1"], "N1": ["R1.2"]}
        after = {"VDD": ["R1.1"], "N42": ["R1.2"]}
        self.assertEqual(compare_topology(before, after), [])
        self.assertEqual(codes(compare_topology(before, after, preserve_labels=True)), {"NAMED_NET_MISMATCH"})
        self.assertNotEqual(canonical_topology(before, preserve_labels=True), canonical_topology(after, preserve_labels=True))
        self.assertEqual(compare_topology(before, {"vcc": ["R1.1"], "N$004": ["R1.2"]}, preserve_labels=True), [])
        self.assertTrue(compare_topology({"0": ["R1.1"]}, {"GND": ["R1.1"]}, preserve_labels=True))

    def test_explicit_labels_preserve_alias_sets_and_arbitrary_anonymous_ids(self):
        before, after = {"source-group": ["R1.1"]}, {"routed-id": ["R1.1"]}
        labels_before, labels_after = {"source-group": ["OUT", "measure"]}, {"routed-id": ["MEASURE", "out"]}
        self.assertEqual(canonical_topology(before, preserve_labels=True, labels=labels_before),
                         [(('measure', 'out'), ('R1.1',))])
        self.assertEqual(compare_topology(before, after, preserve_labels=True,
                                         expected_labels=labels_before, actual_labels=labels_after), [])
        self.assertEqual(compare_topology(before, after, preserve_labels=True, expected_labels={}, actual_labels={}), [])
        self.assertEqual(codes(compare_topology(before, after, preserve_labels=True,
                                               expected_labels={"source-group": "OUT"}, actual_labels={})), {"NAMED_NET_MISMATCH"})
        self.assertEqual(canonical_topology({"VCC": []}, preserve_labels=True), [(('vcc',), ())])
        self.assertTrue(compare_topology({"VCC": []}, {}, preserve_labels=True))
        self.assertTrue(compare_topology({"OUT": ["R1.1"], "N1": ["R1.2"]},
                                         {"N2": ["R1.1"], "OUT": ["R1.2"]}, preserve_labels=True))

    def test_missing_unexpected_opens_and_shorts(self):
        before = {"N1": ["R1.1", "R2.1"], "N2": ["R3.1"], "N3": ["R4.1"]}
        after = {"A": ["R1.1", "R3.1"], "B": ["R2.1"], "C": ["X1.1"]}
        issues = compare_topology(before, after, circuit="topology")
        self.assertEqual(codes(issues), {"MISSING_PIN", "UNEXPECTED_PIN", "OPEN", "SHORT"})
        missing = next(issue for issue in issues if issue["code"] == "MISSING_PIN")
        self.assertEqual((missing["component"], missing["pin"], missing["circuit"]), ("R4", "1", "topology"))
        json.dumps(issues, allow_nan=False)

    def test_invalid_partitions_do_not_collapse_duplicate_pins(self):
        for groups in ({"A": "R1.1"}, {"A": ["R1"]}, {"A": [".1"]}, {"A": ["R1.1.2"]},
                       {"A": ["R1.1", "R1.1"]}, {"A": ["R1.1"], "B": ["R1.1"]}):
            with self.subTest(groups=groups):
                self.assertEqual(codes(compare_topology(groups, {})), {"INVALID_TOPOLOGY"})
                self.assertEqual(codes(compare_topology({}, groups)), {"INVALID_TOPOLOGY"})
                with self.assertRaises(ValueError):
                    canonical_topology(groups)
        self.assertEqual(codes(compare_topology({"A": ["R1.1"]}, {}, preserve_labels=True,
                                               expected_labels={"A": ["bad label"]})), {"INVALID_TOPOLOGY"})

    def test_actual_net_name_case_does_not_merge_distinct_groups(self):
        self.assertEqual(compare_topology({"1": ["R1.1"], "2": ["R2.1"]},
                                          {"net": ["R1.1"], "NET": ["R2.1"]}), [])


class MetricTests(unittest.TestCase):
    def test_both_relative_and_absolute_gates_and_exact_boundaries(self):
        cases = [("total_length", 1000, 1200, False), ("total_length", 1000, 1201, True),
                 ("total_length", 100, 163, False), ("total_length", 100, 164, True),
                 ("total_length", 0, 63, False), ("total_length", 0, 64, True),
                 ("bend_count", 10, 13, False), ("bend_count", 10, 14, True),
                 ("bend_count", 1, 2, False), ("bend_count", 1, 3, True),
                 ("bend_count", 0, 1, False), ("bend_count", 0, 2, True),
                 ("crossing_count", 0, 1, True), ("crossing_count", 100, 101, True),
                 ("crossing_count", 0, 0, False), ("total_length", 1000, 200, False)]
        for metric, old, new, regression in cases:
            with self.subTest(metric=metric, old=old, new=new):
                issues = compare_metrics({metric: old}, {metric: new})
                self.assertEqual(bool(issues), regression)
                self.assertTrue(all(issue["severity"] == "review" for issue in issues))
                if issues:
                    self.assertEqual(codes(issues), {"METRIC_REGRESSION"})

    def test_configurable_thresholds_and_no_global_mutation(self):
        before, after = {"total_length": 100}, {"total_length": 130}
        self.assertEqual(len(compare_metrics(before, after, thresholds={"total_length": {"absolute": 16}})), 1)
        self.assertEqual(compare_metrics(before, after), [])
        self.assertEqual(compare_metrics({"crossing_count": 0}, {"crossing_count": 1},
                                         thresholds={"crossing_count": {"absolute": 2}}), [])
        for thresholds in ({"typo": {}}, {"total_length": {"typo": 1}},
                           {"total_length": {"relative": -1}}, {"total_length": {"absolute": float("nan")}},
                           {"total_length": {"absolute": True}}):
            with self.assertRaises(ValueError):
                compare_metrics({}, {}, thresholds=thresholds)

    def test_missing_invalid_and_unrelated_metrics(self):
        self.assertEqual(compare_metrics({}, {}), [])
        self.assertEqual(compare_metrics({"area": 0}, {"area": 1e9}), [])
        for old, new in (({}, {"total_length": 1}), ({"bend_count": 1}, {})):
            self.assertEqual(codes(compare_metrics(old, new)), {"METRIC_MISSING"})
        for value in (-1, True, "10", None, float("inf"), float("nan")):
            with self.subTest(value=value):
                issues = compare_metrics({"total_length": value}, {"total_length": 1})
                self.assertEqual(codes(issues), {"INVALID_METRIC"})
                json.dumps(issues, allow_nan=False)


class GeometryAuditTests(unittest.TestCase):
    def audit(self, routed, **kwargs):
        return validate_routing(empty_model(), {}, routed, circuit="geometry", **kwargs)

    def test_empty_and_flag_endpoints(self):
        self.assertEqual(self.audit(RoutingResult()), [])
        net = wire_net("A", (0, 0), (64, 0))
        self.assertEqual(self.audit(RoutingResult(net_geometries=[net])), [])
        net.flags = []
        routed = RoutingResult(net_geometries=[net], flags=[RoutedFlag("A", (0, 0), "a"), RoutedFlag("A", (64, 0), "a")])
        before = copy.deepcopy(routed)
        self.assertEqual(self.audit(routed), [])
        self.assertEqual(routed, before)

    def test_direct_own_pin_flag_allowed_and_body_flag_rejected(self):
        model, layouts, routed = lead_fixture()
        net = routed.net_geometries[0]
        net.flags, net.segments = [(16, 16)], []
        self.assertEqual(validate_routing(model, layouts, routed), [])
        net.flags = [(16, 48)]
        self.assertIn("UNSAFE_ROUTING_FLAG", codes(validate_routing(model, layouts, routed)))

    def test_list_coordinates_are_accepted_without_input_mutation(self):
        routed = RoutingResult(net_geometries=[wire_net("A", [0, 0], [64, 0])])
        before = copy.deepcopy(routed)
        self.assertEqual(self.audit(routed), [])
        self.assertEqual(routed, before)

    def test_cleaned_long_lead_temporary_split_in_both_directions_no_mutation(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                model, layouts, routed = lead_fixture(reverse=reverse)
                before = copy.deepcopy((model, layouts, routed))
                self.assertEqual(validate_routing(model, layouts, routed), [])
                self.assertEqual((model, layouts, routed), before)
                self.assertEqual(len(routed.net_geometries[0].segments), 1)

    def test_long_wire_with_escapes_at_both_ends(self):
        model = build_connectivity({"components": [{"reference": ref, "type": "resistor"} for ref in ("R1", "R2")],
                                    "wires": [{"from": "R1.1", "to": "R2.2"}]})
        layouts = {"R1": {"type": "resistor", "_ltspice_anchor": (0, 0)},
                   "R2": {"type": "resistor", "_ltspice_anchor": (0, -256)}}
        net = NetGeometry(model.nets[0].name, pins=[PinPoint("R1", "1", (16, 16)), PinPoint("R2", "2", (16, -160))],
                          segments=[WireSegment(model.nets[0].name, (16, 16), (16, -160))])
        self.assertEqual(validate_routing(model, layouts, RoutingResult(net_geometries=[net])), [])

    def test_inward_owner_body_foreign_body_and_reserved_corridor_rejected(self):
        model, layouts, routed = lead_fixture()
        name = routed.net_geometries[0].name
        for end in ((16, 160), (64, 16)):
            net = NetGeometry(name, pins=[PinPoint("R1", "1", (16, 16))], flags=[end],
                              segments=[WireSegment(name, (16, 16), end)])
            self.assertIn("UNSAFE_ROUTING_SEGMENT", codes(validate_routing(model, layouts, RoutingResult(net_geometries=[net]))))
        # Unwired lower pin reserves its complete outward corridor.
        for start, end in (((-64, 112), (96, 112)), ((-64, 48), (96, 48))):
            foreign = wire_net("foreign", start, end)
            self.assertIn("UNSAFE_ROUTING_SEGMENT", codes(validate_routing(model, layouts, RoutingResult(net_geometries=[foreign]))))

    def test_geometry_errors_and_all_contacts_are_blocking(self):
        fixtures = [([wire_net("A", (0, 0), (0, 0))], "ZERO_LENGTH_WIRE"),
                    ([wire_net("A", (0, 0), (16, 16))], "NON_ORTHOGONAL_WIRE"),
                    ([wire_net("A", (0, 0), (17, 0))], "OFF_GRID"),
                    ([wire_net("A", (0, 0), (64, 0)), wire_net("B", (32, 0), (96, 0))], "NET_SHORT"),
                    ([wire_net("A", (0, 0), (64, 0)), wire_net("B", (64, 0), (64, 32))], "NET_SHORT"),
                    ([wire_net("A", (0, 0), (64, 0)), wire_net("B", (32, -32), (32, 0))], "NET_SHORT")]
        for nets, code in fixtures:
            with self.subTest(code=code, nets=nets):
                issues = self.audit(RoutingResult(net_geometries=nets))
                self.assertIn(code, codes(issues))
                self.assertTrue(all(issue["severity"] == "error" for issue in issues))

    def test_invalid_endpoint_orphan_disconnection_and_pin_not_connected(self):
        net = NetGeometry("A", pins=[PinPoint("R1", "1", (0, 0)), PinPoint("R2", "1", (96, 0))],
                          segments=[WireSegment("A", (0, 0), (32, 0)), WireSegment("A", (160, 0), (192, 0))])
        issues = self.audit(RoutingResult(net_geometries=[net]))
        self.assertTrue({"INVALID_WIRE_ENDPOINT", "ORPHAN_WIRE_ISLAND", "NET_DISCONNECTED", "PIN_NOT_CONNECTED"} <= codes(issues))
        issue = next(issue for issue in issues if issue["code"] == "PIN_NOT_CONNECTED")
        self.assertEqual((issue["component"], issue["pin"], issue["expected"]), ("R2", "1", [96, 0]))

    def test_duplicate_and_partial_same_net_overlap_invalid_but_subdivision_valid(self):
        for other, code in ((WireSegment("A", (64, 0), (0, 0)), "DUPLICATE_WIRE_SEGMENT"),
                            (WireSegment("A", (32, 0), (96, 0)), "OVERLAPPING_WIRE_SEGMENTS")):
            net = wire_net("A", (0, 0), (64, 0))
            net.segments.append(other)
            self.assertIn(code, codes(self.audit(RoutingResult(net_geometries=[net]))))
        net = NetGeometry("A", flags=[(0, 0), (64, 0)], segments=[WireSegment("A", (0, 0), (32, 0)), WireSegment("A", (32, 0), (64, 0))])
        self.assertEqual(self.audit(RoutingResult(net_geometries=[net])), [])

    def test_actual_crossings_must_exactly_match_declarations(self):
        nets = [wire_net("A", (-64, 0), (64, 0)), wire_net("B", (0, -64), (0, 64))]
        crossing = SafeCrossing(("B", "A"), (0, 0))
        self.assertEqual(self.audit(RoutingResult(net_geometries=nets, crossings=(crossing,))), [])
        self.assertIn("CROSSING_MISMATCH", codes(self.audit(RoutingResult(net_geometries=nets))))
        for declaration in (SafeCrossing(("A", "B"), (16, 0)), SafeCrossing(("A", "C"), (0, 0))):
            self.assertIn("CROSSING_MISMATCH", codes(self.audit(RoutingResult(net_geometries=nets, crossings=(declaration,)))))
        self.assertIn("CROSSING_MISMATCH", codes(self.audit(RoutingResult(net_geometries=nets[:1], crossings=(crossing,)))))
        self.assertIn("DUPLICATE_CROSSING", codes(self.audit(RoutingResult(net_geometries=nets, crossings=(crossing, crossing)))))
        self.assertIn("UNSAFE_ROUTING_SEGMENT", codes(self.audit(RoutingResult(net_geometries=nets, crossings=(crossing,)),
                                                                  options=RoutingOptions(allow_crossings=False))))

    def test_invalid_crossing_and_wire_ownership(self):
        nets = [wire_net("A", (-64, 0), (64, 0)), wire_net("B", (0, -64), (0, 64))]
        for crossing in (SafeCrossing(("A", "A"), (0, 0)), SafeCrossing(("A", "B"), (0.0, 0)),
                         SafeCrossing(("A", ""), (0, 0))):
            self.assertIn("INVALID_CROSSING", codes(self.audit(RoutingResult(net_geometries=nets, crossings=(crossing,)))))
        net = wire_net("A", (0, 0), (64, 0))
        net.segments = [WireSegment("wrong-net", (0, 0), (64, 0))]
        self.assertIn("WIRE_NET_MISMATCH", codes(self.audit(RoutingResult(net_geometries=[net]))))

    def test_crossing_flag_or_third_wire_cannot_be_hidden_by_metadata(self):
        nets = [wire_net("A", (-64, 0), (64, 0)), wire_net("B", (0, -64), (0, 64))]
        crossing = SafeCrossing(("A", "B"), (0, 0))
        nets[0].flags.append((0, 0))
        issues = self.audit(RoutingResult(net_geometries=nets, crossings=(crossing,)))
        self.assertIn("UNSAFE_ROUTING_FLAG", codes(issues))
        self.assertIn("NET_SHORT", codes(issues))
        nets[0].flags.pop()
        nets.append(wire_net("C", (-32, 0), (32, 0)))
        self.assertIn("UNSAFE_ROUTING_SEGMENT", codes(self.audit(RoutingResult(net_geometries=nets, crossings=(crossing,)))))

    def test_bad_layout_missing_layout_unknown_symbol_and_bad_coordinate(self):
        model, layouts, routed = lead_fixture()
        self.assertIn("MISSING_LAYOUT", codes(validate_routing(model, {}, routed)))
        for anchor in ((0.0, 0), (True, 0), (0,), None):
            layouts["R1"]["_ltspice_anchor"] = anchor
            self.assertIn("INVALID_ROUTING_GEOMETRY", codes(validate_routing(model, layouts, routed)))
        layouts["R1"] = {"type": "unsupported", "_ltspice_anchor": (0, 0)}
        self.assertIn("UNSUPPORTED_ROUTING_SYMBOL", codes(validate_routing(model, layouts, routed)))
        for coordinate in ((0.0, 0), (True, 0), (0,), None):
            net = wire_net("A", coordinate, (64, 0))
            self.assertIn("INVALID_COORDINATE", codes(self.audit(RoutingResult(net_geometries=[net]))))

    def test_flag_attachment_unknown_net_and_existing_diagnostics(self):
        self.assertIn("FLAG_NOT_CONNECTED", codes(self.audit(RoutingResult(net_geometries=[NetGeometry("A", flags=[(0, 0)])]))))
        self.assertIn("UNKNOWN_FLAG_NET", codes(self.audit(RoutingResult(flags=[RoutedFlag("A", (0, 0), "A")]))))
        issue = ExportDiagnostic("error", "UPSTREAM", "Resolve upstream failure", component="R1", pin="1", actual=(0, 0))
        issues = self.audit(RoutingResult(diagnostics=[issue]))
        self.assertEqual(codes(issues), {"UPSTREAM"})
        self.assertEqual(issues[0]["circuit"], "geometry")
        json.dumps(issues, allow_nan=False)

    def test_no_pillow_or_exporter_import_dependency(self):
        program = ("import sys; sys.path.insert(0, " + repr(str(BACKEND_ROOT)) + "); "
                   "import app.services.regression_validation; "
                   "assert not any(name == 'PIL' or name.startswith('PIL.') for name in sys.modules); "
                   "assert 'app.services.ltspice_exporter' not in sys.modules")
        result = subprocess.run([sys.executable, "-S", "-c", program], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
