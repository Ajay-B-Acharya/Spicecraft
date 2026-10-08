"""Bound untrusted circuit data before allocating electrical or routing models."""
from __future__ import annotations

import json
import math
import re

from app.services.production import Execution, PipelineError
from app.services.pin_maps import COMPONENT_LIBRARY, COMPONENT_KIND_ALIASES, resolve_component_kind

_TOKEN = re.compile(r'[A-Za-z][A-Za-z0-9_$-]*\Z')
_VALUE = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?(?:[a-zA-ZµΩ]*)\Z')


def validate_input(circuit, execution: Execution):
    limits = execution.limits

    def fail(code, message, component=None):
        raise PipelineError(code, message, stage='input_validation', circuit=execution.circuit_id, component=component)

    if not isinstance(circuit, dict):
        fail('INVALID_CIRCUIT', 'Circuit must be an object')
    # Iterative traversal rejects cycles/deep metadata before serializers or builders recurse.
    active = set()
    stack = [(circuit, 0, False)]
    items = 0
    while stack:
        value, depth, exiting = stack.pop()
        if exiting:
            active.remove(id(value))
            continue
        items += 1
        execution.require('input_items', items)
        execution.require('input_depth', depth)
        execution.check()
        if isinstance(value, (dict, list)):
            if id(value) in active:
                fail('CYCLIC_INPUT', 'Circuit JSON must not contain circular references')
            active.add(id(value))
            stack.append((value, depth, True))
            execution.require('input_items', items + len(stack) + len(value))
            children = value.values() if isinstance(value, dict) else value
            if isinstance(value, dict):
                for key in value:
                    if not isinstance(key, str) or len(key) > limits.max_string_length or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in key):
                        fail('INVALID_METADATA', 'Object keys must be bounded strings without control characters')
            stack.extend((child, depth + 1, False) for child in children)
        elif isinstance(value, str):
            execution.require('string_length', len(value))
            if any(0xD800 <= ord(c) <= 0xDFFF for c in value):
                fail('INVALID_STRING', 'Strings must contain valid Unicode scalar values')
            if any(ord(c) < 32 and c not in '\r\n\t' for c in value):
                fail('INVALID_STRING', 'Strings must not contain control characters')
        elif isinstance(value, (float, int)) and not isinstance(value, bool):
            if isinstance(value, float) and not math.isfinite(value):
                fail('INVALID_NUMBER', 'Numbers must be finite')
            if isinstance(value, int) and value.bit_length() > 64:
                fail('INVALID_NUMBER', 'Integer exceeds supported range')
        elif value is not None and not isinstance(value, bool):
            fail('INVALID_JSON_VALUE', 'Circuit data must contain only JSON values')

    encoded_size = 0
    for chunk in json.JSONEncoder(ensure_ascii=False, allow_nan=False, separators=(',', ':')).iterencode(circuit):
        execution.check()
        encoded_size += len(chunk.encode('utf-8'))
        execution.require('input_bytes', encoded_size)

    components = circuit.get('components')
    if not isinstance(components, list) or not components:
        fail('INVALID_COMPONENTS', 'Circuit must contain a nonempty components list')
    wires = circuit.get('wires', [])
    if not isinstance(wires, list):
        fail('INVALID_WIRES', 'Circuit wires must be a list (empty or omitted means unwired)')
    if any(key in circuit for key in ('nets', 'connections')):
        fail('UNSUPPORTED_CONNECTIVITY_FORMAT', 'Normalize nets/connections into explicit wires before backend export')
    execution.counts['componentCount'] = len(components)
    execution.require('components', len(components))
    execution.require('wires', len(wires))
    for key in ('id', 'name', 'description', 'category'):
        if key in circuit and not isinstance(circuit[key], str):
            fail('INVALID_METADATA', f'{key} must be a string')
    pin_count = 0
    for index, component in enumerate(components):
        if not isinstance(component, dict):
            fail('INVALID_COMPONENT', f'Component #{index + 1} must be an object')
        reference = component.get('reference') or component.get('id')
        if not isinstance(reference, str) or not _TOKEN.fullmatch(reference):
            fail('INVALID_COMPONENT_IDENTITY', 'Component reference must start with a letter and contain only letters, digits, _, $, or -')
        for key in ('id', 'reference'):
            if key in component and (not isinstance(component[key], str) or not _TOKEN.fullmatch(component[key])):
                fail('INVALID_COMPONENT_IDENTITY', f'{key} must be a valid component token', reference)
        kind = resolve_component_kind(component)
        raw_type = component.get('type')
        if not isinstance(raw_type, str) or not raw_type.strip():
            fail('INVALID_COMPONENT_TYPE', 'Component must specify its type', reference)
        # Generic legacy transistor/IC types may resolve by a verified model value.
        known_type = raw_type.strip().lower() in COMPONENT_KIND_ALIASES
        generic_type = raw_type.strip().lower() in {'transistor', 'ic'}
        if kind not in COMPONENT_LIBRARY or not (known_type or generic_type):
            fail('UNSUPPORTED_COMPONENT', f'Component type {raw_type!r} (value {component.get("value")!r}) is not currently supported by SpiceCraft', reference)
        pin_count += len(COMPONENT_LIBRARY[kind].pins)
        execution.require('pins', pin_count)
        value = component.get('value')
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, (str, int, float)):
                fail('INVALID_VALUE', 'Component value must be a string or finite number', reference)
            text = str(value)
            if any(c in text for c in '\r\n\x00'):
                fail('INVALID_ATTRIBUTE', 'Component value must not contain ASC record separators', reference)
            if text and kind in {'resistor', 'capacitor'} and not _VALUE.fullmatch(text.strip()):
                fail('INVALID_VALUE', 'Passive component value must be numeric with an optional unit suffix', reference)
        for key in ('x', 'y', 'rotation'):
            if key in component:
                coordinate = component[key]
                if isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)) or abs(coordinate) > limits.max_coordinate:
                    fail('INVALID_COORDINATE', f'{key} must be a finite bounded number', reference)
        if 'position' in component:
            position = component['position']
            if not isinstance(position, dict) or any(isinstance(position.get(axis), bool) or not isinstance(position.get(axis), (int, float)) or abs(position[axis]) > limits.max_coordinate for axis in ('x', 'y')):
                fail('INVALID_COORDINATE', 'Position must contain finite bounded x and y coordinates', reference)
    execution.counts['pinCount'] = pin_count
