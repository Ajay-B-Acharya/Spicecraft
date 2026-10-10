'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const { load, root } = require('../tools/load-typescript.cjs');
const { CircuitCompiler } = load(path.join(root, 'lib/circuit/engine/CircuitCompiler'));
const { CIRCUIT_INPUT_LIMITS: limits } = load(path.join(root, 'lib/circuit/engine/CircuitBuilder'));
const { componentLibrary } = load(path.join(root, 'lib/circuit/engine/ComponentLibrary'));
const { resolvePins } = load(path.join(root, 'lib/circuit/engine/PinResolver'));
const { CircuitValidator } = load(path.join(root, 'lib/circuit/engine/CircuitValidator'));
const { PinSystemDebugger } = load(path.join(root, 'lib/circuit/engine/PinSystemDebugger'));
const { LayoutEngine } = load(path.join(root, 'lib/circuit/layout/LayoutEngine'));
const { LayoutAnalyzer } = load(path.join(root, 'lib/circuit/layout/LayoutAnalyzer'));
const { PlacementStrategy } = load(path.join(root, 'lib/circuit/layout/PlacementStrategy'));
const { PositionOptimizer } = load(path.join(root, 'lib/circuit/layout/PositionOptimizer'));
const { Grid } = load(path.join(root, 'lib/circuit/layout/Grid'));
const { LayoutDebugger } = load(path.join(root, 'lib/circuit/layout/LayoutDebugger'));
const { DEFAULT_LAYOUT_CONFIG } = load(path.join(root, 'lib/circuit/layout/LayoutTypes'));
const { buildCircuitFlow } = load(path.join(root, 'components/circuits/circuitFlowAdapter'));
const { ApiError, apiRequest, responseError, formatApiDetail } = load(path.join(root, 'lib/apiError'));
const resistor = id => ({ id, type: 'resistor', value: '1k' });
const source = (components = [resistor('R1'), resistor('R2')], wires = []) => ({
  id: 'circuit', name: 'Test', description: '', category: '', tags: [], components, wires,
});
const compile = value => CircuitCompiler.compile(value);
const invalid = value => {
  const result = compile(value);
  assert.equal(result.validation.valid, false, JSON.stringify(result.validation));
  return result;
};

function mockedModule(relative, mocks) {
  const filename = path.join(root, relative);
  const module = { exports: {} };
  const code = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  new Function('require', 'module', 'exports', code)(specifier => {
    if (Object.hasOwn(mocks, specifier)) return mocks[specifier];
    if (specifier.startsWith('@/')) return load(path.join(root, specifier.slice(2)));
    if (specifier.startsWith('.')) return load(path.resolve(path.dirname(filename), specifier));
    return require(specifier);
  }, module, module.exports);
  return module.exports;
}

// Runs hook state transitions without a browser or a second React renderer.
function hookHarness(relative, name, mocks) {
  const slots = [];
  let cursor = 0, dirty = false, args = [], value;
  let effects = [];
  const same = (a, b) => a && b && a.length === b.length && a.every((item, i) => Object.is(item, b[i]));
  const react = {
    useState(initial) {
      const index = cursor++;
      if (!(index in slots)) slots[index] = typeof initial === 'function' ? initial() : initial;
      return [slots[index], update => {
        const next = typeof update === 'function' ? update(slots[index]) : update;
        if (!Object.is(slots[index], next)) { slots[index] = next; dirty = true; }
      }];
    },
    useRef(initial) {
      const index = cursor++;
      return slots[index] ??= { current: initial };
    },
    useCallback(callback, dependencies) {
      const index = cursor++;
      if (!same(slots[index]?.dependencies, dependencies)) slots[index] = { dependencies, callback };
      return slots[index].callback;
    },
    useEffect(effect, dependencies) {
      const index = cursor++;
      if (!same(slots[index]?.dependencies, dependencies)) {
        const previous = slots[index];
        slots[index] = { dependencies };
        effects.push(() => {
          previous?.cleanup?.();
          slots[index].cleanup = effect();
        });
      }
    },
  };
  const hook = mockedModule(relative, { ...mocks, react })[name];
  const render = (...nextArgs) => {
    if (nextArgs.length) args = nextArgs;
    let passes = 0;
    do {
      assert.ok(++passes < 30, 'hook updates settle');
      cursor = 0; dirty = false; effects = [];
      value = hook(...args);
      for (const effect of effects) effect();
    } while (dirty);
    return value;
  };
  return { render, unmount: () => slots.forEach(slot => slot?.cleanup?.()) };
}
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
};

test('explicit unsupported, malformed, and prototype-looking types never become a supported device', () => {
  for (const type of ['LM358', 'mosfet', 'constructor', '__proto__', '', null, false, 555, {}, []]) {
    for (const value of ['NE555', 'BC547', 'resistor']) {
      invalid(source([{ id: 'U1', type, value }]));
    }
  }
  invalid(source([{ id: 'U1', value: 'NE555' }]));
  invalid(source([{ id: 'U1', type: null, kind: 'ne555', value: 'NE555' }]));
  assert.equal(compile(source([{ id: 'Q1', type: 'bjt', value: '2N3906' }])).components[0].type, 'pnp_transistor');
  assert.equal(compile(source([{ id: 'R1', type: 'resistor', value: 'NE555' }])).components[0].type, 'resistor');
});

test('JSON normalization accepts fenced objects and rejects malformed, deep, cyclic and accessor inputs', () => {
  assert.equal(compile('```json\n' + JSON.stringify(source()) + '\n```').validation.valid, true);
  for (const value of ['{broken}', '[]', '{} trailing', 'x'.repeat(limits.characters + 1), { components: new Array(0xffffffff) }]) invalid(value);
  const cyclic = source(); cyclic.loop = cyclic; invalid(cyclic);
  let deep = {}; for (let i = 0; i < 40; i++) deep = { deep }; invalid(deep);
  const accessor = {};
  Object.defineProperty(accessor, 'components', { get() { throw new Error('getter was invoked'); } });
  assert.match(invalid(accessor).validation.errors.join(), /accessor/);
  invalid({ components: [new Date()], wires: [] });
  invalid(source([{ ...resistor('R1'), x: 1 }]));
  for (const value of [NaN, Infinity, 1_000_001, '2px']) invalid(source([{ ...resistor('R1'), position: { x: value, y: 0 } }]));
});

test('component, wire and endpoint identity budgets reject excess before layout', () => {
  invalid(source(Array.from({ length: limits.components + 1 }, (_, i) => resistor(`R${i}`))));
  invalid(source(undefined, Array.from({ length: limits.wires + 1 }, () => ({ from: 'R1.1', to: 'R2.1' }))));
  invalid(source([resistor('r'.repeat(limits.identifier + 1))]));
  for (const to of ['n'.repeat(limits.identifier + 1), 'bad\nlabel', { label: 'n'.repeat(limits.identifier + 1) }]) {
    invalid(source(undefined, [{ from: 'R1.1', to }]));
  }
  invalid(source(undefined, [{ from: 'R1.1', to: 'OUT', id: 'same' }, { from: 'R2.1', to: 'OUT', id: 'same' }]));
});

test('all library pins are cloned and resolve finite geometry through mirrored quarter turns', () => {
  for (const definition of componentLibrary.list()) {
    assert.equal(new Set(definition.pins.map(pin => pin.id)).size, definition.pins.length);
    for (const rotation of [0, 90, 180, 270, -90, 450]) for (const mirror of [false, true]) {
      const position = { x: 123, y: -456 };
      const component = componentLibrary.createComponent(definition.type, { id: 'X1', position, rotation, mirror });
      position.x = 999;
      assert.equal(component.position.x, 123);
      const pins = resolvePins(component);
      assert.ok(pins.every(pin => Number.isFinite(pin.absoluteX) && Number.isFinite(pin.absoluteY)));
      assert.deepEqual(pins.map(pin => pin.id), definition.pins.map(pin => pin.id));
      const radians = rotation * Math.PI / 180;
      pins.forEach((pin, i) => {
        const original = definition.pins[i];
        const x = mirror ? -original.x : original.x;
        assert.ok(Math.abs(pin.absoluteX - (123 + x * Math.cos(radians) - original.y * Math.sin(radians))) < 1e-8);
        assert.ok(Math.abs(pin.absoluteY - (-456 + x * Math.sin(radians) + original.y * Math.cos(radians))) < 1e-8);
      });
      component.pins[0].id = 'mutated';
      assert.notEqual(componentLibrary.getDefinition(definition.type).pins[0].id, 'mutated');
    }
  }
});

test('fatal compiler errors never enter topology layout analysis', () => {
  const analyze = LayoutAnalyzer.analyze;
  let called = false;
  LayoutAnalyzer.analyze = () => { called = true; throw new Error('analysis should not run'); };
  try {
    assert.throws(() => LayoutEngine.layout(invalid(source([{ id: 'U1', type: 'ic', value: 'LM358' }]))), /invalid circuit/);
    assert.throws(() => LayoutEngine.layout(invalid(source(undefined, [{ from: 'R1.bad', to: 'R2.1' }]))), /invalid circuit/);
    assert.equal(called, false);
  } finally { LayoutAnalyzer.analyze = analyze; }
});

test('layout preserves topology, refreshes resolved geometry, and honors saved-position mode', () => {
  const compiled = compile(source(undefined, [{ from: 'R1.1', to: 'R2.2' }]));
  const before = JSON.stringify(compiled);
  const laidOut = LayoutEngine.layout(compiled);
  assert.deepEqual(laidOut.nets, compiled.nets);
  assert.deepEqual(laidOut.connections, compiled.connections);
  assert.deepEqual(laidOut.resolvedPins, laidOut.components.flatMap(resolvePins));
  assert.deepEqual(laidOut, LayoutEngine.layout(compiled));
  assert.equal(JSON.stringify(compiled), before);
  const preserved = LayoutEngine.layout(compiled, { ...DEFAULT_LAYOUT_CONFIG, preserveUserPositions: true });
  assert.deepEqual(preserved.components, compiled.components);
  const grid = new Grid(DEFAULT_LAYOUT_CONFIG.grid);
  assert.equal(grid.distance({ col: 0, row: 0 }, { col: 3, row: 4 }), 5);
  for (const spacingX of [0, -1, NaN, Infinity]) assert.throws(() => new Grid({ ...DEFAULT_LAYOUT_CONFIG.grid, spacingX }));
});

test('500-component placement stays bounded, deterministic and collision-free past the old 100-attempt cap', () => {
  const compiled = compile(source(Array.from({ length: limits.components }, (_, i) => resistor(`R${i}`))));
  const crowded = new Map(compiled.components.map(component => [component.id, { col: 0, row: 0 }]));
  const optimized = new PositionOptimizer().optimize(crowded, compiled);
  assert.equal(new Set([...optimized.values()].map(JSON.stringify)).size, limits.components);
  const analysis = LayoutAnalyzer.analyze(compiled);
  const hints = compiled.components.map(component => ({ componentId: component.id, preferredCol: 0, preferredRow: 0, weight: 100 }));
  hints.push({ componentId: 'R0', preferredCol: 999, preferredRow: 999, weight: 1 });
  const placements = PlacementStrategy.computePlacements(compiled, analysis, hints);
  assert.deepEqual(placements.get('R0'), { col: 0, row: 0 });
  assert.equal(new Set([...placements.values()].map(JSON.stringify)).size, limits.components);
  const result = new LayoutEngine().computeLayout(compiled);
  assert.equal(result.placements.size, limits.components);
  assert.ok(Object.values(result.bounds).every(Number.isFinite));
});

test('canonical BJT pins and signed supply labels drive layout hints', () => {
  const compiled = compile(source([resistor('R1'), { id: 'Q1', type: 'npn', value: 'BC547' }], [{ from: 'R1.1', to: 'Q1.B' }]));
  const hints = PlacementStrategy.generateHints(compiled, LayoutAnalyzer.analyze(compiled));
  assert.ok(hints.some(hint => hint.componentId === 'R1' && hint.preferredCol === 2 && hint.preferredRow === 3));
  const supply = compile(source([resistor('R1')], [{ from: 'R1.1', to: { label: 'V+' } }]));
  assert.ok(LayoutAnalyzer.analyze(supply).classification.supplies.includes('R1'));
});

test('flow label identities cannot collide with component IDs and numeric-string saved positions survive', () => {
  const id = 'net-label:["N1","OUT"]';
  const input = source([{ ...resistor(id), position: { x: '450', y: '300' } }], [{ from: { componentId: id, pinId: '1' }, to: 'OUT' }]);
  const flow = buildCircuitFlow(input);
  assert.equal(flow.validation.valid, true);
  assert.equal(new Set(flow.nodes.map(node => node.id)).size, flow.nodes.length);
  assert.deepEqual(flow.nodes.find(node => node.id === id).position, { x: 450, y: 300 });
  assert.deepEqual(flow, buildCircuitFlow(input));
  assert.deepEqual(PinSystemDebugger.findInvalidConnections(compile(input), flow.edges), []);
});

test('maximum-sized shared nets render all explicit labels without inventing connectivity', () => {
  const components = Array.from({ length: limits.components }, (_, i) => resistor(`R${i}`));
  const wires = components.map(component => ({ from: `${component.id}.1`, to: 'shared' }));
  for (let i = wires.length; i < limits.wires; i++) wires.push({ from: 'shared', to: `signal_${i}` });
  const input = source(components, wires);
  const compiled = compile(input);
  assert.equal(compiled.validation.valid, true);
  assert.equal(compiled.nets.length, 1);
  const flow = buildCircuitFlow(input);
  assert.equal(flow.nodes.length, limits.components + 1501);
  assert.equal(flow.edges.length, limits.components - 1 + 1501);
  assert.deepEqual(flow, buildCircuitFlow(input));
});

test('validator and direct layout reject corrupted non-finite geometry', () => {
  for (const mutate of [
    circuit => { circuit.components[0].position.x = NaN; },
    circuit => { circuit.components[0].pins[0].x = Infinity; },
    circuit => { circuit.resolvedPins[0].absoluteY = NaN; },
  ]) {
    const compiled = compile(source());
    mutate(compiled);
    assert.equal(CircuitValidator.validate(compiled).valid, false);
    assert.throws(() => LayoutEngine.layout(compiled), /invalid circuit/);
  }
  const grid = new Grid(DEFAULT_LAYOUT_CONFIG.grid);
  assert.throws(() => grid.toAbsolute({ col: Infinity, row: 0 }), /coordinate limit/);
  assert.throws(() => grid.toAbsolute({ col: 1_000_000, row: 0 }), /coordinate limit/);
});

test('debug-grid rendering refuses huge extents and unsafe grid indices without allocating a dense matrix', () => {
  const compiled = compile(source());
  const result = new LayoutEngine().computeLayout(compiled);
  assert.match(LayoutDebugger.formatGrid(compiled, result), /ASCII Grid Visualization/);
  const oversized = { ...result, gridBounds: { minCol: -1_000_000, maxCol: 1_000_000, minRow: -1_000_000, maxRow: 1_000_000, cols: 2_000_001, rows: 2_000_001 } };
  assert.match(LayoutDebugger.formatGrid(compiled, oversized), /omitted/);
  const tiny = new Grid({ ...DEFAULT_LAYOUT_CONFIG.grid, spacingX: Number.MIN_VALUE });
  assert.throws(() => tiny.toGrid({ x: 500, y: 0 }), /safe integer/);
});

test('API normalization rejects malformed types/collections and preserves object and React Flow endpoints on round trip', async () => {
  let data, sent, requested;
  const { circuitService } = mockedModule('lib/circuitService.ts', { './api': { api: {
    get: async url => { requested = url; return data; },
    put: async (_url, body) => { sent = body; return body; },
  } } });
  for (const type of [555, null, true, {}, 'mosfet']) {
    data = source([{ id: 'U1', type, value: 'NE555', kind: 'ne555' }]);
    await assert.rejects(circuitService.getCircuit('a/b'), error => error instanceof ApiError && error.status === 502);
  }
  for (const malformed of [null, {}, { components: [null], wires: [] }, { components: [], wires: {} }]) {
    data = malformed;
    await assert.rejects(circuitService.getCircuit('a/b'), ApiError);
  }
  data = {};
  await assert.rejects(circuitService.getCircuits(), ApiError);
  for (const wire of [
    { from: { componentId: 'R1', pinId: '2' }, to: { componentId: 'R2', pinId: '1' } },
    { source: 'R1', sourceHandle: '2', target: 'R2', targetHandle: '1' },
  ]) {
    data = { ...source(undefined, [wire]), metadata: { author: 'Preserved author', revision: 3 } };
    const result = await circuitService.getCircuit('a/b');
    assert.deepEqual(result.metadata, data.metadata);
    assert.equal(requested, '/circuits/a%2Fb');
    assert.deepEqual(result.wires, [wire]);
    await circuitService.updateCircuit('a/b', result);
    assert.deepEqual(sent.wires, [wire]);
    assert.deepEqual(sent.metadata, data.metadata);
    assert.deepEqual(compile(result).nets, compile(data).nets);
  }
  sent = undefined;
  await assert.rejects(circuitService.updateCircuit('x', source([{ id: 'U1', type: 'unsupported' }])), error => error.status === 422);
  assert.equal(sent, undefined);
});

test('API diagnostics preserve structured details and bound cyclic or very large error trees', async () => {
  const detail = { stage: 'validation', code: 'BAD_PIN', component: 'R1', pin: '9', retryable: false,
    diagnostics: [{ msg: 'Invalid endpoint', loc: ['body', 'wires', 0] }] };
  const error = await responseError(new Response(JSON.stringify({ detail }), { status: 422 }));
  assert.equal(error.status, 422);
  assert.equal(error.retryable, false);
  assert.match(error.message, /Stage: validation/);
  assert.match(error.message, /Invalid endpoint/);
  assert.match(error.message, /Field: body.wires.0/);
  const gateway = await responseError(new Response('<html>bad gateway</html>', { status: 503 }));
  assert.equal(gateway.message, 'Request failed (HTTP 503).');
  assert.equal(gateway.retryable, true);
  const cycle = { message: 'cycle' }; cycle.errors = [cycle];
  assert.equal(formatApiDetail(cycle), 'cycle');
  assert.ok(formatApiDetail(Array.from({ length: 1000 }, () => ({ message: 'x'.repeat(100_000) }))).length <= 16_384);
});

test('network, malformed JSON, timeout and cancellation errors do not automatically replay requests', async () => {
  const original = global.fetch;
  let calls = 0;
  try {
    global.fetch = async () => { calls++; throw new TypeError('offline'); };
    await assert.rejects(apiRequest('/x', {}, r => r.json()), error => error instanceof ApiError && error.status === 0 && error.retryable);
    assert.equal(calls, 1);
    global.fetch = async () => new Response('{bad', { status: 200 });
    await assert.rejects(apiRequest('/x', {}, r => r.json()), error => error.status === 502 && /malformed JSON/.test(error.message));
    global.fetch = (_url, init) => new Promise((_resolve, reject) => {
      const abort = () => reject(new DOMException('Aborted', 'AbortError'));
      if (init.signal.aborted) abort(); else init.signal.addEventListener('abort', abort, { once: true });
    });
    await assert.rejects(apiRequest('/x', {}, r => r.json(), 5), error => error.status === 408 && /preserved/.test(error.message));
    const controller = new AbortController();
    const pending = apiRequest('/x', { signal: controller.signal }, r => r.json());
    controller.abort();
    await assert.rejects(pending, error => error.status === 0 && !error.retryable && /cancelled/.test(error.message));
  } finally { global.fetch = original; }
});

test('export download cleanup removes its anchor and releases the blob URL even when clicking fails', async () => {
  const originalDocument = global.document;
  const originalCreate = URL.createObjectURL, originalRevoke = URL.revokeObjectURL;
  const originalTimeout = global.setTimeout;
  let removed = false, revoked = false, requestUrl;
  const callbacks = [];
  try {
    const anchor = { click() { throw new Error('download blocked'); }, remove() { removed = true; } };
    global.document = { createElement: () => anchor, body: { appendChild() {} } };
    URL.createObjectURL = () => 'blob:test';
    URL.revokeObjectURL = value => { revoked = value === 'blob:test'; };
    global.setTimeout = callback => { callbacks.push(callback); return 1; };
    const { ltspiceExportService } = mockedModule('lib/ltspiceExportService.ts', {
      './firebase': { auth: { currentUser: { getIdToken: async () => 'token' } } },
      './apiError': { apiRequest: async (url, _init, consume) => {
        requestUrl = url;
        return consume(new Response('Version 4\nSHEET 1 880 680\n', { headers: { 'content-type': 'application/octet-stream' } }));
      } },
    });
    await assert.rejects(ltspiceExportService.exportAsc('a/b', 'circuit'), /download blocked/);
    assert.match(requestUrl, /\/circuits\/a%2Fb\/export\/asc$/);
    assert.equal(anchor.download, 'circuit.asc');
    assert.equal(removed, true);
    assert.equal(callbacks.length, 1);
    callbacks[0]();
    assert.equal(revoked, true);
  } finally {
    global.document = originalDocument;
    URL.createObjectURL = originalCreate; URL.revokeObjectURL = originalRevoke;
    global.setTimeout = originalTimeout;
  }
});

test('failed saves retain drafts, prevent duplicate submission and recover on an explicit retry', async () => {
  let request = deferred(), calls = 0;
  const harness = hookHarness('hooks/useCircuitEditor.ts', 'useCircuitEditor', {
    sonner: { toast: { success() {}, error() {} } },
    '@/lib/circuitService': { circuitService: { updateCircuit: () => { calls++; return request.promise; } } },
  });
  let editor = harness.render(source());
  editor.updateComponentValue('R1', '2k'); editor = harness.render();
  const save = editor.saveChanges();
  assert.equal(await editor.saveChanges(), null);
  assert.equal(calls, 1);
  request.reject(new ApiError('Validation failed', 422));
  assert.equal(await save, null);
  editor = harness.render();
  assert.equal(editor.circuit.components[0].value, '2k');
  assert.equal(editor.hasUnsavedChanges, true);
  assert.equal(editor.saving, false);
  assert.equal(editor.saveError, 'Validation failed');
  request = deferred();
  const retry = editor.saveChanges();
  request.resolve(structuredClone(editor.circuit)); await retry;
  editor = harness.render();
  assert.equal(editor.hasUnsavedChanges, false);
  assert.equal(editor.saveError, null);
});

test('save responses and same-circuit refreshes never overwrite newer local edits or a different circuit', async () => {
  const request = deferred();
  const harness = hookHarness('hooks/useCircuitEditor.ts', 'useCircuitEditor', {
    sonner: { toast: { success() {}, error() {} } },
    '@/lib/circuitService': { circuitService: { updateCircuit: () => request.promise } },
  });
  let editor = harness.render(source());
  editor.updateComponentValue('R1', '2k'); editor = harness.render();
  const submitted = editor.circuit, pending = editor.saveChanges();
  editor.updateComponentValue('R1', '3k'); editor = harness.render();
  request.resolve(structuredClone(submitted)); await pending;
  editor = harness.render();
  assert.equal(editor.circuit.components[0].value, '3k');
  assert.equal(editor.hasUnsavedChanges, true);
  editor = harness.render(source());
  assert.equal(editor.circuit.components[0].value, '3k');
  const second = deferred();
  const other = hookHarness('hooks/useCircuitEditor.ts', 'useCircuitEditor', {
    sonner: { toast: { success() {}, error() {} } },
    '@/lib/circuitService': { circuitService: { updateCircuit: () => second.promise } },
  });
  editor = other.render(source());
  editor.updateComponentValue('R1', '4k'); editor = other.render();
  const stale = editor.saveChanges();
  other.render({ ...source(), id: 'different' });
  second.resolve(submitted);
  assert.equal(await stale, null);
  assert.equal(other.render().circuit.id, 'different');
});

test('fetch races, refresh errors and sign-out cannot restore stale circuit state', async () => {
  const requests = [];
  let authListener;
  const auth = { currentUser: { uid: 'user' } };
  const harness = hookHarness('hooks/useCircuit.ts', 'useCircuit', {
    '@/lib/firebase': { auth },
    'firebase/auth': { onAuthStateChanged: (_auth, listener) => { authListener = listener; listener(auth.currentUser); return () => {}; } },
    '@/lib/circuitService': { circuitService: { getCircuit: id => {
      const request = deferred(); requests.push({ ...request, id }); return request.promise;
    } } },
  });
  harness.render('first');
  harness.render('second');
  requests[1].resolve({ ...source(), id: 'second' }); await Promise.resolve();
  requests[0].resolve({ ...source(), id: 'first' }); await Promise.resolve();
  let state = harness.render();
  assert.equal(state.circuit.id, 'second');
  const refresh = state.refetch(); requests[2].reject(new ApiError('Unavailable', 503)); await refresh;
  state = harness.render();
  assert.equal(state.circuit.id, 'second');
  assert.equal(state.error, 'Unavailable');
  assert.equal(state.notFound, false);
  const pending = state.refetch();
  auth.currentUser = null; authListener(null);
  requests[3].resolve({ ...source(), id: 'second' }); await pending;
  assert.equal(harness.render().circuit, null);
  harness.unmount();
});

test('backend request-validation locations remain visible', () => {
  assert.match(formatApiDetail({ diagnostics: [{ message: 'Field required', location: ['body', 'components', 0, 'type'] }] }), /Field: body.components.0.type/);
});

test('aborted error-body reads retain timeout and cancellation semantics', async () => {
  const original = global.fetch;
  try {
    global.fetch = async (_url, init) => new Response(new ReadableStream({
      start(controller) {
        init.signal.addEventListener('abort', () => controller.error(new DOMException('Aborted', 'AbortError')), { once: true });
      },
    }), { status: 422 });
    await assert.rejects(apiRequest('/x', {}, r => r.json(), 5), error => error.status === 408 && error.retryable);
    const controller = new AbortController();
    const pending = apiRequest('/x', { signal: controller.signal }, r => r.json());
    controller.abort();
    await assert.rejects(pending, error => error.status === 0 && /cancelled/.test(error.message));
  } finally { global.fetch = original; }
});

test('successful HTTP error pages and malformed ASC never create downloads', async () => {
  const original = global.fetch;
  const create = URL.createObjectURL;
  let downloads = 0;
  try {
    URL.createObjectURL = () => { downloads++; return 'blob:test'; };
    const { ltspiceExportService } = mockedModule('lib/ltspiceExportService.ts', {
      './firebase': { auth: { currentUser: { getIdToken: async () => 'token' } } },
    });
    for (const [type, body] of [['text/html', '<html>Sign in</html>'], ['application/json', '{}'], ['application/octet-stream', ''], ['text/plain', 'Version 4\nnot a schematic']]) {
      global.fetch = async () => new Response(body, { headers: { 'content-type': type } });
      await assert.rejects(ltspiceExportService.exportAsc('circuit', 'test'), error => error instanceof ApiError && error.status === 502);
    }
    assert.equal(downloads, 0);
  } finally { global.fetch = original; URL.createObjectURL = create; }
});

test('project reads and mutations cannot restore data after sign-out or overwrite a newer fetch', async () => {
  const requests = [], create = deferred();
  let listener;
  const auth = { currentUser: { uid: 'first' } };
  const harness = hookHarness('hooks/useProjects.ts', 'useProjects', {
    '@/lib/firebase': { auth },
    'firebase/auth': { onAuthStateChanged: (_auth, next) => { listener = next; next(auth.currentUser); return () => {}; } },
    '@/lib/projectService': { projectService: {
      getProjects: () => { const request = deferred(); requests.push(request); return request.promise; },
      createProject: () => create.promise,
    } },
  });
  let state = harness.render();
  const refresh = state.fetchProjects();
  requests[1].resolve([{ id: 'new' }]); await refresh;
  requests[0].resolve([{ id: 'old' }]); await Promise.resolve();
  state = harness.render();
  assert.deepEqual(state.projects, [{ id: 'new' }]);
  const mutation = state.createProject({ name: 'Private project' });
  const stale = state.fetchProjects();
  auth.currentUser = null; listener(null);
  create.resolve({ id: 'private' }); requests[2].resolve([{ id: 'private' }]);
  await Promise.all([mutation, stale]);
  state = harness.render();
  assert.deepEqual(state.projects, []);
  assert.equal(state.loading, false);
  assert.equal(state.error, null);
  harness.unmount();
});

test('project and source update/delete hooks apply successful results and discard stale mutation responses', async () => {
  for (const kind of ['Project', 'Source']) {
    const isProject = kind === 'Project';
    const listKey = isProject ? 'projects' : 'sources';
    const modulePath = isProject ? '@/lib/projectService' : '@/lib/circuitSourceService';
    const serviceName = isProject ? 'projectService' : 'circuitSourceService';
    const hookName = isProject ? 'useProjects' : 'useCircuitSources';
    const requests = [];
    let listener;
    const auth = { currentUser: { uid: 'user' } };
    const service = {
      [isProject ? 'getProjects' : 'getSources']: async () => [{ id: 'row', title: 'Original' }],
      [`update${kind}`]: () => { const request = deferred(); requests.push(request); return request.promise; },
      [`delete${kind}`]: () => { const request = deferred(); requests.push(request); return request.promise; },
    };
    const harness = hookHarness(`hooks/${hookName}.ts`, hookName, {
      '@/lib/firebase': { auth },
      'firebase/auth': { onAuthStateChanged: (_auth, next) => { listener = next; next(auth.currentUser); return () => {}; } },
      [modulePath]: { [serviceName]: service },
    });
    harness.render('project'); await Promise.resolve();
    let state = harness.render();
    const update = state[`update${kind}`]('row', { title: 'Updated' });
    requests[0].resolve({ id: 'row', title: 'Updated' }); await update;
    state = harness.render();
    assert.equal(state[listKey][0].title, 'Updated');
    const deletion = state[`delete${kind}`]('row');
    requests[1].resolve(); await deletion;
    state = harness.render();
    assert.deepEqual(state[listKey], []);
    const stale = state[`update${kind}`]('row', { title: 'Private' });
    auth.currentUser = null; listener(null);
    requests[2].resolve({ id: 'row', title: 'Private' }); await stale;
    assert.deepEqual(harness.render()[listKey], []);
    harness.unmount();
  }
});

test('source requests are isolated by project and failed mutations retain existing rows', async () => {
  const requests = [], mutation = deferred(), deletion = deferred();
  let listener;
  const auth = { currentUser: { uid: 'user' } };
  const harness = hookHarness('hooks/useCircuitSources.ts', 'useCircuitSources', {
    '@/lib/firebase': { auth },
    'firebase/auth': { onAuthStateChanged: (_auth, next) => { listener = next; next(auth.currentUser); return () => {}; } },
    '@/lib/circuitSourceService': { circuitSourceService: {
      getSources: () => { const request = deferred(); requests.push(request); return request.promise; },
      createSource: () => mutation.promise,
      deleteSource: () => deletion.promise,
    } },
  });
  harness.render('first');
  harness.render('second');
  requests[1].resolve([{ id: 'second-source' }]); await Promise.resolve();
  requests[0].resolve([{ id: 'first-source' }]); await Promise.resolve();
  let state = harness.render();
  assert.deepEqual(state.sources, [{ id: 'second-source' }]);
  const remove = state.deleteSource('second-source');
  assert.deepEqual(harness.render().sources, [{ id: 'second-source' }]);
  deletion.reject(new ApiError('Delete failed', 503));
  await assert.rejects(remove, /Delete failed/);
  state = harness.render();
  assert.deepEqual(state.sources, [{ id: 'second-source' }]);
  const create = state.createSource({ title: 'Private source' });
  auth.currentUser = null; listener(null);
  mutation.resolve({ id: 'private' }); await create;
  state = harness.render();
  assert.deepEqual(state.sources, []);
  assert.equal(state.error, null);
  assert.equal(state.loading, false);
  harness.unmount();
});
