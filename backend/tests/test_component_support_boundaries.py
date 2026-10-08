"""Generic families do not authorize substitution of an unknown device model."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.ltspice_exporter import generate_asc_with_routing
from app.services.pin_maps import resolve_component_kind


class GenericComponentSupportTests(unittest.TestCase):
    def test_unknown_generic_model_never_exports_a_default_symbol(self):
        for kind, value in [('ic', 'LM358'), ('transistor', 'PNP'), ('bjt', 'BC557'),
                            ('ic', 'resistor')]:
            with self.subTest(kind=kind, value=value):
                source = {'components': [{'reference': 'U1', 'type': kind, 'value': value}], 'wires': []}
                asc, diagnostics, routed = generate_asc_with_routing(source)
                self.assertEqual(asc, '')
                self.assertIsNone(routed)
                self.assertTrue(any(d.code in {'UNSUPPORTED_COMPONENT', 'CONFLICTING_COMPONENT_DEFINITION'} for d in diagnostics))

    def test_existing_generic_models_retain_their_verified_kind(self):
        self.assertEqual(resolve_component_kind({'type': 'ic', 'value': 'NE555'}), 'ne555')
        self.assertEqual(resolve_component_kind({'type': 'transistor', 'value': 'BC547'}), 'bc547')
        self.assertEqual(resolve_component_kind({'type': 'bjt', 'value': 'NPN'}), 'bc547')
        self.assertEqual(resolve_component_kind({'type': 'transistor'}), 'bc547')
        self.assertEqual(resolve_component_kind({'type': 'ic'}), 'ne555')


if __name__ == '__main__':
    unittest.main()
