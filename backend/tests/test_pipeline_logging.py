"""Structured production events retain severity without logging raw circuit data."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.production import Execution, PipelineLimits, circuit_size, log_report


class PipelineLoggingTests(unittest.TestCase):
    def test_size_boundaries_and_missing_counts(self):
        for count, expected in [(1, 'small'), (20, 'small'), (21, 'medium'),
                                (100, 'medium'), (101, 'large'), (500, 'large'),
                                (501, 'extreme'), (0, 'unknown'), (None, 'unknown'),
                                (-1, 'unknown'), (True, 'unknown')]:
            with self.subTest(count=count):
                self.assertEqual(circuit_size(count), expected)
        self.assertEqual(Execution(PipelineLimits()).report()['classification'], 'unknown')

    def test_json_events_use_diagnostic_severity(self):
        for errors, warnings, level in [(0, 0, 'INFO'), (0, 1, 'WARNING'), (1, 1, 'ERROR')]:
            with self.subTest(level=level), self.assertLogs('app.services.production', level='INFO') as captured:
                log_report('pipeline_complete' if not errors else 'pipeline_failed',
                           {'circuitId': 'test', 'errorCount': errors, 'warningCount': warnings})
            self.assertEqual(captured.records[0].levelname, level)
            payload = json.loads(captured.records[0].getMessage())
            self.assertEqual(payload['circuitId'], 'test')
            self.assertEqual(payload['errorCount'], errors)

    def test_default_metrics_contain_no_raw_components_or_wires(self):
        report = Execution(PipelineLimits(), circuit_id='test').report()
        self.assertNotIn('components', report)
        self.assertNotIn('wires', report)
        self.assertIn('stagesMs', report)
        self.assertIn('totalTimeMs', report)


if __name__ == '__main__':
    unittest.main()
