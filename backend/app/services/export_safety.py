"""Check serialized records against the already validated electrical geometry."""
from collections import Counter

from app.services.asc_validation import ERROR, ExportDiagnostic
from app.services.pin_maps import COMPONENT_LIBRARY, PinResolver, get_pin_coordinate, resolve_component_kind
from app.services.regression_validation import parse_asc_semantics
from app.services.production import checkpoint


def validate_serialized_export(text, layouts, geometries, components):
    parsed = parse_asc_semantics(text)
    found = [ExportDiagnostic(ERROR, d['code'], d['error'], component=d.get('component'), pin=d.get('pin'), net=d.get('net'), stage='post_export_validation')
             for d in parsed['diagnostics'] if d['severity'] == ERROR]

    def compare(code, expected, actual):
        if expected != actual:
            found.append(ExportDiagnostic(ERROR, code, 'Serialized ASC differs from the validated internal representation', stage='post_export_validation'))

    expected_components = {}
    for reference, component in components:
        checkpoint()
        layout = layouts[reference]
        expected_components[reference] = (layout['_ltspice_symbol'], tuple(layout['_ltspice_anchor']),
            PinResolver.orientation_string(layout['_ltspice_rotation'], layout['_ltspice_mirror']),
            str(component['value']) if component.get('value') not in (None, '') else None)
    actual_components = {component['reference']: (component['symbol'], tuple(component['anchor']), component['orientation'], component['value']) for component in parsed['components']}
    compare('SERIALIZED_COMPONENT_MISMATCH', expected_components, actual_components)
    compare('SERIALIZED_COMPONENT_COUNT', len(expected_components), len(parsed['components']))
    expected_wires = Counter(tuple(sorted((s.start, s.end))) for net in geometries for s in net.segments)
    actual_wires = Counter(tuple(sorted((tuple(s['start']), tuple(s['end'])))) for s in parsed['wires'])
    compare('SERIALIZED_WIRE_MISMATCH', expected_wires, actual_wires)
    compare('SERIALIZED_FLAG_MISMATCH', Counter((net.name, point) for net in geometries for point in net.flags),
            Counter((flag['name'], tuple(flag['point'])) for flag in parsed['flags']))
    parsed_pins = {(component['reference'], pin): tuple(point) for component in parsed['components'] for pin, point in component['pins'].items()}
    expected_pins = {(reference, pin.id): get_pin_coordinate(layouts[reference], pin.id)
                     for reference, component in components
                     for pin in COMPONENT_LIBRARY[resolve_component_kind(component)].pins}
    compare('SERIALIZED_PIN_SET_MISMATCH', expected_pins, parsed_pins)
    for net in geometries:
        checkpoint()
        for pin in net.pins:
            if parsed_pins.get((pin.component, pin.pin)) != pin.point:
                found.append(ExportDiagnostic(ERROR, 'SERIALIZED_PIN_MISMATCH', 'Serialized symbol does not preserve the required electrical pin coordinate', component=pin.component, pin=pin.pin, net=net.name, stage='post_export_validation'))
    return found
