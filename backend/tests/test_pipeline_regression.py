"""Full compiler-derived regression plus failure injection; no live AI requests."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BACKEND), str(BACKEND / "tests")]

from app.services.asc_validation import ERROR, ExportDiagnostic, WireSegment
from app.services.ltspice_exporter import generate_asc_with_routing
from app.services.routing import RoutingResult, route_nets
from tools import run_regression as regression


class FullPipelineRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = regression.load_dataset()
        cls.compiled, cls.coverage = regression.compile_fixtures(cls.dataset["circuits"])

    def test_all_existing_circuits_compile_route_export_and_preserve_semantics(self):
        with tempfile.TemporaryDirectory() as directory:
            for entry in self.dataset["circuits"]:
                with self.subTest(circuit=entry["key"]):
                    result = regression.validate_case(entry, self.dataset, Path(directory), self.compiled[entry["key"]], samples=2)
                    self.assertEqual(result["diagnostics"], [])
                    for category in ("compiler", "electrical", "routing", "export"):
                        self.assertEqual(result["categories"][category], "PASS", result)
                    self.assertEqual(result["categories"]["ltspice"], "REVIEW")
                    self.assertTrue(result["deterministic"])
                    self.assertTrue(Path(result["asc"]).is_file())
                    self.assertEqual(result["counts"]["pins"], len(result["pins"]))
                    self.assertEqual(result["reviews"], [])

    def test_library_inventory_and_all_shared_component_types_are_covered(self):
        self.assertEqual(regression.library_diagnostics(self.dataset), [])
        covered = {c["kind"] for entry in self.dataset["circuits"] for c in entry["components"].values()}
        self.assertEqual(covered, set(self.dataset["library"]))
        self.assertEqual(len(self.dataset["circuits"]), 7)
        self.assertEqual(self.coverage["component_count"], 26)
        self.assertEqual(self.coverage["pin_count"], 60)
        self.assertIn("voltage_source", self.coverage["unsupported_shared_export"])

    def test_reference_library_drift_is_not_automatically_approved(self):
        dataset = copy.deepcopy(self.dataset)
        dataset["library"]["resistor"]["pins"][0]["name"] = "wrong"
        diagnostics = regression.library_diagnostics(dataset)
        self.assertEqual(diagnostics[0]["code"], "LIBRARY_CONTRACT_DRIFT")

    def test_required_connection_removal_is_diagnosed_without_creating_asc(self):
        entry = next(e for e in self.dataset["circuits"] if e["key"] == "common_emitter_amplifier")
        compiled = copy.deepcopy(self.compiled[entry["key"]])
        compiled["backend"]["wires"] = []
        with tempfile.TemporaryDirectory() as directory:
            result = regression.validate_case(entry, self.dataset, Path(directory), compiled, samples=1)
            self.assertEqual(result["categories"]["electrical"], "FAIL")
            self.assertTrue(result["diagnostics"])
            self.assertFalse(list(Path(directory).glob("*.asc")))

    def test_compiler_net_mutation_cannot_hide_behind_correct_backend_connections(self):
        entry = self.dataset["circuits"][0]
        compiled = copy.deepcopy(self.compiled[entry["key"]])
        compiled["topology"][0]["pins"].append(compiled["topology"][1]["pins"][0])
        with tempfile.TemporaryDirectory() as directory:
            result = regression.validate_case(entry, self.dataset, Path(directory), compiled, samples=1)
            self.assertTrue(result["diagnostics"])
            self.assertEqual(result["overall"], "FAIL")
            self.assertFalse(list(Path(directory).glob("*.asc")))

    def test_compiler_label_metadata_drift_is_detected(self):
        entry = self.dataset["circuits"][0]
        compiled = copy.deepcopy(self.compiled[entry["key"]])
        labelled = next(net for net in compiled["topology"] if net["labels"])
        labelled["labels"] = ["WRONG_LABEL"]
        with tempfile.TemporaryDirectory() as directory:
            result = regression.validate_case(entry, self.dataset, Path(directory), compiled, samples=1)
        self.assertIn("NAMED_NET_MISMATCH", {d["code"] for d in result["diagnostics"]})

    def test_compiler_pin_count_drift_is_actionable(self):
        entry = self.dataset["circuits"][0]
        compiled = copy.deepcopy(self.compiled[entry["key"]])
        compiled["components"][0]["pins"].pop()
        with tempfile.TemporaryDirectory() as directory:
            result = regression.validate_case(entry, self.dataset, Path(directory), compiled, samples=1)
        problem = next(d for d in result["diagnostics"] if d["code"] == "COMPILER_PIN_MISMATCH")
        self.assertTrue(problem["component"])
        self.assertNotEqual(problem["expected"], problem["actual"])

    def test_missing_ltspice_is_strict_failure_not_skipped_success(self):
        entry = self.dataset["circuits"][0]
        with tempfile.TemporaryDirectory() as directory:
            result = regression.validate_case(entry, self.dataset, Path(directory), self.compiled[entry["key"]], samples=1, require_ltspice=True)
        self.assertEqual(result["categories"]["ltspice"], "FAIL")
        self.assertEqual(result["overall"], "FAIL")

    def test_actual_ltspice_error_is_reported_not_suppressed(self):
        entry = self.dataset["circuits"][0]
        with tempfile.TemporaryDirectory() as directory, patch.object(regression, "run_ltspice_netlist", side_effect=RuntimeError("fixture netlist failed")):
            result = regression.validate_case(entry, self.dataset, Path(directory), self.compiled[entry["key"]], samples=1, executable=Path("LTspice.exe"))
        self.assertEqual(result["categories"]["ltspice"], "FAIL")
        self.assertIn("fixture netlist failed", str(result["diagnostics"]))


class PipelineFailureRecoveryTests(unittest.TestCase):
    def test_invalid_backend_sources_never_return_usable_asc(self):
        sources = [
            {"components": [{"reference": "X1", "type": "unknown"}], "wires": [{"from": "X1.1", "to": "VCC"}]},
            {"components": [{"reference": "R1", "type": "resistor"}], "wires": [{"from": "R1.9", "to": "VIN"}]},
            {"components": [{"reference": "R1", "type": "resistor"}], "wires": [{"from": "R2.1", "to": "R1.1"}]},
            {"components": [{"reference": "R1", "type": "resistor"}], "wires": [{"from": "VCC", "to": "GND"}]},
            {"components": [{"reference": "V1", "type": "voltage_source"}], "wires": [{"from": "V1.1", "to": "GND"}]},
            {"components": [{"reference": "R1", "type": "resistor", "value": "1k\nWIRE 0 0 16 0"}]},
        ]
        for source in sources:
            with self.subTest(source=source):
                asc, diagnostics, _ = generate_asc_with_routing(source)
                self.assertFalse(asc)
                self.assertTrue(any(d.severity == ERROR for d in diagnostics))

    def test_impossible_route_reports_explicit_failure_without_partial_file(self):
        source = {"name": "Blocked circuit", "components": [{"reference": "R1", "type": "resistor"}], "wires": [{"from": "R1.1", "to": "VIN"}]}
        failed = RoutingResult(diagnostics=[ExportDiagnostic(ERROR, "ROUTE_FAILED", "Pin escape blocked", net="VIN", component="R1", pin="1", actual=(80, 144))])
        with patch("app.services.ltspice_exporter.route_nets", return_value=failed):
            asc, diagnostics, _ = generate_asc_with_routing(source)
        self.assertFalse(asc)
        self.assertEqual(diagnostics[-1].circuit, "Blocked circuit")
        self.assertIn("Pin escape blocked", diagnostics[-1].format())

    def test_invalid_coordinate_and_dangling_required_pin_block_export(self):
        source = json.loads((BACKEND / "circuits/common_emitter_amplifier.json").read_text())
        def malformed(model, layouts):
            routed = route_nets(model, layouts)
            net = routed.net_geometries[0]
            segment = net.segments[0]
            net.segments[0] = WireSegment(net.name, (segment.start[0] + 1, segment.start[1]), segment.end)
            return routed
        with patch("app.services.ltspice_exporter.route_nets", side_effect=malformed):
            asc, diagnostics, _ = generate_asc_with_routing(source)
        self.assertFalse(asc)
        self.assertTrue({d.code for d in diagnostics} & {"OFF_GRID", "INVALID_WIRE_ENDPOINT", "NON_ORTHOGONAL_WIRE"})

    def test_default_output_paths_are_unique_for_repeated_commands(self):
        first = regression.fresh_output()
        second = regression.fresh_output()
        self.assertNotEqual(first, second)
        self.assertIn("regression", first.parts)
        self.assertIn("export-validation", regression.fresh_output(True).parts)

    def test_serialized_label_change_cannot_pass_topology_only_comparison(self):
        dataset = regression.load_dataset()
        entry = next(e for e in dataset["circuits"] if e["key"] == "common_emitter_amplifier")
        def renamed_label(value, strict=False):
            asc, diagnostics, routed = generate_asc_with_routing(value, strict)
            asc = "\n".join(line.rsplit(" ", 1)[0] + " WRONG" if line.startswith("FLAG ") and line.endswith(" VCC") else line
                            for line in asc.splitlines()) + "\n"
            return asc, diagnostics, routed
        with tempfile.TemporaryDirectory() as directory, patch.object(regression, "generate_asc_with_routing", side_effect=renamed_label):
            result = regression.validate_case(entry, dataset, Path(directory), samples=1)
            self.assertFalse(list(Path(directory).glob("*.asc")))
        self.assertIn("SERIALIZED_LABEL_MISMATCH", {d["code"] for d in result["diagnostics"]})

    def test_compiler_derived_input_mutation_is_detected(self):
        dataset = regression.load_dataset()
        entry = dataset["circuits"][0]
        source = json.loads((regression.ROOT / entry["source"]).read_text())
        def mutating_export(value, strict=False):
            value["description"] = "unexpected mutation"
            return generate_asc_with_routing(value, strict)
        with tempfile.TemporaryDirectory() as directory, patch.object(regression, "generate_asc_with_routing", side_effect=mutating_export):
            result = regression.validate_case(entry, dataset, Path(directory), samples=1)
        self.assertIn("SOURCE_MUTATED", {d["code"] for d in result["diagnostics"]})
        self.assertEqual(result["overall"], "FAIL")

    def test_nonempty_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / "user.txt"
            sentinel.write_text("retain me")
            with self.assertRaises(ValueError):
                regression.run_suite(directory, export_only=True)
            self.assertEqual(sentinel.read_text(), "retain me")

    def test_visual_review_rejects_missing_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "regression_report.json").write_text(json.dumps({"circuits": [{"key": "a"}]}))
            with self.assertRaises(ValueError):
                regression.accept_visual_review(directory, {}, "test")

    def test_visual_review_rejects_stale_screenshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "image.png"
            asc = root / "circuit.asc"
            image.write_bytes(b"changed image")
            asc.write_text("Version 4\nSHEET 1 64 64\n")
            report = {"circuits": [{"key": "a", "asc": str(asc), "asc_sha256": regression.digest(asc),
                                      "visual": {"native": str(image), "native_sha256": "old"}}]}
            (root / "regression_report.json").write_text(json.dumps(report))
            with self.assertRaises(ValueError):
                regression.accept_visual_review(root, {"a": {"status": "PASS", "evidence": "test"}}, "test")


if __name__ == "__main__":
    unittest.main()
