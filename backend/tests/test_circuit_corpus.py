"""Corpus inventory, real bridge, isolated execution and failure accounting."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BACKEND), str(BACKEND / "tests/corpus")]
from tools import circuit_corpus as corpus
from fixture_generator import SIZES, python_definitions, scale_circuit


class CorpusInventoryTests(unittest.TestCase):
    def test_inventory_is_deterministic_and_excludes_dependencies_and_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("backend/circuits/example.json", "frontend/examples/example.ts", "node_modules/ignored.json", "backend/tests/artifacts/old.json"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('{"components": [], "wires": []}', encoding="utf-8")
            first = corpus.inventory(root)
            self.assertEqual(first, corpus.inventory(root))
            by_source = {item["source"]: item for item in first}
            self.assertEqual(by_source["node_modules"]["kind"], "excluded_directory")
            self.assertNotIn("node_modules/ignored.json", by_source)
            self.assertEqual(by_source["backend/tests/artifacts/old.json"]["kind"], "generated_evidence")
            self.assertEqual(by_source["frontend/examples/example.ts"]["candidate_lines"], [1])

    def test_collection_deduplicates_content_but_preserves_every_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repository"
            root.mkdir()
            source = '{"name": "A", "components": [], "wires": []}'
            for name in ("a.json", "b.json"):
                (root / name).write_text(source, encoding="utf-8")
            _, first = corpus.collect_circuits(Path(directory) / "one", root=root, include_synthetic=False)
            _, second = corpus.collect_circuits(Path(directory) / "two", root=root, include_synthetic=False)
            self.assertEqual(first, second)
            self.assertEqual(first["summary"]["repository_cases"], 1)
            self.assertEqual(len(first["cases"][0]["origins"]), 2)
            self.assertEqual((root / "a.json").read_text(), source)
            self.assertEqual(first["cases"][0]["counts"]["pins"], None)
            self.assertEqual(first["cases"][0]["validation"], "not_tested")
            self.assertEqual(first["cases"][0]["catalog_metadata"]["size_class"], "unknown")
            view = json.loads((Path(directory) / "one/indexes/malformed.json").read_text())
            self.assertEqual(view["count"], 1)

    def test_static_frontend_templates_and_python_builders_are_collected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repository"
            template = root / "frontend/examples/template.ts"
            template.parent.mkdir(parents=True)
            template.write_text('export const sample = {components: [{reference: "R1", type: "resistor"}], wires: []} as const;', encoding="utf-8")
            builder = root / "backend/builders/sample.py"
            builder.parent.mkdir(parents=True)
            builder.write_text('def make_sample():\n    return {"components": [{"reference": "C1", "type": "capacitor"}], "wires": []}', encoding="utf-8")
            _, catalog = corpus.collect_circuits(Path(directory) / "collected", root=root, include_synthetic=False)
            self.assertEqual(catalog["summary"]["repository_cases"], 2)
            kinds = {origin["kind"] for case in catalog["cases"] for origin in case["origins"]}
            self.assertEqual(kinds, {"python_data_expression", "frontend_data_expression"})
            self.assertTrue(all(origin["source_sha256"] for case in catalog["cases"] for origin in case["origins"]))

    def test_invalid_fixture_json_is_reported_without_aborting_collection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repository"
            source = root / "backend/circuits/broken.json"
            source.parent.mkdir(parents=True)
            source.write_text('{"components":', encoding="utf-8")
            _, catalog = corpus.collect_circuits(Path(directory) / "collected", root=root, include_synthetic=False)
            self.assertEqual(catalog["summary"]["repository_cases"], 0)
            self.assertEqual(catalog["extraction"][0]["status"], "invalid_json")

    def test_string_envelopes_and_missing_counts_are_not_fabricated(self):
        source = {"components": [{"type": "resistor", "reference": "R1"}], "wires": []}
        for value in (source, {"circuit": source}, {"data": {"circuit": source}},
                      json.dumps(source), "```json\n" + json.dumps(source) + "\n```"):
            with self.subTest(value=value):
                self.assertEqual(1, corpus.input_counts(value)["components"])
                self.assertEqual(0, corpus.input_counts(value)["connections"])
        self.assertIsNone(corpus.input_counts({})["components"])
        self.assertIsNone(corpus.input_counts({"components": "invalid"})["components"])
        self.assertEqual(1, corpus.input_counts({"components": None, "nodes": [None]})["components"])

    def test_malformed_component_arrays_are_preserved_in_json_collection(self):
        for value in ({"components": "invalid"}, {"nodes": None}):
            with self.subTest(value=value):
                self.assertEqual([("$", value)], list(corpus.json_circuits(value)))

    def test_component_path_aliases_are_not_circuit_definitions(self):
        config = {"aliases": {"components": "@/components", "utils": "@/lib/utils"}}
        self.assertEqual([], list(corpus.json_circuits(config)))

    def test_unparsed_documentation_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repository"
            root.mkdir()
            (root / "example.md").write_text('```json\n{"components": broken}\n```', encoding="utf-8")
            _, catalog = corpus.collect_circuits(Path(directory) / "collected", root=root, include_synthetic=False)
            self.assertEqual(0, catalog["summary"]["repository_cases"])
            self.assertEqual(1, catalog["summary"]["unresolved_expressions"])
            self.assertEqual("partial", catalog["extraction"][0]["status"])

    def test_nonempty_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / "sentinel.json"
            sentinel.write_text("retain", encoding="utf-8")
            with self.assertRaises(ValueError):
                corpus.collect_circuits(directory)
            self.assertEqual(sentinel.read_text(), "retain")

    def test_python_literals_helpers_loops_and_unresolved_are_preserved(self):
        source = '''
def component(ref, kind="resistor", **extra):
    return {"reference": ref, "type": kind, **extra}
def circuit(components=None, edges=()):
    return {"components": components if components is not None else [component("R1")],
            "wires": [{"from": a, "to": b} for a, b in edges]}
def test_cases():
    for pin in ("1", "999"):
        source = circuit(edges=[(f"R1.{pin}", "GND")])
        build_connectivity(source)
    build_connectivity({"components": unknown_factory()})
'''
        found, unresolved = python_definitions(source)
        wires = {value["input"]["wires"][0]["from"] for value in found if value["input"].get("wires")}
        self.assertEqual(wires, {"R1.1", "R1.999"})
        self.assertTrue(any("unknown_factory" in value["expression"] for value in unresolved))

    def test_dynamic_builder_does_not_invent_an_empty_circuit(self):
        source = '''
def builder(count):
    components = []
    for index in range(count):
        components.append({"reference": f"R{index}", "type": "resistor"})
    return {"components": components, "wires": []}
'''
        found, unresolved = python_definitions(source)
        self.assertFalse(found)
        self.assertTrue(unresolved)

    def test_malformed_sources_are_not_dropped(self):
        found, _ = python_definitions('build_connectivity(None)\nbuild_connectivity({"components": [None], "wires": []})')
        self.assertIn(None, [value["input"] for value in found])
        self.assertIn({"components": [None], "wires": []}, [value["input"] for value in found])

    def test_synthetic_fixtures_have_exact_size_unique_identity_and_real_connections(self):
        from app.services.connectivity import build_connectivity, validate_connectivity
        for family in ("resistor", "filter"):
            for size in SIZES:
                with self.subTest(family=family, size=size):
                    source = scale_circuit(size, family)
                    self.assertEqual(source, scale_circuit(size, family))
                    self.assertEqual(len(source["components"]), size)
                    self.assertEqual(len({component["reference"] for component in source["components"]}), size)
                    model = build_connectivity(source)
                    self.assertFalse(model.unconnected_pins())
                    self.assertFalse([issue for issue in validate_connectivity(model) if issue.severity == "error"])
                    self.assertGreater(len(source["wires"]), size)
        with self.assertRaises(ValueError):
            scale_circuit(11, "filter")

    def test_all_repository_json_templates_are_inventoried(self):
        evidence = corpus.inventory()
        sources = {item["source"] for item in evidence if item["kind"] == "source"}
        expected = {path.relative_to(corpus.ROOT).as_posix() for folder in (BACKEND / "circuits", BACKEND / "tests/fixtures/routing") for path in folder.glob("*.json")}
        self.assertEqual(len(expected), 7)
        self.assertTrue(expected.issubset(sources))
        self.assertIn("frontend/tests/connectivity.test.cjs", sources)
        self.assertIn("backend/tests/test_connectivity.py", sources)


class CorpusExecutionTests(unittest.TestCase):
    def case(self, value, directory):
        body = corpus.circuit_body(value)
        case = {"id": "test-case", "name": body.get("name", "Test"), "synthetic": False,
                "counts": corpus.input_counts(value), "input": "input.json",
                "sha256": corpus.sha(corpus.canonical(value).encode())}
        corpus.write_json(Path(directory) / case["input"], value)
        return case

    def test_real_compiler_export_and_serialized_validation(self):
        source = json.loads((BACKEND / "circuits/rc_low_pass_filter.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case = self.case(source, root)
            result = corpus.run_case(case, root, root / "run", timeout=20)
            self.assertEqual(result["overall"], "PASS", result)
            self.assertTrue(all(value == "PASS" for value in result["stages"].values()), result)
            self.assertEqual(result["counts"]["compiled"]["components"], 2)
            self.assertEqual(result["counts"]["compiled"]["pins"], 4)
            self.assertEqual(result["counts"]["exported"]["components"], 2)
            self.assertEqual(result["counts"]["routed"]["nets"], 3)
            self.assertGreater(result["timings_ms"]["compiler_process_wall"], 0)
            self.assertGreater(result["timings_ms"]["route_wall"], 0)
            for stage in ("layout", "pin_resolution", "net_building", "validation", "routing", "optimization", "export"):
                self.assertIn(stage, result["pipeline_metrics"]["stagesMs"])
            self.assertTrue((root / "run/circuit.asc").exists())

    def test_runner_writes_enriched_catalog_and_reference_indexes(self):
        source = json.loads((BACKEND / "circuits/rc_low_pass_filter.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case = self.case(source, root)
            case["origins"] = []
            catalog = {"schema_version": corpus.SCHEMA_VERSION, "cases": [case],
                       "summary": {"total_cases": 1}, "limitations": []}
            corpus.write_json(root / "catalog.json", catalog)
            output, report = corpus.test_corpus(root / "catalog.json", root / "run", timeout=20)
            self.assertEqual(report["summary"]["case_status"], {"PASS": 1})
            metadata = report["cases"][0]["catalog_metadata"]
            self.assertEqual(metadata["size_class"], "small")
            self.assertEqual(metadata["component_support"]["counts"]["supported"], 2)
            view = json.loads((output / "indexes/small.json").read_text())
            self.assertEqual(view["count"], 1)
            self.assertEqual((output / "indexes" / view["cases"][0]["input_path"]).resolve(),
                             (root / "input.json").resolve())
            self.assertTrue((output / "validated_catalog.json").is_file())

    def test_invalid_and_frontend_only_cases_keep_actual_compile_counts(self):
        sources = [("INVALID", {"components": [{"reference": "R1", "type": "resistor"}], "wires": [{"from": "R1.999", "to": "GND"}]}),
                   ("UNSUPPORTED", {"components": [{"reference": "V1", "type": "voltage_source"}], "wires": []})]
        for expected, source in sources:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                result = corpus.run_case(self.case(source, root), root, root / "run", timeout=20)
                self.assertEqual(result["overall"], expected, result)
                self.assertEqual(result["counts"]["compiled"]["components"], 1)
                self.assertEqual(result["stages"]["export"], "NOT_RUN")
                self.assertEqual(result["stages"]["route"], "NOT_RUN")
                self.assertIsNone(result["counts"]["exported"])
                if expected == "UNSUPPORTED":
                    self.assertEqual(result["stages"]["compile"], "PASS")
                    self.assertEqual(result["stages"]["bridge"], "FAIL")

    def test_unknown_component_is_unsupported_not_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = {"components": [{"reference": "U1", "type": "LM358"}], "wires": []}
            result = corpus.run_case(self.case(source, root), root, root / "run", timeout=20)
            self.assertEqual(result["overall"], "UNSUPPORTED", result)
            self.assertEqual(result["stages"]["compile"], "FAIL")
            self.assertEqual(result["stages"]["route"], "NOT_RUN")
            self.assertEqual(result["support"], "unsupported")

    def test_cooperative_routing_timeout_finishes_the_route_stage(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(corpus.os.environ, {"SPICECRAFT_ROUTING_SECONDS": "0.000001"}):
            root = Path(directory)
            source = {"components": [{"reference": "R1", "type": "resistor"}, {"reference": "R2", "type": "resistor"}],
                      "wires": [{"from": "R1.2", "to": "R2.1"}]}
            result = corpus.run_case(self.case(source, root), root, root / "run", timeout=20)
            self.assertEqual(result["overall"], "FAIL", result)
            self.assertEqual(result["stages"]["route"], "TIMEOUT")
            self.assertEqual(result["failure_stage"], "route")
            self.assertNotIn("RUNNING", result["stages"].values())
            self.assertFalse((root / "run/circuit.asc").exists())

    def test_backend_rejections_remain_distinct_from_pipeline_failures(self):
        result = {"overall": "FAIL", "support": "supported", "diagnostics": [
            {"severity": "error", "code": "INVALID_VALUE", "pipeline_stage": "input_validation"}]}
        self.assertEqual(corpus.classify_rejection(result), "INVALID")
        for code, stage in [("PIPELINE_TIMEOUT", "validation"), ("RESOURCE_LIMIT", "input_validation"),
                            ("SERIALIZED_TOPOLOGY_DRIFT", "serialized_validation"), ("NO_SAFE_ROUTE", "routing")]:
            with self.subTest(code=code):
                result["diagnostics"] = [{"severity": "error", "code": code, "pipeline_stage": stage}]
                self.assertEqual(corpus.classify_rejection(result), "FAIL")

    def test_invalid_budgets_reject_before_subprocess_or_catalog_read(self):
        for timeout in (0, -1, float("nan"), float("inf"), True):
            with self.subTest(timeout=timeout), patch.object(corpus.subprocess, "Popen") as process:
                with self.assertRaises(ValueError):
                    corpus.run_process([sys.executable], timeout=timeout)
                process.assert_not_called()
                with self.assertRaises(ValueError):
                    corpus.test_corpus("missing.json", timeout=timeout)
        for samples in (0, 101, 1.5, True):
            with self.subTest(samples=samples), self.assertRaises(ValueError):
                corpus.test_corpus("missing.json", samples=samples)

    def test_unsafe_or_duplicate_catalog_ids_cannot_write_outside_output(self):
        for identities in (("../escape",), ("CON",), ("a/b",), ("A", "a")):
            with self.subTest(identities=identities), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                corpus.write_json(root / "catalog.json", {"schema_version": corpus.SCHEMA_VERSION,
                    "cases": [{"id": identity} for identity in identities]})
                with self.assertRaises(ValueError):
                    corpus.test_corpus(root / "catalog.json", root / "run")
                self.assertFalse((root / "run").exists())
                self.assertFalse((root / "escape").exists())

    def test_environment_evidence_only_contains_known_resource_settings(self):
        with patch.dict(corpus.os.environ, {"SPICECRAFT_MAX_COMPONENTS": "100", "SPICECRAFT_SECRET": "private"}):
            settings = corpus.pipeline_environment()
        self.assertEqual("100", settings["SPICECRAFT_MAX_COMPONENTS"])
        self.assertNotIn("SPICECRAFT_SECRET", settings)

    def test_timeout_terminates_subprocess(self):
        result = corpus.run_process([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.1)
        self.assertTrue(result["timeout"])
        self.assertNotEqual(result["returncode"], 0)
        self.assertLess(result["wall_ms"], 10000)

    def test_memory_measurement_is_real_or_explicitly_unavailable(self):
        result = corpus.run_process([sys.executable, "-c", "import time; data=bytearray(b'x'*(16*1024*1024)); time.sleep(0.5)"], timeout=5)
        self.assertEqual(result["returncode"], 0)
        if sys.platform.startswith(("win", "linux")):
            self.assertGreater(result["memory"]["peak_rss_bytes"], 16 * 1024 * 1024)
            self.assertGreater(result["memory"]["observations"], 0)
        else:
            self.assertIsNone(result["memory"]["peak_rss_bytes"])

    def test_compiler_timeout_does_not_claim_route_or_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case = self.case({"components": []}, root)
            process = {"timeout": True, "returncode": -1, "stdout": "", "stderr": "", "wall_ms": 10}
            with patch.object(corpus, "run_process", return_value=process):
                result = corpus.run_case(case, root, root / "run")
            self.assertEqual(result["overall"], "FAIL")
            self.assertEqual(result["stages"]["compile"], "TIMEOUT")
            self.assertEqual(result["stages"]["route"], "NOT_RUN")
            self.assertIsNone(result["counts"]["exported"])

    def test_digest_change_is_detected_before_compilation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case = self.case({"components": []}, root)
            corpus.write_json(root / "input.json", {"components": [None]})
            with patch.object(corpus, "run_process") as process:
                result = corpus.run_case(case, root, root / "run")
            process.assert_not_called()
            self.assertEqual(result["overall"], "FAIL")
            self.assertEqual(result["diagnostics"][0]["code"], "INPUT_DIGEST_MISMATCH")

    def test_unavailable_or_escaping_input_is_a_preserved_case_failure(self):
        for contents in (None, "{broken", '{"components": NaN}'):
            with self.subTest(contents=contents), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                case = self.case({"components": []}, root)
                path = root / "input.json"
                if contents is None:
                    path.unlink()
                else:
                    path.write_text(contents)
                with patch.object(corpus, "run_process") as process:
                    result = corpus.run_case(case, root, root / "run")
                process.assert_not_called()
                self.assertEqual("FAIL", result["overall"])
                self.assertEqual("INPUT_UNAVAILABLE", result["diagnostics"][0]["code"])
                self.assertEqual("input", result["failure_stage"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case = self.case({"components": []}, root)
            case["input"] = "../outside.json"
            with patch.object(corpus, "run_process") as process:
                result = corpus.run_case(case, root, root / "run")
            process.assert_not_called()
            self.assertEqual("INPUT_UNAVAILABLE", result["diagnostics"][0]["code"])

    def test_handled_routing_timeout_cannot_leave_a_running_stage(self):
        result = {"stages": dict.fromkeys(corpus.STAGES, "NOT_RUN") | {"route": "RUNNING", "export": "FAIL"},
                  "diagnostics": [{"severity": "error", "code": "PIPELINE_TIMEOUT", "stage": "export", "pipeline_stage": "routing"}]}
        corpus.settle_stages(result)
        self.assertEqual(result["stages"]["route"], "FAIL")
        self.assertNotIn("RUNNING", result["stages"].values())
        self.assertEqual(result["stages"]["serialized_validation"], "NOT_RUN")

    def test_validated_catalog_preserves_unknown_and_rejected_counts(self):
        catalog = {"cases": [{"id": "bad", "counts": {"components": 1, "pins": None, "nets": None}, "support": "not_tested"},
                             {"id": "unrun", "counts": {"components": 1, "pins": None, "nets": None}, "support": "not_tested"}]}
        report = {"summary": {}, "cases": [{"id": "bad", "overall": "INVALID", "samples": [
            {"counts": {"compiled": {"components": 1, "pins": 2, "nets": 0}}, "support": "invalid_or_unknown",
             "stages": {"serialized_validation": "NOT_RUN"}, "failure_stage": "compile"}]}]}
        result = corpus.execution_catalog(catalog, report)
        self.assertEqual(result["cases"][0]["counts"]["pins"], 2)
        self.assertEqual(result["cases"][0]["overall"], "INVALID")
        self.assertEqual(result["cases"][0]["validation"], ["NOT_RUN"])
        self.assertEqual(result["cases"][1]["support"], "not_tested")
        self.assertIsNone(catalog["cases"][0]["counts"]["pins"])

    def test_summary_separates_cases_attempts_compile_route_and_export(self):
        def sample(compile, route, export, overall):
            return {"overall": overall, "stages": dict.fromkeys(corpus.STAGES, "NOT_RUN") | {"compile": compile, "route": route, "export": export}}
        result = corpus.summarize([
            {"overall": "PASS", "samples": [sample("PASS", "PASS", "PASS", "PASS")] * 2},
            {"overall": "UNSUPPORTED", "samples": [sample("PASS", "NOT_RUN", "NOT_RUN", "UNSUPPORTED")] * 2},
            {"overall": "FAIL", "samples": [sample("PASS", "PASS", "FAIL", "FAIL")] * 2}])
        self.assertEqual(result["cases"], 3)
        self.assertEqual(result["attempts"], 6)
        self.assertEqual(result["successful_cases_by_stage"]["compile"], 3)
        self.assertEqual(result["successful_cases_by_stage"]["route"], 2)
        self.assertEqual(result["successful_cases_by_stage"]["export"], 1)
        self.assertEqual(result["successful_attempts_by_stage"]["export"], 2)


if __name__ == "__main__":
    unittest.main()
