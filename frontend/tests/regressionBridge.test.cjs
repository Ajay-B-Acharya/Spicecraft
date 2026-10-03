'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { compileCircuit, compileRequest, SHARED_EXPORT_TYPES } = require('../tools/compile-regression.cjs');
const { load, root } = require('../tools/load-typescript.cjs');
const { CircuitCompiler } = load(path.join(root, 'lib/circuit/engine/CircuitCompiler'));
const { componentLibrary } = load(path.join(root, 'lib/circuit/engine/ComponentLibrary'));
const { canonicalLabel, isLabelConnection, LABEL_COMPONENT_PREFIX } = load(path.join(root, 'lib/circuit/engine/NetBuilder'));
const project = path.resolve(root, '..');
const cli = path.join(root, 'tools/compile-regression.cjs');
const component = (id, type = 'resistor', value = '1k') => ({ id, reference: id, type, value });
const circuit = (wires = [], components = [component('R1'), component('R2')]) => ({ components, wires });
const hasCode = (result, code) => result.diagnostics.some(diagnostic => diagnostic.code === code);
const requireValid = result => assert.equal(result.valid, true, JSON.stringify(result.diagnostics));
const deepFreeze = value => {
  if (value && typeof value === 'object') {
    Object.freeze(value);
    Object.values(value).forEach(deepFreeze);
  }
  return value;
};
const fixturePaths = [
  ...fs.readdirSync(path.join(project, 'backend/circuits')).filter(file => file.endsWith('.json'))
    .map(file => path.join(project, 'backend/circuits', file)),
  ...fs.readdirSync(path.join(project, 'backend/tests/fixtures/routing')).filter(file => file.endsWith('.json'))
    .map(file => path.join(project, 'backend/tests/fixtures/routing', file)),
];
const fixtures = fixturePaths.map(filename => ({
  key: path.basename(filename, '.json'), input: JSON.parse(fs.readFileSync(filename, 'utf8')),
}));

function expectedEndpoint(endpoint, mapping) {
  return isLabelConnection(endpoint)
    ? canonicalLabel(endpoint.componentId.slice(LABEL_COMPONENT_PREFIX.length))
    : `${mapping.get(endpoint.componentId)}.${endpoint.pinId}`;
}

for (const { key, input } of fixtures) {
  test(`existing JSON ${key}: bridge exactly translates the actual compiler output`, () => {
    const source = deepFreeze(structuredClone(input));
    const before = JSON.stringify(source);
    const compiled = CircuitCompiler.compile(source);
    const result = compileCircuit(source, key);
    requireValid(result);
    assert.equal(result.compiler_valid, true);
    assert.equal(result.key, key);
    assert.deepEqual(result.components, compiled.components);
    assert.deepEqual(result.connections, compiled.connections);
    assert.deepEqual(result.resolved_pins, compiled.resolvedPins);
    assert.equal(result.backend.name, input.name);
    assert.equal(result.backend.description, input.description);
    assert.equal(result.identity_mapping.length, compiled.components.length);
    const mapping = new Map(result.identity_mapping.map(item => [item.compiled_id, item.backend_id]));
    assert.deepEqual(result.backend.wires, compiled.connections.map(connection => ({
      from: expectedEndpoint(connection.source, mapping),
      to: expectedEndpoint(connection.target, mapping),
      ...(connection.id === undefined ? {} : { id: connection.id }),
    })));
    assert.deepEqual(result.topology.map(net => net.pins), compiled.nets.map(net =>
      net.pins.map(pin => expectedEndpoint(pin, mapping)).sort()));
    assert.deepEqual(result.value_drift, []);
    assert.ok(Number.isFinite(result.duration_ms) && result.duration_ms >= 0);
    assert.equal(JSON.stringify(source), before);
  });
}

test('coverage enumerates all eleven frontend definitions, six shared kinds and actual pin counts', () => {
  assert.equal(fixtures.length, 7);
  const { circuits, coverage } = compileRequest({ circuits: fixtures });
  const definitions = componentLibrary.list();
  assert.deepEqual(coverage.frontend_supported_names, definitions.map(definition => definition.type));
  assert.deepEqual(coverage.shared_export_types, SHARED_EXPORT_TYPES);
  assert.deepEqual(coverage.unsupported_shared_export,
    ['inductor', 'pnp_transistor', 'voltage_source', 'current_source', 'ground']);
  assert.equal(coverage.definition_count, 11);
  assert.equal(coverage.definition_pin_count, 29);
  assert.equal(coverage.shared_definition_count, 6);
  assert.equal(coverage.shared_definition_pin_count, 19);
  assert.equal(coverage.valid_circuit_count, 7);
  assert.equal(coverage.component_count, circuits.reduce((sum, item) => sum + item.components.length, 0));
  assert.equal(coverage.pin_count, circuits.reduce((sum, item) => sum + item.counts.pins, 0));
  assert.equal(coverage.component_count, coverage.by_type.reduce((sum, item) => sum + item.component_count, 0));
  assert.equal(coverage.pin_count, coverage.by_type.reduce((sum, item) => sum + item.pin_count, 0));
  assert.ok(coverage.by_type.filter(item => item.shared_export).every(item => item.component_count > 0));
  for (const definition of circuits[0].pin_definitions) {
    const actual = componentLibrary.getDefinition(definition.type);
    assert.equal(definition.pin_count, actual.pins.length);
    assert.equal(definition.coordinate_space, 'frontend_symbol_local');
    assert.deepEqual(definition.pins, actual.pins.map(pin => ({ ...pin, orientation: pin.direction ?? null })));
  }
  assert.match(coverage.coordinate_note, /logical pin IDs, not physical offsets/);
  const resistor = circuits[0].pin_definitions.find(definition => definition.type === 'resistor');
  assert.deepEqual(resistor.pins.map(pin => [pin.x, pin.y]), [[-32, 0], [32, 0]]);
});

test('both compiler envelopes preserve outer metadata and prefer explicit circuit metadata', () => {
  const source = circuit([{ from: 'R1.2', to: 'R2.1' }]);
  for (const wrap of [value => ({ circuit: value }), value => ({ data: { circuit: value } })]) {
    const input = { name: 'Envelope title', description: 'Envelope description', ...wrap(source) };
    const result = compileCircuit(input);
    requireValid(result);
    assert.equal(result.backend.name, input.name);
    assert.equal(result.backend.description, input.description);
    assert.deepEqual(result.backend.wires, [{ from: 'R1.2', to: 'R2.1' }]);
    const inner = compileCircuit({ name: 'Outer', ...wrap({ ...source, name: 'Inner', description: '' }) });
    assert.equal(inner.backend.name, 'Inner');
    assert.equal(inner.backend.description, '');
  }
  const result = compileCircuit({ data: { name: 'Data name', description: 'Data description', circuit: source } });
  assert.equal(result.backend.name, 'Data name');
  assert.equal(result.backend.description, 'Data description');
  const sibling = compileCircuit({ name: 'Envelope', circuit: source, data: { name: 'Unrelated data' } });
  assert.equal(sibling.backend.name, 'Envelope');
});

test('endpoint objects, pin aliases and React Flow handles are normalized only by the compiler', () => {
  const source = circuit([
    { from: { componentId: 'part', pinId: 'base', name: 'descriptive only' }, to: { componentId: 'R1', pinId: 'right' } },
    { source: 'part', sourceHandle: '3', target: 'R1', targetHandle: '1' },
    { from: { componentId: 'part', pinId: 'collector' }, to: { label: 'out' } },
  ], [{ ...component('part', 'transistor', 'BC547'), reference: 'Q1' }, component('R1')]);
  const result = compileCircuit(source);
  requireValid(result);
  assert.deepEqual(result.backend.wires, [
    { from: 'Q1.B', to: 'R1.2' }, { from: 'Q1.E', to: 'R1.1' }, { from: 'Q1.C', to: 'VOUT' },
  ]);
  assert.equal(result.components[0].type, 'npn_transistor');
  assert.equal(result.backend.components[0].type, 'transistor');
});

test('ground aliases share real NetBuilder identity without extra wires or nets', () => {
  const result = compileCircuit(circuit([
    { from: 'R1.1', to: 'ground' }, { from: 'R2.1', to: '0' },
    { from: 'R1.2', to: 'a' }, { from: 'R2.2', to: 'b' },
  ]));
  requireValid(result);
  assert.deepEqual(result.backend.wires, [
    { from: 'R1.1', to: 'GND' }, { from: 'R2.1', to: 'GND' },
    { from: 'R1.2', to: 'a' }, { from: 'R2.2', to: 'b' },
  ]);
  assert.equal(result.topology.length, 3);
  assert.equal(result.backend.wires.length, result.connections.length);
  assert.deepEqual(result.topology.find(net => net.labels.includes('GND')).pins, ['R1.1', 'R2.1']);
});

test('invalid pins block backend output, preserving compiler diagnostics and defined pins', () => {
  const result = compileCircuit(circuit([{ from: 'R1.999', to: 'R2.1' }]));
  assert.equal(result.compiler_valid, false);
  assert.equal(result.valid, false);
  assert.equal(result.backend, null);
  assert.ok(result.diagnostics.some(item => item.stage === 'compiler' && /invalid pin/.test(item.message)));
  assert.deepEqual(result.components[0].pins.map(pin => pin.id), ['1', '2']);
});

for (const [inputType, compiledType] of [
  ['voltage', 'voltage_source'], ['inductor', 'inductor'], ['pnp', 'pnp_transistor'],
  ['ground', 'ground'], ['current', 'current_source'],
]) {
  test(`frontend-only ${inputType} is explicitly invalid for shared export, never a resistor fallback`, () => {
    const result = compileCircuit(circuit([], [component('X1', inputType)]));
    assert.equal(result.compiler_valid, true);
    assert.equal(result.components[0].type, compiledType);
    assert.equal(result.valid, false);
    assert.equal(result.backend, null);
    assert.ok(hasCode(result, 'UNSUPPORTED_SHARED_EXPORT_KIND'));
    assert.ok(result.pin_definitions.some(definition => definition.type === compiledType && !definition.shared_export));
  });
}

test('compiled id to original reference mapping is explicit in components, wires and topology', () => {
  const source = circuit([
    { from: 'node-a.2', to: 'R2.1' }, { from: 'R1.1', to: 'ground' },
  ], [{ ...component('node-a'), reference: 'R1' }, { ...component('node-b'), reference: 'R2' }]);
  const result = compileCircuit(source);
  requireValid(result);
  assert.deepEqual(result.components.map(item => item.id), ['node-a', 'node-b']);
  assert.deepEqual(result.backend.components.map(item => [item.id, item.reference]), [['R1', 'R1'], ['R2', 'R2']]);
  assert.deepEqual(result.identity_mapping, [
    { compiled_id: 'node-a', backend_id: 'R1', source_index: 0, source_id: 'node-a', source_reference: 'R1', generated_by_compiler: false },
    { compiled_id: 'node-b', backend_id: 'R2', source_index: 1, source_id: 'node-b', source_reference: 'R2', generated_by_compiler: false },
  ]);
  assert.deepEqual(result.backend.wires, [{ from: 'R1.2', to: 'R2.1' }, { from: 'R1.1', to: 'GND' }]);
  assert.deepEqual(result.topology[0].pins, ['R1.2', 'R2.1']);
  assert.deepEqual(result.topology[0].compiled_pins, ['node-a.2', 'node-b.1']);
});

test('source object remains deeply immutable, including envelope, geometry and endpoints', () => {
  const input = deepFreeze({ name: 'Outer', data: { circuit: circuit([
    { from: { componentId: 'part', pinId: 'left' }, to: { net: '0' } },
  ], [{ ...component('part'), reference: 'R1', position: { x: 15, y: 30 }, rotation: 90, mirror: true }]) } });
  const before = JSON.stringify(input);
  requireValid(compileCircuit(input));
  assert.equal(JSON.stringify(input), before);
});

test('actual library defaults and compiler value normalization are reported, never rewritten', () => {
  const source = circuit([], [
    { id: 'R1', type: 'resistor' }, { id: 'C1', type: 'capacitor', value: '' },
    { id: 'R2', type: 'resistor', value: 1000 }, { id: 'R3', type: 'resistor', value: ' 2k ' },
  ]);
  const result = compileCircuit(source);
  requireValid(result);
  assert.deepEqual(result.backend.components.map(item => item.value),
    CircuitCompiler.compile(source).components.map(item => item.value));
  assert.equal(result.backend.components[0].value, componentLibrary.getDefinition('resistor').defaultValue);
  assert.equal(result.value_drift.length, 4);
  assert.deepEqual(result.value_drift.map(item => item.reason),
    ['compiler_default', 'compiler_default', 'compiler_normalization', 'compiler_normalization']);
  assert.equal(result.value_drift[0].source_present, false);
  assert.equal(result.value_drift[1].source_value, '');
  assert.ok(hasCode(result, 'VALUE_DRIFT'));
});

test('compiler-generated references remain deterministic and mapped without inventing source aliases', () => {
  const input = { nodes: [component('R1'), { type: 'resistor' }, { type: 'capacitor' }], edges: [] };
  const first = compileCircuit(input), second = compileCircuit(input);
  requireValid(first);
  assert.deepEqual(first.backend, second.backend);
  assert.deepEqual(first.identity_mapping.map(item => [item.compiled_id, item.generated_by_compiler]),
    [['R1', false], ['R2', true], ['C1', true]]);
});

test('duplicate identities and ambiguous source aliases fail closed', () => {
  for (const components of [
    [component('R1'), component('R1')],
    [{ ...component('a'), reference: 'R1' }, { ...component('b'), reference: 'R1' }],
    [{ ...component('a'), reference: 'b' }, component('b')],
  ]) {
    const result = compileCircuit(circuit([], components));
    assert.equal(result.compiler_valid, false);
    assert.equal(result.valid, false);
    assert.equal(result.backend, null);
  }
  assert.ok(hasCode(compileCircuit(circuit([], [component('R1'), component('R1')])), 'AMBIGUOUS_SOURCE_IDENTITY'));
});

test('case-sensitive compiler identities are distinguished from case-insensitive backend export gate', () => {
  const direct = compileCircuit(circuit([], [component('R1'), component('r1')]));
  assert.equal(direct.compiler_valid, true);
  assert.equal(direct.valid, false);
  assert.equal(direct.backend, null);
  assert.ok(hasCode(direct, 'INSTANCE_NAME_COLLISION'));
  const references = compileCircuit(circuit([], [
    { ...component('node1'), reference: 'Q1' }, { ...component('node2'), reference: 'q1' },
  ]));
  assert.equal(references.compiler_valid, true);
  assert.ok(hasCode(references, 'INSTANCE_NAME_COLLISION'));
  const distinct = compileCircuit(circuit([], [
    { ...component('a'), reference: 'R1' }, { ...component('A'), reference: 'R2' },
  ]));
  requireValid(distinct);
  assert.deepEqual(distinct.identity_mapping.map(item => item.compiled_id), ['a', 'A']);
});

test('backend token restrictions reject ambiguous dotted or whitespace references and labels', () => {
  for (const reference of ['R.1', 'R 1', 'R\u00011']) {
    const result = compileCircuit(circuit([], [{ ...component('node'), reference }]));
    assert.equal(result.valid, false);
    assert.equal(result.backend, null);
    assert.ok(hasCode(result, 'INVALID_BACKEND_IDENTITY'));
  }
  const label = compileCircuit(circuit([{ from: 'R1.1', to: { label: 'signal.with.dot' } }]));
  assert.equal(label.backend, null);
  assert.ok(hasCode(label, 'INVALID_COMPILED_LABEL'));
});

test('missing references and malformed circuits never yield a partial export', () => {
  for (const input of [null, { components: {} }, circuit([{ from: 'R99.1', to: 'R1.1' }]), circuit([{ from: 'R1.1' }])]) {
    const result = compileCircuit(input);
    assert.equal(result.valid, false);
    assert.equal(result.backend, null);
    assert.ok(result.diagnostics.some(item => item.severity === 'error'));
  }
});

test('bridge reads wires only inside the actual compiler, then exports its canonical connections', () => {
  // The getter fails if the bridge consults source wires after compilation.
  const input = circuit([{ from: 'R1.left', to: 'ground' }]);
  const actualCompile = CircuitCompiler.compile;
  let compiled = false;
  const wires = input.wires;
  Object.defineProperty(input, 'wires', { get() {
    assert.equal(compiled, false, 'bridge must not re-read source wires');
    return wires;
  } });
  CircuitCompiler.compile = source => {
    const result = actualCompile.call(CircuitCompiler, source);
    compiled = true;
    return result;
  };
  try {
    const result = compileCircuit(input);
    requireValid(result);
    assert.deepEqual(result.backend.wires, [{ from: 'R1.1', to: 'GND' }]);
  } finally {
    CircuitCompiler.compile = actualCompile;
  }
});

test('unexpected unmapped compiler identities fail rather than guessing a source reference', () => {
  const actualCompile = CircuitCompiler.compile;
  CircuitCompiler.compile = source => {
    const compiled = actualCompile.call(CircuitCompiler, source);
    compiled.components[0].id = 'not-a-source-id';
    return compiled;
  };
  try {
    const result = compileCircuit(circuit([{ from: 'R1.1', to: 'R2.1' }]));
    assert.equal(result.valid, false);
    assert.equal(result.backend, null);
    assert.ok(hasCode(result, 'UNMAPPED_SOURCE_IDENTITY'));
    assert.ok(hasCode(result, 'UNMAPPED_COMPILED_REFERENCE'));
  } finally {
    CircuitCompiler.compile = actualCompile;
  }
});

test('CLI accepts batch JSON with clean stdout, no auth and no working-directory assumptions', () => {
  const child = spawnSync(process.execPath, [cli], {
    cwd: path.join(project, 'backend'),
    input: JSON.stringify({ circuits: fixtures, ignoredOption: true }),
    encoding: 'utf8',
    env: { ...process.env, FIREBASE_API_KEY: '', OPENAI_API_KEY: '' },
  });
  assert.equal(child.status, 0, child.stderr);
  assert.equal(child.stderr, '');
  const output = JSON.parse(child.stdout);
  assert.equal(output.circuits.length, 7);
  assert.equal(output.coverage.valid_circuit_count, 7);
  assert.equal(child.stdout.trim().split('\n').length, 1);
});

test('CLI reports invalid circuits as data and malformed request as structured JSON with exit 1', () => {
  const invalidCircuit = spawnSync(process.execPath, [cli], {
    input: JSON.stringify({ circuits: [{ key: 'bad', input: null }] }), encoding: 'utf8',
  });
  assert.equal(invalidCircuit.status, 0);
  assert.equal(JSON.parse(invalidCircuit.stdout).circuits[0].backend, null);
  for (const input of ['not JSON', '{}', '{"circuits":[{}]}']) {
    const child = spawnSync(process.execPath, [cli], { input, encoding: 'utf8' });
    assert.equal(child.status, 1);
    assert.equal(child.stderr, '');
    const result = JSON.parse(child.stdout);
    assert.deepEqual(result.circuits, []);
    assert.equal(result.diagnostics[0].code, 'INVALID_REQUEST');
  }
});

test('request keys must be explicit and unique; repeated compilation does not share mutable results', () => {
  assert.throws(() => compileRequest({ circuits: [{ input: {} }] }), /key/);
  assert.throws(() => compileRequest({ circuits: [{ key: 'x', input: {} }, { key: 'x', input: {} }] }), /Duplicate/);
  const first = compileRequest({ circuits: [{ key: 'x', input: circuit() }] });
  first.circuits[0].pin_definitions[0].pins[0].id = 'mutated';
  first.circuits[0].components[0].pins[0].id = 'mutated';
  const second = compileRequest({ circuits: [{ key: 'x', input: circuit() }] });
  assert.equal(second.circuits[0].pin_definitions[0].pins[0].id, '1');
  assert.equal(second.circuits[0].components[0].pins[0].id, '1');
});
