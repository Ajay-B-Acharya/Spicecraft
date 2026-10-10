"""Exact label-overlap scoring must not change when nonoverlap is fast-pathed."""
from itertools import combinations_with_replacement, product
from pathlib import Path
import copy
import json
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.export_presentation import _overlap, _nearby_obstacles, _choose_windows, _Symbol, build_presentation
from app.services.production import Execution, PipelineError, PipelineLimits, execution_context


class PresentationOverlapTests(unittest.TestCase):
    def test_label_scoring_honors_pipeline_deadline(self):
        execution = Execution(PipelineLimits(), stage='export', started=-100)
        layout = {'R1': {'type': 'resistor', 'reference': 'R1', 'value': '1k',
                         '_inst_name': 'R1', '_ltspice_anchor': (0, 0)}}
        with execution_context(execution), self.assertRaises(PipelineError) as caught:
            build_presentation(layout, [], '', '')
        self.assertEqual(caught.exception.stage, 'export')
        self.assertEqual(caught.exception.diagnostics[0].code, 'PIPELINE_TIMEOUT')

    def test_candidate_filter_preserves_scores_and_order(self):
        obstacles = [((x, y, x + 80, y + 48), weight)
                     for x in range(-800, 1000, 160) for y in range(-800, 1000, 160)
                     for weight in (4, 12)]
        original = copy.deepcopy(obstacles)
        for value in ("", "10k", "MWµΩ\t", "x" * 500):
            labels = ((0, "R1"), (3, value)) if value else ((0, "R1"),)
            for bounds in ((0, 0, 32, 80), (-73, 121, 7, 153), (0, 0, 0, 0)):
                with self.subTest(value=value, bounds=bounds):
                    symbol = _Symbol("R1", (0, 0), 0, False, bounds, labels)
                    nearby = _nearby_obstacles(symbol, obstacles)
                    self.assertEqual(_choose_windows(symbol, obstacles), _choose_windows(symbol, nearby))
        self.assertEqual(original, obstacles)
        symbol = _Symbol("R1", (0, 0), 0, False, (0, 0, 32, 80), ((0, "R1"), (3, "10k")))
        self.assertLess(len(_nearby_obstacles(symbol, obstacles)), len(obstacles) // 2)

    def test_all_library_orientations_preserve_presentation(self):
        from app.services.pin_maps import COMPONENT_LIBRARY
        layouts = {}
        for index, definition in enumerate(COMPONENT_LIBRARY.values()):
            for rotation in definition.supported_rotations:
                for mirrored in (False, True):
                    reference = f"{definition.prefix}{len(layouts) + 1}"
                    layouts[reference] = {"type": definition.kind, "value": definition.default_value,
                        "_inst_name": reference, "_ltspice_symbol": definition.symbol,
                        "_ltspice_anchor": (index * 512, len(layouts) * 256),
                        "_ltspice_rotation": rotation, "_ltspice_mirror": mirrored}
        original = copy.deepcopy(layouts)
        filtered = build_presentation(layouts, [], "All orientations", "")
        with patch("app.services.export_presentation._nearby_obstacles", side_effect=lambda symbol, obstacles: obstacles):
            exhaustive = build_presentation(layouts, [], "All orientations", "")
        self.assertEqual(exhaustive, filtered)
        self.assertEqual(original, layouts)

    def test_existing_source_exports_are_byte_identical_without_filter(self):
        from app.services.ltspice_exporter import generate_asc
        for path in sorted((Path(__file__).resolve().parents[1] / "circuits").glob("*.json")):
            with self.subTest(circuit=path.name):
                source = json.loads(path.read_text())
                filtered = generate_asc(source)
                with patch("app.services.export_presentation._nearby_obstacles", side_effect=lambda symbol, obstacles: obstacles):
                    exhaustive = generate_asc(source)
                self.assertEqual(exhaustive, filtered)

    def test_overlap_matches_area_formula_including_touching_and_zero_area(self):
        intervals = list(combinations_with_replacement((-16, 0, 16, 32), 2))
        boxes = [(x0, y0, x1, y1) for (x0, x1), (y0, y1) in product(intervals, repeat=2)]
        for first, second in product(boxes, repeat=2):
            expected = (max(0, min(first[2], second[2]) - max(first[0], second[0]))
                        * max(0, min(first[3], second[3]) - max(first[1], second[1])))
            self.assertEqual(_overlap(first, second), expected, (first, second))


if __name__ == '__main__':
    unittest.main()
