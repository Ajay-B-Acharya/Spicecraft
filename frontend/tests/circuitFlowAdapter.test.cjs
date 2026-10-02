/** Dependency-free adapter regression tests; TypeScript is transpiled in memory. */
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
const { buildCircuitFlow } = load(path.join(root, 'components/circuits/circuitFlowAdapter'));
const { CircuitCompiler } = load(path.join(root, 'lib/circuit/engine/CircuitCompiler'));
const sample = JSON.parse(fs.readFileSync(path.join(root, '../backend/circuits/common_emitter_amplifier.json'), 'utf8'));

test('six components and named nets match the verified JSON topology', () => {
  const original = JSON.stringify(sample);
  const flow = buildCircuitFlow(sample);
  const compiled = CircuitCompiler.compile(sample);
  assert.equal(flow.nodes.filter(n => !n.data.netLabel).length, 6);
  assert.deepEqual(flow.nodes.filter(n => n.data.netLabel).map(n => n.data.reference).sort(), ['GND', 'OUT', 'VCC']);
  for (const edge of flow.edges) {
    assert.ok(edge.sourceHandle && edge.targetHandle);
    const net = compiled.nets.find(n => n.id === edge.data.netId);
    for (const [id, pin] of [[edge.source, edge.sourceHandle], [edge.target, edge.targetHandle]]) {
      const node = flow.nodes.find(n => n.id === id);
      assert.ok(node);
      if (!node.data.netLabel) assert.ok(net.pins.some(p => p.componentId === id && p.pinId === pin));
    }
  }
  assert.ok(flow.edges.some(e => e.source === 'R1' && e.sourceHandle === '2' && e.target === 'Q1' && e.targetHandle === 'B'));
  const expected = {
    VCC: ['R1.1', 'R3.2'],
    GND: ['C1.2', 'R2.2'],
    OUT: ['C2.2'],
  };
  for (const [label, endpoints] of Object.entries(expected)) {
    const net = compiled.nets.find(n => n.labels?.includes(label));
    assert.deepEqual(net.pins.map(p => `${p.componentId}.${p.pinId}`).sort(), endpoints.sort());
  }
  assert.equal(JSON.stringify(sample), original);
});

test('placement is deterministic and follows transistor terminal relationships', () => {
  const flow = buildCircuitFlow(sample);
  assert.deepEqual(flow, buildCircuitFlow(sample));
  const pos = id => flow.nodes.find(n => n.id === id).position;
  assert.ok(pos('R3').y < pos('Q1').y);
  assert.ok(pos('R1').x < pos('Q1').x);
  assert.ok(pos('C1').y > pos('Q1').y);
  const positions = flow.nodes.filter(n => !n.data.netLabel).map(n => JSON.stringify(n.position));
  assert.equal(new Set(positions).size, 6);
});

test('saved positions and semantic pin references preserve connectivity', () => {
  const data = structuredClone(sample);
  data.components[0].position = { x: 450, y: 300 };
  data.wires = data.wires.map(w => ({ ...w, from: w.from.replace('Q1.B', 'Q1.base'), source: w.source.replace('Q1.B', 'Q1.base') }));
  const flow = buildCircuitFlow(data);
  assert.deepEqual(flow.nodes.find(n => n.id === 'Q1').position, { x: 450, y: 300 });
  assert.ok(flow.edges.some(e => e.target === 'Q1' && e.targetHandle === 'B'));
});
