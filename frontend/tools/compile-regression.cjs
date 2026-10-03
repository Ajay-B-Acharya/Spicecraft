#!/usr/bin/env node
'use strict';

// Phase 9 TEST ONLY. No application imports this bridge and no TS is emitted.
// Input: { circuits: [{ key: string, input: unknown }], ...ignoredOptions }.
// Backend components/connections come exclusively from CircuitCompiler output.
// Source inspection below is limited to metadata, identity provenance and values.
const fs = require('node:fs');
const path = require('node:path');
const { performance } = require('node:perf_hooks');
const { load, root } = require('./load-typescript.cjs');
const { CircuitCompiler } = load(path.join(root, 'lib/circuit/engine/CircuitCompiler'));
const { componentLibrary } = load(path.join(root, 'lib/circuit/engine/ComponentLibrary'));
const { canonicalLabel, isLabelConnection, labelConnection, endpointKey, LABEL_COMPONENT_PREFIX } =
  load(path.join(root, 'lib/circuit/engine/NetBuilder'));

const SHARED_EXPORT_TYPES = Object.freeze({
  resistor: 'resistor',
  capacitor: 'capacitor',
  npn_transistor: 'transistor',
  diode: 'diode',
  led: 'led',
  ne555: 'ne555',
});
const COORDINATE_NOTE = 'Frontend symbol-local coordinates are intentionally not LTspice ASY offsets; compare logical pin IDs, not physical offsets.';
const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
const record = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const text = value => typeof value === 'string' ? value.trim() || undefined
  : typeof value === 'number' || typeof value === 'boolean' ? String(value) : undefined;
const sourceIdentity = component => text(component.id) ?? text(component.reference) ?? text(component.name);
const singleToken = value => typeof value === 'string' && value.length > 0 && !/[\s.\x00-\x1f\x7f]/u.test(value);

function sourceContext(input) {
  const envelope = record(input) ? input : {};
  const data = record(envelope.data) ? envelope.data : {};
  const owners = record(envelope.circuit) ? [envelope.circuit, envelope]
    : record(data.circuit) ? [data.circuit, data, envelope] : [envelope];
  const circuit = owners[0];
  const collection = [circuit.components, circuit.nodes].find(Array.isArray) ?? [];
  const components = collection.map((component, index) => ({ component, index }))
    .filter(item => record(item.component));
  const metadata = {};
  for (const key of ['name', 'description']) {
    const owner = owners.find(candidate => own(candidate, key));
    if (owner) metadata[key] = owner[key];
  }
  return { components, metadata };
}

function pinDefinitions() {
  return componentLibrary.list().map(definition => ({
    ...definition,
    backend_type: SHARED_EXPORT_TYPES[definition.type] ?? null,
    shared_export: own(SHARED_EXPORT_TYPES, definition.type),
    pin_count: definition.pins.length,
    coordinate_space: 'frontend_symbol_local',
    // Preserve every actual library field; orientation exposes its direction verbatim.
    pins: definition.pins.map(pin => ({ ...pin, orientation: pin.direction ?? null })),
  }));
}

function libraryCoverage(circuits) {
  const definitions = pinDefinitions();
  const supported = definitions.filter(definition => definition.shared_export);
  const observed = definitions.map(definition => {
    const components = circuits.flatMap(circuit => circuit.components)
      .filter(component => component.type === definition.type);
    return {
      frontend_type: definition.type,
      backend_type: definition.backend_type,
      shared_export: definition.shared_export,
      definition_pin_count: definition.pin_count,
      component_count: components.length,
      pin_count: components.reduce((sum, component) => sum + component.pins.length, 0),
    };
  });
  return {
    frontend_supported_names: definitions.map(definition => definition.type),
    shared_export_types: { ...SHARED_EXPORT_TYPES },
    unsupported_shared_export: definitions.filter(definition => !definition.shared_export).map(definition => definition.type),
    definition_count: definitions.length,
    definition_pin_count: definitions.reduce((sum, definition) => sum + definition.pin_count, 0),
    shared_definition_count: supported.length,
    shared_definition_pin_count: supported.reduce((sum, definition) => sum + definition.pin_count, 0),
    circuit_count: circuits.length,
    valid_circuit_count: circuits.filter(circuit => circuit.valid).length,
    component_count: circuits.reduce((sum, circuit) => sum + circuit.counts.components, 0),
    pin_count: circuits.reduce((sum, circuit) => sum + circuit.counts.pins, 0),
    by_type: observed,
    coordinate_note: COORDINATE_NOTE,
  };
}

function compileCircuit(input, key = null) {
  const started = performance.now();
  const diagnostics = [];
  const diagnostic = (severity, code, message, detail = {}, stage = 'bridge') => {
    diagnostics.push({ severity, stage, code, message, ...detail });
  };
  let compiled;
  try {
    compiled = CircuitCompiler.compile(input);
  } catch (error) {
    diagnostic('error', 'COMPILER_EXCEPTION', error.message, {}, 'compiler');
    compiled = { components: [], connections: [], nets: [], resolvedPins: [], validation: { valid: false, errors: [], warnings: [] } };
  }
  for (const message of compiled.validation.errors) diagnostic('error', 'COMPILER_ERROR', message, {}, 'compiler');
  for (const message of compiled.validation.warnings) diagnostic('warning', 'COMPILER_WARNING', message, {}, 'compiler');

  const context = sourceContext(input);
  const identityMapping = [];
  const valueDrift = [];
  const compiledById = new Map();
  const mappingById = new Map();
  const backendOwners = new Map();
  const usedSourceIndices = new Set();
  const backendComponents = [];

  compiled.components.forEach((component, index) => {
    if (compiledById.has(component.id)) {
      diagnostic('error', 'DUPLICATE_COMPILED_ID', `Compiled identity ${component.id} is ambiguous.`, { compiled_id: component.id });
    } else compiledById.set(component.id, component);
    if (!own(SHARED_EXPORT_TYPES, component.type)) {
      diagnostic('error', 'UNSUPPORTED_SHARED_EXPORT_KIND', `Frontend kind ${component.type} is not supported by the shared backend export; no fallback component is permitted.`, { compiled_id: component.id, frontend_type: component.type });
    }

    let candidates = context.components.filter(item => sourceIdentity(item.component) === component.id);
    let generated = false;
    // Only successful, one-to-one compilation permits ordered attribution for
    // compiler-generated IDs. Explicit identities never use an index fallback.
    if (candidates.length === 0 && compiled.validation.valid && context.components.length === compiled.components.length) {
      const candidate = context.components[index];
      if (candidate && !sourceIdentity(candidate.component)) {
        candidates = [candidate];
        generated = true;
      }
    }
    if (candidates.length !== 1 || usedSourceIndices.has(candidates[0]?.index)) {
      diagnostic('error', candidates.length > 1 ? 'AMBIGUOUS_SOURCE_IDENTITY' : 'UNMAPPED_SOURCE_IDENTITY', `Compiled identity ${component.id} must map to exactly one source component.`, { compiled_id: component.id });
      return;
    }
    const { component: source, index: sourceIndex } = candidates[0];
    usedSourceIndices.add(sourceIndex);
    // The compiler prefers id; the backend prefers reference. Keep that
    // distinction explicit instead of replacing compiled identity silently.
    const backendId = text(source.reference) ?? component.id;
    const mapping = {
      compiled_id: component.id,
      backend_id: backendId,
      source_index: sourceIndex,
      source_id: source.id ?? null,
      source_reference: source.reference ?? null,
      generated_by_compiler: generated,
    };
    identityMapping.push(mapping);
    mappingById.set(component.id, mapping);
    if (!singleToken(backendId) || backendId.startsWith(LABEL_COMPONENT_PREFIX)) {
      diagnostic('error', 'INVALID_BACKEND_IDENTITY', `Backend identity ${JSON.stringify(backendId)} cannot be represented as an unambiguous Component.Pin token.`, mapping);
    }
    // LTspice instance names are case-insensitive, unlike compiler identities.
    const folded = backendId.toUpperCase();
    if (backendOwners.has(folded)) {
      diagnostic('error', 'INSTANCE_NAME_COLLISION', `Backend references ${backendOwners.get(folded)} and ${backendId} collide in case-insensitive LTspice.`, mapping);
    } else backendOwners.set(folded, backendId);

    const sourcePresent = own(source, 'value');
    if (!sourcePresent || !Object.is(source.value, component.value)) {
      const drift = {
        compiled_id: component.id,
        backend_id: backendId,
        source_present: sourcePresent,
        source_value: source.value ?? null,
        compiled_value: component.value ?? null,
        reason: text(source.value) === undefined ? 'compiler_default' : 'compiler_normalization',
      };
      valueDrift.push(drift);
      diagnostic('warning', 'VALUE_DRIFT', 'Compiled value differs from the source; the actual compiler value is preserved unchanged.', drift);
    }
    const backendComponent = { id: backendId, reference: backendId, type: SHARED_EXPORT_TYPES[component.type] ?? null };
    if (component.value !== undefined) backendComponent.value = component.value;
    backendComponents.push(backendComponent);
  });

  function endpoint(endpoint, location) {
    if (isLabelConnection(endpoint)) {
      const label = canonicalLabel(endpoint.componentId.slice(LABEL_COMPONENT_PREFIX.length));
      if (!singleToken(label) || endpointKey(labelConnection(label)) !== endpointKey(endpoint)) {
        diagnostic('error', 'INVALID_COMPILED_LABEL', `Compiled label cannot be exported unambiguously at ${location}.`, { endpoint });
        return null;
      }
      return label;
    }
    const component = compiledById.get(endpoint.componentId);
    const mapping = mappingById.get(endpoint.componentId);
    if (!component || !mapping) {
      diagnostic('error', 'UNMAPPED_COMPILED_REFERENCE', `Unmapped compiled reference at ${location}.`, { endpoint });
      return null;
    }
    if (component.pins.filter(pin => pin.id === endpoint.pinId).length !== 1 || !singleToken(endpoint.pinId)) {
      diagnostic('error', 'INVALID_COMPILED_PIN', `Compiled pin is undefined or ambiguous at ${location}.`, { endpoint });
      return null;
    }
    return `${mapping.backend_id}.${endpoint.pinId}`;
  }

  // Never consult source wires or recreate pins, aliases, missing nets or edges.
  const backendWires = compiled.connections.map((connection, index) => ({
    from: endpoint(connection.source, `connection ${index} source`),
    to: endpoint(connection.target, `connection ${index} target`),
    ...(connection.id === undefined ? {} : { id: connection.id }),
  }));
  const topology = compiled.nets.map(net => ({
    id: net.id,
    name: net.name ?? net.id,
    labels: [...new Set((net.labels ?? []).map(canonicalLabel))].sort(),
    pins: net.pins.map(pin => endpoint(pin, `net ${net.id}`)).sort(),
    compiled_pins: net.pins.map(pin => `${pin.componentId}.${pin.pinId}`).sort(),
  }));
  const valid = compiled.validation.valid && !diagnostics.some(item => item.severity === 'error');
  return {
    key,
    valid,
    compiler_valid: compiled.validation.valid,
    diagnostics,
    backend: valid ? { ...context.metadata, components: backendComponents, wires: backendWires } : null,
    metadata: context.metadata,
    topology,
    components: compiled.components,
    connections: compiled.connections,
    resolved_pins: compiled.resolvedPins,
    identity_mapping: identityMapping,
    pin_definitions: pinDefinitions(),
    value_drift: valueDrift,
    counts: {
      components: compiled.components.length,
      pins: compiled.components.reduce((sum, component) => sum + component.pins.length, 0),
      connections: compiled.connections.length,
      nets: compiled.nets.length,
      mapped_components: identityMapping.length,
    },
    coordinate_note: COORDINATE_NOTE,
    duration_ms: performance.now() - started,
  };
}

function compileRequest(request) {
  if (!record(request) || !Array.isArray(request.circuits)) throw new TypeError('Request must contain a circuits array.');
  const keys = new Set();
  for (const entry of request.circuits) {
    if (!record(entry) || typeof entry.key !== 'string' || !entry.key || !own(entry, 'input')) {
      throw new TypeError('Each circuit must contain a nonempty string key and an input field.');
    }
    if (keys.has(entry.key)) throw new TypeError(`Duplicate circuit key: ${entry.key}`);
    keys.add(entry.key);
  }
  const circuits = request.circuits.map(entry => compileCircuit(entry.input, entry.key));
  return { circuits, coverage: libraryCoverage(circuits) };
}

if (require.main === module) {
  try {
    const result = compileRequest(JSON.parse(fs.readFileSync(0, 'utf8')));
    process.stdout.write(`${JSON.stringify(result)}\n`);
  } catch (error) {
    process.stdout.write(`${JSON.stringify({
      circuits: [],
      coverage: libraryCoverage([]),
      diagnostics: [{ severity: 'error', stage: 'request', code: 'INVALID_REQUEST', message: error.message }],
    })}\n`);
    process.exitCode = 1;
  }
}

module.exports = { compileCircuit, compileRequest, SHARED_EXPORT_TYPES };
