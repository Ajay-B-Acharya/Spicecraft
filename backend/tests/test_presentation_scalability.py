"""Exact label-overlap scoring must not change when nonoverlap is fast-pathed."""
from itertools import combinations_with_replacement, product
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.export_presentation import _overlap, build_presentation
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

    def test_overlap_matches_area_formula_including_touching_and_zero_area(self):
        intervals = list(combinations_with_replacement((-16, 0, 16, 32), 2))
        boxes = [(x0, y0, x1, y1) for (x0, x1), (y0, y1) in product(intervals, repeat=2)]
        for first, second in product(boxes, repeat=2):
            expected = (max(0, min(first[2], second[2]) - max(first[0], second[0]))
                        * max(0, min(first[3], second[3]) - max(first[1], second[1])))
            self.assertEqual(_overlap(first, second), expected, (first, second))


if __name__ == '__main__':
    unittest.main()
