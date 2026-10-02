const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const root = path.resolve(__dirname, '..');
const cache = new Map();
function load(filename) {
  filename = fs.existsSync(filename + '.ts') ? filename + '.ts' : filename;
  if (fs.statSync(filename).isDirectory()) filename = path.join(filename, 'index.ts');
  if (cache.has(filename)) return cache.get(filename).exports;
  const module = { exports: {} };
  cache.set(filename, module);
  const code = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  new Function('require', 'module', 'exports', code)(specifier => {
    if (specifier.startsWith('@/')) return load(path.join(root, specifier.slice(2)));
    if (specifier.startsWith('.')) return load(path.resolve(path.dirname(filename), specifier));
    return require(specifier);
  }, module, module.exports);
  return module.exports;
}
const { CircuitCompiler } = load(path.join(root, 'lib/circuit/engine/CircuitCompiler'));
const { CircuitValidator } = load(path.join(root, 'lib/circuit/engine/CircuitValidator'));
const { PinSystemDebugger } = load(path.join(root, 'lib/circuit/engine/PinSystemDebugger'));
const { visualEdgesToConnections } = load(path.join(root, 'lib/circuit/engine/NetBuilder'));
const { buildCircuitFlow } = load(path.join(root, 'components/circuits/circuitFlowAdapter'));
const sample = JSON.parse(fs.readFileSync(path.join(root, '../backend/circuits/common_emitter_amplifier.json'), 'utf8'));
const component = (id, type = 'resistor') => ({ id, reference: id, type, value: type === 'transistor' ? 'BC547' : '1k' });
const circuit = (wires, components = [component('R1'), component('R2')]) => ({ components, wires });
const compile = source => CircuitCompiler.compile(source);
const partition = compiled => compiled.nets.map(n => n.pins.map(p => `${p.componentId}.${p.pinId}`).sort()).sort((a,b) => JSON.stringify(a).localeCompare(JSON.stringify(b)));
const invalid = source => { const c = compile(source); assert.equal(c.validation.valid, false, JSON.stringify(c.validation)); return c; };

test('resistor and capacitor connections use exact canonical pins', () => {
  for (const type of ['resistor', 'capacitor']) {
    const c = compile(circuit([{ from: 'R1.2', to: 'R2.1' }], [component('R1'), component('R2', type)]));
    assert.equal(c.validation.valid, true);
    assert.deepEqual(partition(c), [['R1.2', 'R2.1']]);
  }
});
test('transistor base collector and emitter remain distinct nets', () => {
  const c = compile(circuit([{ from: 'R1.1', to: 'Q1.base' }, { from: 'R1.2', to: 'Q1.1' }, { from: 'Q1.emitter', to: 'GND' }], [component('R1'), component('Q1', 'transistor')]));
  assert.equal(c.validation.valid, true);
  assert.deepEqual(partition(c), [['Q1.B', 'R1.1'], ['Q1.C', 'R1.2'], ['Q1.E']]);
});
test('multiple edges on a pin form one shared net without duplicate membership', () => {
  const c = compile(circuit([{ from: 'R1.2', to: 'Q1.B' }, { from: 'Q1.base', to: 'R2.1' }], [component('R1'), component('R2'), component('Q1', 'transistor')]));
  assert.equal(c.validation.valid, true);
  assert.deepEqual(partition(c), [['Q1.B', 'R1.2', 'R2.1']]);
});
test('physical coincidence and arbitrary position changes do not merge logical nets', () => {
  const source = circuit([{ from: 'R1.1', to: 'VIN' }, { from: 'R2.1', to: 'OUT' }]);
  const expected = partition(compile(source));
  source.components.forEach(c => { c.position = { x: 0, y: 0 }; c.rotation = 90; });
  assert.deepEqual(partition(compile(source)), expected);
  assert.equal(expected.length, 2);
});
test('missing component and undefined pin fail instead of inventing a connection', () => {
  invalid(circuit([{ from: 'R99.1', to: 'R1.1' }]));
  invalid(circuit([{ from: 'R1.9', to: 'R2.1' }]));
});
test('contradictory and empty endpoint representations fail', () => {
  for (const wire of [
    { source: 'R1.1', from: 'R2.1', to: 'GND' },
    { source: '', from: 'R1.1', to: 'GND' },
    { from: 'R1.1', to: 'GND', destination: 'VCC' },
    { from: 'R1.1' },
  ]) invalid(circuit([wire]));
});
test('equivalent endpoint fields canonicalize before comparison', () => {
  const c = compile(circuit([{ from: 'Q1.base', source: 'Q1.2', to: 'IN', destination: 'VIN' }], [component('Q1', 'transistor')]));
  assert.equal(c.validation.valid, true, c.validation.errors.join('\n'));
  assert.deepEqual(partition(c), [['Q1.B']]);
});
test('React Flow node and handle pairs preserve pin connectivity', () => {
  const c = compile(circuit([{ source: 'R1', sourceHandle: '2', target: 'R2', targetHandle: '1' }]));
  assert.equal(c.validation.valid, true);
  assert.deepEqual(partition(c), [['R1.2', 'R2.1']]);
  invalid(circuit([{ source: 'R1', sourceHandle: '9', target: 'R2', targetHandle: '1' }]));
  invalid(circuit([{ source: 'R1.1', sourceHandle: '2', target: 'R2', targetHandle: '1' }]));
});
test('endpoint object descriptive name does not override component and pin', () => {
  const c = compile(circuit([{ from: { componentId: 'R1', pinId: '2', name: 'description' }, to: { componentId: 'R2', pinId: '1' } }]));
  assert.equal(c.validation.valid, true);
  assert.deepEqual(partition(c), [['R1.2', 'R2.1']]);
});
test('duplicate component IDs and ambiguous reference aliases are rejected', () => {
  invalid(circuit([], [component('R1'), component('R1')]));
  invalid(circuit([], [{ ...component('a'), reference: 'R1' }, { ...component('b'), reference: 'R1' }]));
});
test('generated references are local deterministic and reserve explicit IDs', () => {
  const source = circuit([], [component('R1'), { type: 'resistor', value: '1k' }, { type: 'resistor', value: '2k' }]);
  const a = compile(source), b = compile(source);
  assert.deepEqual(a.components.map(c => c.id), ['R1', 'R2', 'R3']);
  assert.deepEqual(a, b);
});
test('recognized explicit type is not overridden by model-looking value', () => {
  const c = compile(circuit([], [{ ...component('R1'), value: 'BC547' }]));
  assert.equal(c.components[0].type, 'resistor');
  invalid(circuit([], [{ id: 'U1', type: 'ic', value: 'LM358' }]));
});
test('ground aliases share identity and unrelated signal labels remain separate', () => {
  const c = compile(circuit([{ from: 'R1.1', to: 'ground' }, { from: 'R2.1', to: '0' }, { from: 'R1.2', to: 'a' }, { from: 'R2.2', to: 'b' }]));
  assert.equal(c.validation.valid, true);
  assert.equal(c.nets.length, 3);
  assert.ok(c.nets.some(n => n.pins.length === 2));
});
test('explicit supply ground mega-net is rejected without modifying the source', () => {
  const source = circuit([{ from: 'VCC', to: 'R1.1' }, { from: 'R1.1', to: 'GND' }]);
  const before = JSON.stringify(source);
  invalid(source);
  assert.equal(JSON.stringify(source), before);
});
test('valid one-pin external port is not an invalid singleton net', () => {
  const c = compile(circuit([{ from: 'R1.1', to: 'OUT' }]));
  assert.equal(c.validation.valid, true);
  assert.equal(PinSystemDebugger.validateNets(c).valid, true);
});
test('self-connections fail and repeated source pairs warn without duplicate pins', () => {
  invalid(circuit([{ from: 'R1.1', to: 'R1.A' }]));
  const c = compile(circuit([{ from: 'R1.1', to: 'R2.2' }, { from: 'R2.2', to: 'R1.1' }]));
  assert.equal(c.validation.valid, true);
  assert.deepEqual(partition(c), [['R1.1', 'R2.2']]);
  assert.ok(c.validation.warnings.some(w => /duplicate source/i.test(w)));
});
test('net IDs stay distinct from a user label matching an anonymous ID', () => {
  const c = compile(circuit([{ from: 'R1.1', to: 'N2' }, { from: 'R1.2', to: 'R2.1' }]));
  assert.equal(c.validation.valid, true);
  for (const net of c.nets) for (const ref of net.pins) {
    assert.equal(c.components.find(x => x.id === ref.componentId).pins.find(x => x.id === ref.pinId).net, net.id);
  }
});
test('mutated membership detects unexpected floating duplicate and merged pins', () => {
  const c = compile(sample);
  const pin = c.nets[1].pins.pop();
  c.nets[0].pins.push(pin);
  assert.equal(CircuitValidator.validate(c).valid, false);
  assert.ok(CircuitValidator.validate(c).errors.some(e => /not equivalent/.test(e)));
  c.nets[0].pins.push(pin);
  assert.ok(CircuitValidator.validate(c).errors.some(e => /duplicate pin reference/.test(e)));
});
test('missing reciprocal pin.net and duplicate pin IDs fail validation', () => {
  const c = compile(circuit([{ from: 'R1.2', to: 'R2.1' }]));
  c.components[0].pins.find(p => p.id === '2').net = undefined;
  c.components[0].pins.push({ ...c.components[0].pins[0] });
  const v = CircuitValidator.validate(c);
  assert.equal(v.valid, false);
  assert.ok(v.errors.some(e => /not reciprocal/.test(e)));
  assert.ok(v.errors.some(e => /Duplicate pin identity/.test(e)));
});
test('malformed documents and collections report errors; an empty draft warns', () => {
  invalid(null);
  invalid({ components: [null], wires: [] });
  invalid({ components: {}, wires: [] });
  invalid({ components: [], wires: [null] });
  const c = compile({});
  assert.ok(c.validation.warnings.some(w => /empty/.test(w)));
});
test('Common Emitter exactly preserves all six source-derived nets', () => {
  const original = JSON.stringify(sample);
  const c = compile(sample);
  assert.equal(c.validation.valid, true);
  assert.deepEqual(partition(c), [
    ['C1.1', 'Q1.E'], ['C1.2', 'R2.2'], ['C2.1', 'Q1.C', 'R3.1'],
    ['C2.2'], ['Q1.B', 'R1.2', 'R2.1'], ['R1.1', 'R3.2'],
  ]);
  assert.ok(c.validation.warnings.some(w => /DC emitter return/.test(w)));
  assert.equal(JSON.stringify(sample), original);
});
test('all bundled templates compile with source limitations reported not repaired', () => {
  const dir = path.join(root, '../backend/circuits');
  for (const file of fs.readdirSync(dir).filter(f => f.endsWith('.json'))) {
    const source = JSON.parse(fs.readFileSync(path.join(dir, file), 'utf8'));
    assert.equal(compile(source).validation.valid, true, file);
  }
  const led = compile(JSON.parse(fs.readFileSync(path.join(dir, 'led_blinker.json'), 'utf8')));
  assert.ok(led.validation.warnings.some(w => /Q1.E.*floating/.test(w)));
  const timer = compile(JSON.parse(fs.readFileSync(path.join(dir, '555_astable_multivibrator.json'), 'utf8')));
  assert.ok(timer.validation.warnings.some(w => /RESET must be driven/.test(w)));
});
test('every adapter edge including labels resolves to its source net', () => {
  const c = compile(sample), flow = buildCircuitFlow(sample);
  assert.deepEqual(PinSystemDebugger.findInvalidConnections(c, flow.edges), []);
  const bad = { ...flow.edges.find(e => e.source === 'R1'), targetHandle: '9' };
  assert.ok(PinSystemDebugger.findInvalidConnections(c, [bad]).length);
  assert.match(PinSystemDebugger.tracePin(c, 'Q1', 'B'), /net ID/);
  assert.match(PinSystemDebugger.traceNet(c, c.nets[1].id), /R1/);
});
test('invalid flow is returned with diagnostics rather than a misleading graph', () => {
  const source = { ...sample, wires: [{ from: 'Q1.noSuchPin', to: 'R1.1' }] };
  const flow = buildCircuitFlow(source);
  assert.equal(flow.validation.valid, false);
  assert.deepEqual(flow.nodes, []);
  assert.deepEqual(flow.edges, []);
});
test('visual edge adapter rejects malformed and self edges without silently dropping them', () => {
  assert.throws(() => visualEdgesToConnections([{ source: 'R1', target: 'R2' }]));
  assert.throws(() => visualEdgesToConnections([{ source: 'R1', sourceHandle: '1', target: 'R1', targetHandle: '1' }]));
});
