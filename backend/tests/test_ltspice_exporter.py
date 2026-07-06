from __future__ import annotations

import json
import re
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

    def assert_flag(self, asc: str, net: str) -> None:
        pattern = rf"^FLAG\s+-?\d+\s+-?\d+\s+{re.escape(net)}$"
        self.assertIsNotNone(re.search(pattern, asc, re.MULTILINE))

    def assert_not_floating_special_text(self, asc: str) -> None:
        pattern = r"^TEXT\s+.*;(?:VCC|GND|VIN|VOUT|OUT|IN)$"
        self.assertIsNone(re.search(pattern, asc, re.MULTILINE))

    def test_rc_low_pass_filter_export_contains_special_nodes(self) -> None:
        asc = generate_asc(self._load_circuit("rc_low_pass_filter.json"))

        self.assertIn("SYMBOL res", asc)
        self.assertIn("SYMBOL cap", asc)
        self.assert_flag(asc, "VIN")
        self.assert_flag(asc, "VOUT")
        self.assert_flag(asc, "0")
        self.assert_not_floating_special_text(asc)
        self.assertGreaterEqual(asc.count("WIRE "), 3)

    def test_led_blinker_uses_led_and_transistor_symbols(self) -> None:
        asc = generate_asc(self._load_circuit("led_blinker.json"))

        self.assertIn("SYMBOL led", asc)
        self.assertIn("SYMBOL npn", asc)
        self.assert_flag(asc, "VCC")
        self.assert_flag(asc, "0")
        self.assert_not_floating_special_text(asc)
        self.assertGreaterEqual(asc.count("WIRE "), 4)

    def test_common_emitter_amplifier_routes_output_and_bias_nodes(self) -> None:
        asc = generate_asc(self._load_circuit("common_emitter_amplifier.json"))

        self.assertIn("SYMBOL npn", asc)
        self.assert_flag(asc, "VCC")
        self.assert_flag(asc, "VOUT")
        self.assert_flag(asc, "0")
        self.assert_not_floating_special_text(asc)
        self.assertGreaterEqual(asc.count("WIRE "), 6)

    def test_all_bundled_circuits_export_without_special_text_nodes(self) -> None:
        for path in CIRCUITS_DIR.glob("*.json"):
            with self.subTest(circuit=path.name):
                asc = generate_asc(self._load_circuit(path.name))

                self.assertTrue(asc.startswith("Version 4\nSHEET 1 "))
                self.assert_not_floating_special_text(asc)


if __name__ == "__main__":
    unittest.main()
