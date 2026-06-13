from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.ltspice_exporter import generate_asc

BACKEND_ROOT = Path(__file__).resolve().parents[1]
CIRCUITS_DIR = BACKEND_ROOT / "circuits"


class LtspiceExporterTests(unittest.TestCase):
    def _load_circuit(self, filename: str) -> dict:
        return json.loads((CIRCUITS_DIR / filename).read_text(encoding="utf-8"))

    def test_rc_low_pass_filter_export_contains_special_nodes(self) -> None:
        asc = generate_asc(self._load_circuit("rc_low_pass_filter.json"))

        self.assertIn("SYMBOL res", asc)
        self.assertIn("SYMBOL cap", asc)
        self.assertIn("FLAG", asc)
        self.assertIn("VIN", asc)
        self.assertIn("VOUT", asc)
        self.assertIn("0", asc)
        self.assertGreaterEqual(asc.count("WIRE "), 3)

    def test_led_blinker_uses_led_and_transistor_symbols(self) -> None:
        asc = generate_asc(self._load_circuit("led_blinker.json"))

        self.assertIn("SYMBOL led", asc)
        self.assertIn("SYMBOL npn", asc)
        self.assertIn("VCC", asc)
        self.assertIn("0", asc)
        self.assertGreaterEqual(asc.count("WIRE "), 4)

    def test_common_emitter_amplifier_routes_output_and_bias_nodes(self) -> None:
        asc = generate_asc(self._load_circuit("common_emitter_amplifier.json"))

        self.assertIn("SYMBOL npn", asc)
        self.assertIn("VCC", asc)
        self.assertIn("VOUT", asc)
        self.assertIn("0", asc)
        self.assertGreaterEqual(asc.count("WIRE "), 6)


if __name__ == "__main__":
    unittest.main()
