"""Reference-only corpus metadata, using the real compiler/bridge evidence."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from tools import corpus_catalog as catalog


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class SizeTests(unittest.TestCase):
    def test_exact_boundaries_and_invalid_counts(self):
        for count, expected in [(0, "unknown"), (1, "small"), (10, "small"), (20, "small"),
                                (21, "medium"), (25, "medium"), (50, "medium"), (100, "medium"),
                                (101, "large"), (250, "large"), (500, "large"), (501, "extreme"),
                                (10000, "extreme"), (None, "unknown"), (-1, "unknown"),
                                (True, "unknown"), (False, "unknown"), (1.5, "unknown"), (25.0, "unknown"), ("25", "unknown")]:
            with self.subTest(count=count):
                self.assertEqual(catalog.classify_size(count), expected)


class CatalogFixture:
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.collection = self.root / "collection"
        self.collection.mkdir()

    def source(self, value, key="case", **extra):
        relative = f"inputs/{key}.json"
        path = self.collection / relative
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return {"id": key, "name": key, "input": relative, "sha256": digest(value),
                "origins": [{"source": "backend/circuits/example.json", "source_sha256": "original-hash", "locator": "$", "kind": "json"}],
                "counts": {"components": 999, "pins": None, "nets": None}, "synthetic": False,
                "target_components": 500, "support": "not_tested", **extra}

    def enrich(self, cases, **kwargs):
        return catalog.enrich_catalog({"schema_version": 1, "cases": cases, "summary": {"total_cases": len(cases)}}, self.collection, **kwargs)


class CatalogTests(CatalogFixture, unittest.TestCase):
    def test_actual_counts_preserve_every_original_field_and_byte(self):
        case = self.source({"components": [{"reference": "R1", "type": "resistor"}, None], "wires": []})
        before = deepcopy(case)
        path = self.collection / case["input"]
        raw = path.read_bytes()
        result = self.enrich([case])
        enriched = result["cases"][0]
        self.assertEqual(case, before)
        self.assertEqual({key: enriched[key] for key in case}, case)
        self.assertEqual(path.read_bytes(), raw)
        metadata = enriched["catalog_metadata"]
        self.assertEqual(metadata["input_component_count"], 2)
        self.assertEqual(metadata["size_class"], "small")
        self.assertEqual(metadata["input_integrity"], "match")
        self.assertEqual(metadata["observed_input_sha256"], case["sha256"])
        self.assertIn("malformed", metadata["categories"])
        self.assertEqual(metadata["component_support"]["counts"], {"supported": 0, "unsupported": 0, "unknown": 2})

    def test_envelopes_nodes_strings_and_malformed_inputs(self):
        values = [({"components": []}, 0), ({"circuit": {"nodes": [None]}}, 1),
                  ({"data": {"circuit": {"components": [{}, {}]}}}, 2),
                  ({"components": "invalid", "nodes": [{}]}, 1),
                  ('```json\n{"components": [{}]}\n```', 1),
                  (None, None), ({}, None), ({"components": 0}, None), ("not JSON", None)]
        for index, (value, count) in enumerate(values):
            with self.subTest(value=value):
                metadata = self.enrich([self.source(value, str(index))])["cases"][0]["catalog_metadata"]
                self.assertEqual(metadata["input_component_count"], count)
                self.assertEqual(metadata["size_class"], "unknown" if count in (None, 0) else "small")
                if count in (None, 0):
                    self.assertIn("malformed", metadata["categories"])

    def test_missing_and_invalid_input_files_preserve_cases(self):
        cases = [self.source({}, "missing"), self.source({}, "invalid")]
        (self.collection / cases[0]["input"]).unlink()
        (self.collection / cases[1]["input"]).write_text("{broken", encoding="utf-8")
        result = self.enrich(cases)
        self.assertEqual(len(result["cases"]), 2)
        for case in result["cases"]:
            metadata = case["catalog_metadata"]
            self.assertEqual(metadata["size_class"], "unknown")
            self.assertEqual(metadata["input_integrity"], "unavailable")
            self.assertTrue(metadata["evidence_issues"])
        self.assertIn("malformed", result["cases"][1]["catalog_metadata"]["categories"])
        self.assertNotIn("malformed", result["cases"][0]["catalog_metadata"]["categories"])

    def test_input_digest_mismatch_never_attributes_old_diagnostics(self):
        case = self.source({"components": [{"id": "U1", "type": "mystery"}]})
        case["sha256"] = "old-digest"
        report = {"cases": [{"id": case["id"], "samples": [{"diagnostics": [
            {"severity": "error", "code": "COMPILER_ERROR", "message": "Unknown component type 'mystery' on component U1."}]}]}]}
        metadata = self.enrich([case], report=report)["cases"][0]["catalog_metadata"]
        self.assertEqual(metadata["input_integrity"], "mismatch")
        self.assertEqual(metadata["component_support"]["counts"]["unknown"], 1)

    def test_overlapping_indexes_reference_inputs_and_preserve_unknown_cases(self):
        cases = [self.source({"components": [{}] * count}, str(count)) for count in (1, 26, 101, 501)]
        cases.append(self.source(None, "malformed"))
        cases.append(self.source({}, "missing"))
        (self.collection / cases[-1]["input"]).unlink()
        cases[0]["origins"][0]["source"] = "backend/tests/test_example.py"
        report = {"cases": [{"id": "26", "overall": "UNSUPPORTED"}, {"id": "101", "overall": "FAIL"}]}
        enriched = self.enrich(cases, report=report)
        before = {path: path.read_bytes() for path in self.collection.rglob("*.json")}
        output = self.root / "indexes"
        paths = catalog.write_category_indexes(enriched, self.collection, output)
        self.assertEqual(set(paths), {"all", *catalog.CATEGORIES})
        views = {key: json.loads(path.read_text()) for key, path in paths.items()}
        self.assertEqual(views["all"]["count"], len(cases))
        self.assertEqual(views["regression"]["cases"][0]["id"], "1")
        for category, identity in [("small", "1"), ("medium", "26"), ("large", "101"), ("extreme", "501")]:
            self.assertEqual([case["id"] for case in views[category]["cases"]], [identity])
        self.assertEqual(views["unsupported"]["cases"][0]["id"], "26")
        self.assertEqual(views["failing"]["cases"][0]["id"], "101")
        self.assertEqual(views["malformed"]["cases"][0]["id"], "malformed")
        originals = {case["id"]: case for case in cases}
        for entry in views["all"]["cases"]:
            original = originals[entry["id"]]
            for key in ("id", "input", "sha256", "origins"):
                self.assertEqual(entry[key], original[key])
            self.assertEqual((output / entry["input_path"]).resolve(), (self.collection / original["input"]).resolve())
            self.assertNotIn("components", entry)
            self.assertNotIn("wires", entry)
        self.assertEqual(before, {path: path.read_bytes() for path in self.collection.rglob("*.json")})
        self.assertEqual({path.suffix for path in output.iterdir()}, {".json"})
        with self.assertRaises(ValueError):
            catalog.write_category_indexes(enriched, self.collection, output)

    def test_deterministic_idempotent_enrichment_and_index_bytes(self):
        cases = [self.source({"components": [{}]}, "z"), self.source({"components": []}, "a")]
        first = self.enrich(cases)
        second = catalog.enrich_catalog(first, self.collection)
        self.assertEqual(first, second)
        out = self.root / "indexes"
        views = catalog.category_indexes(first, self.collection, index_root=out)
        reordered = deepcopy(first)
        reordered["cases"].reverse()
        self.assertEqual(views, catalog.category_indexes(reordered, self.collection, index_root=out))
        paths = catalog.write_category_indexes(first, self.collection, out)
        original = {name: path.read_bytes() for name, path in paths.items()}
        for path in paths.values():
            path.unlink()
        paths = catalog.write_category_indexes(second, self.collection, out)
        self.assertEqual(original, {name: path.read_bytes() for name, path in paths.items()})

    def test_report_enrichment_keeps_attempts_and_nonexecuted_catalog_cases(self):
        cases = [self.source({"components": []}, "run"), self.source(None, "unrun")]
        report = {"summary": {"cases": 1}, "cases": [{"id": "run", "overall": "INVALID", "samples": [{"overall": "INVALID"}]}]}
        original = deepcopy(report)
        enriched = self.enrich(cases, report=report)
        result = catalog.enrich_report(report, enriched)
        self.assertEqual(report, original)
        self.assertEqual(result["cases"][0]["samples"], report["cases"][0]["samples"])
        self.assertEqual(len(result["cases"]), 1)
        self.assertEqual(len(enriched["cases"]), 2)
        self.assertEqual(result["cases"][0]["input"], cases[0]["input"])
        self.assertEqual(result["cases"][0]["sha256"], cases[0]["sha256"])
        self.assertIn("malformed", result["cases"][0]["catalog_metadata"]["categories"])
        absent = catalog.enrich_report({"cases": [{"id": "absent"}]}, enriched)
        self.assertEqual(absent["cases"][0]["catalog_metadata"]["evidence_issues"], ["case_not_in_catalog"])

    def test_case_level_support_is_not_component_evidence(self):
        case = self.source({"components": [{"type": "resistor"}]}, support="supported")
        case["origins"][0].update(source="backend/tests/corpus/fixture_generator.py", kind="synthetic")
        report = {"cases": [{"id": case["id"], "overall": "PASS", "support": ["supported"]}]}
        metadata = self.enrich([case], report=report)["cases"][0]["catalog_metadata"]
        self.assertEqual(metadata["component_support"]["counts"], {"supported": 0, "unsupported": 0, "unknown": 1})
        self.assertNotIn("regression", metadata["categories"])
        case["regression"] = True
        self.assertIn("regression", self.enrich([case])["cases"][0]["catalog_metadata"]["categories"])

    def test_paths_cannot_escape_collection(self):
        case = self.source({"components": []})
        case["input"] = "../outside.json"
        metadata = self.enrich([case])["cases"][0]["catalog_metadata"]
        self.assertEqual(metadata["evidence_issues"], ["invalid_input_path"])


class RealEvidenceTests(CatalogFixture, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = {
            "mixed": {"components": [{"id": "res-id", "reference": "R1", "type": "resistor"},
                                      {"id": "source-id", "reference": "V1", "type": "voltage_source"}], "wires": []},
            "unknown": {"components": [{"reference": "U1", "type": "LM358"}], "wires": []},
            "partial": {"components": [{"reference": "R1", "type": "resistor"}, {"reference": "U1", "type": "LM358"}], "wires": []},
            "generated": {"components": [{"type": "resistor"}], "wires": []},
            "bad_pin": {"components": [{"reference": "R1", "type": "resistor"}], "wires": [{"from": "R1.999", "to": "GND"}]},
            "duplicates": {"components": [{"id": "R1", "type": "resistor"}, {"id": "R1", "type": "resistor"}], "wires": []},
        }
        process = subprocess.run(["node", str(BACKEND.parent / "frontend/tools/compile-regression.cjs")],
                                 input=json.dumps({"circuits": [{"key": key, "input": value} for key, value in cls.inputs.items()]}),
                                 capture_output=True, text=True, encoding="utf-8", timeout=30)
        if process.returncode:
            raise AssertionError(process.stderr or process.stdout)
        cls.compiled = {item["key"]: item for item in json.loads(process.stdout)["circuits"]}

    def support(self, key):
        return catalog.component_support(self.inputs[key]["components"], [{"compiled": self.compiled[key]}])

    def test_real_mixed_frontend_and_bridge_boundary(self):
        support = self.support("mixed")
        self.assertEqual(support["boundary"], catalog.SUPPORT_BOUNDARY)
        self.assertEqual(support["counts"], {"supported": 1, "unsupported": 1, "unknown": 0})
        self.assertEqual(support["supported"][0]["reference"], "R1")
        self.assertEqual(support["supported"][0]["evidence"][0]["compiled_id"], "res-id")
        self.assertEqual(support["unsupported"][0]["reference"], "V1")
        self.assertFalse(self.compiled["mixed"]["valid"])
        self.assertTrue(self.compiled["mixed"]["compiler_valid"])

    def test_unknown_type_negative_diagnostic_not_silent_unknown(self):
        support = self.support("unknown")
        self.assertEqual(support["counts"], {"supported": 0, "unsupported": 1, "unknown": 0})
        self.assertEqual(support["unsupported"][0]["reference"], "U1")
        self.assertEqual(support["unsupported"][0]["evidence"][0]["diagnostic"]["code"], "COMPILER_ERROR")

    def test_partial_compilation_preserves_input_slots(self):
        support = self.support("partial")
        self.assertEqual(support["counts"], {"supported": 1, "unsupported": 1, "unknown": 0})
        self.assertEqual(len(self.compiled["partial"]["components"]), 1)
        self.assertEqual(sum(support["counts"].values()), 2)

    def test_generated_identity_uses_real_mapping_only(self):
        support = self.support("generated")
        self.assertEqual(support["counts"]["supported"], 1)
        self.assertEqual(support["supported"][0]["source_index"], 0)
        self.assertNotIn("id", support["supported"][0])
        compiled = deepcopy(self.compiled["generated"])
        compiled["identity_mapping"] = []
        missing = catalog.component_support(self.inputs["generated"]["components"], [{"compiled": compiled}])
        self.assertEqual(missing["counts"]["unknown"], 1)

    def test_invalid_wiring_does_not_mean_unsupported_kind(self):
        support = self.support("bad_pin")
        self.assertFalse(self.compiled["bad_pin"]["valid"])
        self.assertEqual(support["counts"], {"supported": 1, "unsupported": 0, "unknown": 0})

    def test_ambiguous_identity_not_attributed_by_position(self):
        support = self.support("duplicates")
        self.assertEqual(support["counts"], {"supported": 0, "unsupported": 0, "unknown": 2})

    def test_missing_definitions_or_compilation_is_explicit_unknown(self):
        compiled = deepcopy(self.compiled["generated"])
        compiled.pop("pin_definitions")
        for observations in ([], [{"compiled": compiled}], [{"diagnostics": [{"code": "COMPILER_TIMEOUT", "severity": "error"}]}]):
            support = catalog.component_support(self.inputs["generated"]["components"], observations)
            self.assertEqual(support["counts"]["unknown"], 1)

    def test_conflicting_evidence_and_unattributed_negative_diagnostics(self):
        observations = [{"compiled": self.compiled["generated"]}, {"diagnostics": [
            {"severity": "error", "code": "UNSUPPORTED_SHARED_EXPORT_KIND", "source_index": 0},
            {"severity": "error", "code": "UNSUPPORTED_SHARED_EXPORT_KIND", "compiled_id": "not-mapped"},
            {"severity": "error", "code": "UNSUPPORTED_ROTATION", "component": "R1"}]}]
        support = catalog.component_support(self.inputs["generated"]["components"], observations)
        self.assertEqual(support["unknown"][0]["reason"], "conflicting_evidence")
        self.assertEqual(len(support["unattributed_diagnostics"]), 2)
        self.assertEqual(support, catalog.component_support(self.inputs["generated"]["components"], list(reversed(observations))))

    def test_executed_catalog_reads_compiled_files_and_report_diagnostics(self):
        cases = [self.source(value, key) for key, value in self.inputs.items()]
        report = {"cases": []}
        evidence = self.root / "execution"
        for case in cases:
            compiled = self.compiled[case["id"]]
            directory = f"{case['id']}/sample-1"
            path = evidence / directory / "compiled.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(compiled), encoding="utf-8")
            sample = {"evidence_directory": directory, "diagnostics": compiled["diagnostics"],
                      "compiled_sha256": digest({key: value for key, value in compiled.items() if key != "duration_ms"})}
            report["cases"].append({"id": case["id"], "samples": [sample]})
        before = deepcopy(report)
        result = self.enrich(cases, report=report, evidence_root=evidence)
        self.assertEqual(report, before)
        for case in result["cases"]:
            self.assertEqual(case["catalog_metadata"]["component_support"], self.support(case["id"]))
        self.assertEqual(result, catalog.enrich_catalog(result, self.collection, report=report, evidence_root=evidence))
        for error, change in [("compiled_digest_mismatch", {"compiled_sha256": "bad"}),
                              ("unreadable_file", {"evidence_directory": "missing"}),
                              ("invalid_evidence_path", {"evidence_directory": "../outside"})]:
            modified = deepcopy(report)
            modified["cases"][0]["samples"][0].update(change)
            metadata = self.enrich(cases, report=modified, evidence_root=evidence)["cases"][0]["catalog_metadata"]
            self.assertIn(error, metadata["evidence_issues"])
            self.assertEqual(metadata["component_support"]["counts"]["supported"], 0)


if __name__ == "__main__":
    unittest.main()
