"""Hand-computable evidence metrics without optional imaging dependencies."""
from __future__ import annotations

import ast
import copy
from pathlib import Path
import sys
import unittest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services.asc_validation import NetGeometry, PinPoint, WireSegment
from app.services.routing.metrics import measure_routing
from tools.export_polish_report import EvidenceError, assign_serialized_wires, canonical_coverage


class ExportEvidenceMetricsTests(unittest.TestCase):
    def test_inspection_renderer_accepts_vertical_center_and_edge_windows(self):
        # Exercise the pure alignment function without requiring optional Pillow.
        module = ast.parse((BACKEND / "tools/render_asc.py").read_text(encoding="utf-8"))
        function = next(node for node in module.body if isinstance(node, ast.FunctionDef)
                        and node.name == "_alignment")
        namespace = {"Instance": object}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "render_asc.py", "exec"), namespace)
        for alignment in ("Center", "Left", "Right", "Top", "Bottom"):
            self.assertEqual(namespace["_alignment"]("V" + alignment), alignment)

    def test_interval_union_preserves_gaps_axes_and_reversed_duplicates(self):
        wires = [((0, 0), (32, 0)), ((48, 0), (16, 0)), ((32, 0), (0, 0)),
                 ((64, 0), (80, 0)), ((0, 0), (0, 16)), ((0, 0), (0, 0))]
        self.assertEqual(canonical_coverage(wires),
                         [["h", 0, 0, 48], ["h", 0, 64, 80], ["v", 0, 0, 16]])

    def test_assignment_accepts_merged_and_subdivided_coverage_without_mutation(self):
        reference = [NetGeometry("signal", pins=[PinPoint("R1", "1", (0, 0))],
                                flags=[(64, 0)], segments=[
                                    WireSegment("signal", (0, 0), (32, 0)),
                                    WireSegment("signal", (32, 0), (64, 0))])]
        snapshot = copy.deepcopy(reference)
        assigned = assign_serialized_wires([((64, 0), (0, 0))], reference)
        self.assertEqual(len(assigned[0].segments), 1)
        self.assertEqual(assigned[0].segments[0].net, "signal")
        self.assertEqual(reference, snapshot)
        self.assertEqual(measure_routing(assigned)["total_length"], 64)
        self.assertEqual(measure_routing(assigned)["bend_count"], 0)

    def test_missing_extra_diagonal_and_ambiguous_paths_fail(self):
        net = NetGeometry("a", segments=[WireSegment("a", (0, 0), (64, 0))])
        for wires in ([((0, 0), (32, 0))], [((0, 16), (64, 16))], [((0, 0), (64, 16))]):
            with self.subTest(wires=wires), self.assertRaises(ValueError):
                assign_serialized_wires(wires, [net])
        foreign = NetGeometry("b", segments=[WireSegment("b", (0, 0), (64, 0))])
        with self.assertRaises(EvidenceError):
            assign_serialized_wires([((0, 0), (64, 0))], [net, foreign])

    def test_bends_junctions_and_records_are_independent(self):
        net = NetGeometry("a", segments=[WireSegment("a", a, b) for a, b in [
            ((0, 0), (32, 0)), ((32, 0), (64, 0)), ((32, 0), (32, 32)),
            ((64, 0), (64, 32)), ((64, 32), (96, 32))]])
        metrics = measure_routing([net])
        self.assertEqual((metrics["total_length"], metrics["segment_count"],
                          metrics["bend_count"], metrics["junction_count"]), (160, 5, 2, 1))


if __name__ == "__main__":
    unittest.main()
