/**
 * Circuit builder.
 *
 * Parses AI-style circuit JSON, instantiates canonical components through the
 * ComponentLibrary, resolves pin geometry, translates wire references into
 * electrical nets through the NetBuilder, and returns a complete UI-independent
 * circuit object. The builder does not depend on React Flow.
 */
import { buildNets, canonicalLabel, endpointKey, isLabelConnection, labelConnection, LABEL_COMPONENT_PREFIX } from './NetBuilder';
import { componentLibrary } from './ComponentLibrary';
import { resolvePins } from './PinResolver';
import { Component } from '../models/Component';
import { Net } from '../models/Net';
import {
  CircuitBuildResult,
  CircuitValidationResult,
  CompiledCircuit,
  PinConnection,
  VisualConnection,
} from '../types';

const DEFAULT_COMPONENT_SPACING_X = 220;
const DEFAULT_COMPONENT_SPACING_Y = 160;
const DEFAULT_COMPONENT_COLUMNS = 4;

interface NormalizedComponentInput {
  rawIndex: number;
  reference?: string;
  rawType?: string;
  rawValue?: string;
  canonicalType?: string;
  position: { x: number; y: number };
  rotation: number;
  mirror: boolean;
}

interface NormalizedWireInput {
  rawIndex: number;
  id?: string;
  raw: Record<string, unknown>;
}

type EndpointReference =
  | {
      kind: 'pin';
      componentId: string;
      pinId: string;
    }
  | {
      kind: 'label';
      label: string;
    };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function toText(value: unknown): string | undefined {
  if (typeof value === 'string') {
    const normalized = value.trim();
    return normalized.length > 0 ? normalized : undefined;
  }

  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value);
  }

  return undefined;
}

function toNumber(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === 'string' && /^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i.test(value.trim())) {
    const parsed = Number(value.trim());
    return Number.isFinite(parsed) ? parsed : undefined;
  }

  return undefined;
}

function toBoolean(value: unknown): boolean | undefined {
  if (typeof value === 'boolean') {
    return value;
  }

  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase();

    if (normalized === 'true') {
      return true;
    }

    if (normalized === 'false') {
      return false;
    }
  }

  return undefined;
}

export const CIRCUIT_INPUT_LIMITS = {
  characters: 2_000_000, entries: 50_000, depth: 32, components: 500, pins: 4_000, wires: 2_000,
  identifier: 256, coordinate: 1_000_000,
} as const;

function prepareSource(source: unknown): unknown {
  if (typeof source === 'string') {
    if (source.length > CIRCUIT_INPUT_LIMITS.characters) throw new Error('Circuit JSON exceeds the input size limit.');
    const text = source.trim().replace(/^```(?:json)?\s*\n([\s\S]*?)\n```$/i, '$1');
    try { source = JSON.parse(text); }
    catch { throw new Error('Malformed circuit JSON; provide a JSON object without trailing text.'); }
  }
  let entries = 0;
  let characters = 0;
  const ancestors = new Set<object>();
  const visit = (value: unknown, depth: number): void => {
    if (++entries > CIRCUIT_INPUT_LIMITS.entries || depth > CIRCUIT_INPUT_LIMITS.depth) {
      throw new Error('Circuit input exceeds the nesting or entry limit.');
    }
    if (typeof value === 'string') characters += value.length;
    else if (typeof value === 'number' && !Number.isFinite(value)) throw new Error('Circuit input contains a non-finite number.');
    else if (value !== null && typeof value === 'object') {
      if (ancestors.has(value)) throw new Error('Circuit input contains a cyclic object reference.');
      if (!Array.isArray(value) && ![Object.prototype, null].includes(Object.getPrototypeOf(value))) {
        throw new Error('Circuit input must contain only JSON records and arrays.');
      }
      if (Array.isArray(value) && value.length > CIRCUIT_INPUT_LIMITS.entries) {
        throw new Error('Circuit input exceeds the entry limit.');
      }
      ancestors.add(value);
      for (const key of Object.getOwnPropertyNames(value)) {
        characters += key.length;
        const descriptor = Object.getOwnPropertyDescriptor(value, key)!;
        if (!('value' in descriptor)) throw new Error('Circuit input cannot contain accessor properties.');
        visit(descriptor.value, depth + 1);
      }
      ancestors.delete(value);
    } else if (value !== null && !['string', 'number', 'boolean', 'undefined'].includes(typeof value)) {
      throw new Error('Circuit input contains a non-JSON value.');
    }
    if (characters > CIRCUIT_INPUT_LIMITS.characters) throw new Error('Circuit input exceeds the input size limit.');
  };
  visit(source, 0);
  return source;
}

function failedBuild(message: string): CircuitBuildResult {
  const validation: CircuitValidationResult = { valid: false, warnings: [], errors: [`Normalization: ${message}`] };
  return { circuit: { components: [], nets: [], connections: [], resolvedPins: [], validation }, validationSeed: validation };
}

function componentPosition(rawComponent: Record<string, unknown>, index: number): { x: number; y: number } {
  const position = isRecord(rawComponent.position) ? rawComponent.position : undefined;
  const x = toNumber(rawComponent.x) ?? toNumber(position?.x);
  const y = toNumber(rawComponent.y) ?? toNumber(position?.y);

  if (x !== undefined && y !== undefined) {
    return { x, y };
  }

  return {
    x: (index % DEFAULT_COMPONENT_COLUMNS) * DEFAULT_COMPONENT_SPACING_X,
    y: Math.floor(index / DEFAULT_COMPONENT_COLUMNS) * DEFAULT_COMPONENT_SPACING_Y,
  };
}

function componentRotation(rawComponent: Record<string, unknown>): number {
  const numericRotation = toNumber(rawComponent.rotation);

  if (numericRotation !== undefined) {
    return numericRotation;
  }

  const rotationText = toText(rawComponent.rotation);

  if (!rotationText) {
    return 0;
  }

  const match = rotationText.match(/^R([+-]?\d+(?:\.\d+)?)$/i);
  return match ? Number(match[1]) : 0;
}

function normalizeComponentType(rawType?: string, rawValue?: string): string | undefined {
  const typeKey = rawType?.trim().toLowerCase();
  const valueKey = rawValue?.trim().toLowerCase();

  const pnpValues = new Set(['pnp', '2n3906', 'bc557', 's8550']);
  const npnValues = new Set(['npn', 'bc547', '2n3904', '2n2222', 's8050']);

  // Value refines only a generic family, never an explicit unrelated type.
  if (typeKey === 'transistor' || typeKey === 'bjt') {
    if (valueKey && pnpValues.has(valueKey)) return 'pnp_transistor';
    if (valueKey && npnValues.has(valueKey)) return 'npn_transistor';
  }
  if (typeKey === 'ic') {
    return valueKey && ['ne555', '555', 'ne555p', 'lm555'].includes(valueKey) ? 'ne555' : 'ic';
  }

  const aliases: Record<string, string> = {
    resistor: 'resistor',
    res: 'resistor',
    r: 'resistor',
    capacitor: 'capacitor',
    cap: 'capacitor',
    c: 'capacitor',
    inductor: 'inductor',
    ind: 'inductor',
    l: 'inductor',
    diode: 'diode',
    led: 'led',
    d: 'diode',
    transistor: 'npn_transistor',
    npn: 'npn_transistor',
    bjt: 'npn_transistor',
    bc547: 'npn_transistor',
    pnp: 'pnp_transistor',
    bc557: 'pnp_transistor',
    voltage: 'voltage_source',
    voltage_source: 'voltage_source',
    vsource: 'voltage_source',
    v: 'voltage_source',
    current: 'current_source',
    current_source: 'current_source',
    isource: 'current_source',
    i: 'current_source',
    ground: 'ground',
    gnd: 'ground',
    '0': 'ground',
    // NE555 / timer IC aliases
    ne555: 'ne555',
    '555': 'ne555',
    timer: 'ne555',
    '555timer': 'ne555',
  };

  if (typeKey && Object.prototype.hasOwnProperty.call(aliases, typeKey)) {
    return aliases[typeKey];
  }

  return typeKey;
}

function extractRoot(source: unknown): Record<string, unknown> {
  if (!isRecord(source)) {
    return {};
  }

  if (isRecord(source.circuit)) {
    return source.circuit;
  }

  if (isRecord(source.data) && isRecord(source.data.circuit)) {
    return source.data.circuit;
  }

  return source;
}

function readComponents(root: Record<string, unknown>): Record<string, unknown>[] {
  const candidates = [root.components, root.nodes];

  for (const candidate of candidates) {
    if (Array.isArray(candidate)) {
      return candidate.filter(isRecord);
    }
  }

  return [];
}

function readWires(root: Record<string, unknown>): Record<string, unknown>[] {
  const candidates = [root.wires, root.connections, root.edges];

  for (const candidate of candidates) {
    if (Array.isArray(candidate)) {
      return candidate.filter(isRecord);
    }
  }

  return [];
}

function normalizeComponentInput(rawComponent: Record<string, unknown>, index: number): NormalizedComponentInput {
  return {
    rawIndex: index,
    reference: toText(rawComponent.id) ?? toText(rawComponent.reference) ?? toText(rawComponent.name),
    rawType: toText(rawComponent.type) ?? toText(rawComponent.component_type) ?? toText(rawComponent.kind),
    rawValue: toText(rawComponent.value),
    canonicalType: normalizeComponentType(
      toText(rawComponent.type) ?? toText(rawComponent.component_type) ?? toText(rawComponent.kind),
      toText(rawComponent.value),
    ),
    position: componentPosition(rawComponent, index),
    rotation: componentRotation(rawComponent),
    mirror: toBoolean(rawComponent.mirror) ?? false,
  };
}

function normalizeWireInput(rawWire: Record<string, unknown>, index: number): NormalizedWireInput {
  return {
    rawIndex: index,
    id: toText(rawWire.id),
    raw: rawWire,
  };
}

function pinKey(componentId: string, pinId: string): string {
  return endpointKey({ componentId, pinId });
}

function buildPinAliases(component: Component): Map<string, string> {
  const aliases = new Map<string, string>();

  component.pins.forEach((pin) => {
    aliases.set(pin.id.toUpperCase(), pin.id);
    aliases.set(pin.name.toUpperCase(), pin.id);
  });

  if (component.type === 'npn_transistor' || component.type === 'pnp_transistor') {
    // Canonical IDs: C, B, E
    aliases.set('C', 'C');
    aliases.set('B', 'B');
    aliases.set('E', 'E');
    // Semantic name aliases
    aliases.set('BASE', 'B');
    aliases.set('COLLECTOR', 'C');
    aliases.set('EMITTER', 'E');
    // Legacy lowercase semantic aliases (from old pin IDs)
    aliases.set('COLLECTOR', 'C');
    aliases.set('BASE', 'B');
    aliases.set('EMITTER', 'E');
    // Numeric aliases per standard BJT pinout (C=1, B=2, E=3)
    aliases.set('1', 'C');
    aliases.set('2', 'B');
    aliases.set('3', 'E');
  }

  if (component.type === 'resistor' || component.type === 'capacitor' || component.type === 'inductor') {
    aliases.set('LEFT', '1');
    aliases.set('RIGHT', '2');
    aliases.set('A', '1');
    aliases.set('K', '2');
    aliases.set('PLUS', '1');
    aliases.set('POS', '1');
    aliases.set('MINUS', '2');
    aliases.set('NEG', '2');
  }

  if (component.type === 'diode') {
    aliases.set('1', '1');
    aliases.set('2', '2');
    aliases.set('A', '1');
    aliases.set('ANODE', '1');
    aliases.set('PLUS', '1');
    aliases.set('POS', '1');
    aliases.set('K', '2');
    aliases.set('CATHODE', '2');
    aliases.set('MINUS', '2');
    aliases.set('NEG', '2');
  }

  if (component.type === 'led') {
    // Canonical IDs: A, K
    aliases.set('A', 'A');
    aliases.set('K', 'K');
    // Semantic aliases
    aliases.set('ANODE', 'A');
    aliases.set('CATHODE', 'K');
    aliases.set('PLUS', 'A');
    aliases.set('POS', 'A');
    aliases.set('POSITIVE', 'A');
    aliases.set('MINUS', 'K');
    aliases.set('NEG', 'K');
    aliases.set('NEGATIVE', 'K');
    // Numeric aliases
    aliases.set('1', 'A');
    aliases.set('2', 'K');
  }

  if (component.type === 'voltage_source' || component.type === 'current_source') {
    aliases.set('+', '+');
    aliases.set('PLUS', '+');
    aliases.set('POSITIVE', '+');
    aliases.set('POS', '+');
    aliases.set('-', '-');
    aliases.set('MINUS', '-');
    aliases.set('NEGATIVE', '-');
    aliases.set('NEG', '-');
    aliases.set('1', '+');
    aliases.set('2', '-');
  }

  if (component.type === 'ground') {
    aliases.set('0', '0');
    aliases.set('1', '0');
    aliases.set('GND', '0');
    aliases.set('GROUND', '0');
  }

  if (component.type === 'ne555') {
    // Canonical IDs: 1-8
    for (let i = 1; i <= 8; i++) {
      aliases.set(String(i), String(i));
    }
    // Semantic name aliases for common pins
    aliases.set('GND', '1');
    aliases.set('GROUND', '1');
    aliases.set('TRIG', '2');
    aliases.set('TRIGGER', '2');
    aliases.set('OUT', '3');
    aliases.set('OUTPUT', '3');
    aliases.set('RESET', '4');
    aliases.set('RST', '4');
    aliases.set('CTRL', '5');
    aliases.set('CONTROL', '5');
    aliases.set('CV', '5');
    aliases.set('THR', '6');
    aliases.set('THRESH', '6');
    aliases.set('THRESHOLD', '6');
    aliases.set('DIS', '7');
    aliases.set('DISCHARGE', '7');
    aliases.set('VCC', '8');
    aliases.set('VDD', '8');
    aliases.set('PWR', '8');
    aliases.set('POWER', '8');
  }

  return aliases;
}

function resolvePinId(component: Component, rawPinId: string): string | undefined {
  const aliases = buildPinAliases(component);
  return aliases.get(rawPinId.trim().toUpperCase());
}

function parseEndpointReference(
  rawEndpoint: unknown,
  componentsById: Map<string, Component>,
  warnings: string[],
  errors: string[],
  wireDescription: string,
  endpointRole: 'source' | 'target',
): EndpointReference | undefined {
  const validToken = (value: unknown): boolean => {
    const token = toText(value);
    return !!token && token.length <= CIRCUIT_INPUT_LIMITS.identifier && !/[\x00-\x1f\x7f]/.test(token) &&
      (typeof value === 'string' || (typeof value === 'number' && Number.isSafeInteger(value)));
  };
  if (isRecord(rawEndpoint)) {
    const identityFields = ['componentId', 'component', 'reference', 'id', 'pinId', 'pin', 'handle', 'label', 'net'];
    if (identityFields.some(field => field in rawEndpoint && !validToken(rawEndpoint[field])) ||
        ('name' in rawEndpoint && !identityFields.some(field => field in rawEndpoint) && !validToken(rawEndpoint.name))) {
      errors.push(`Wire ${wireDescription} has an invalid or oversized ${endpointRole} endpoint identity.`);
      return undefined;
    }
    const componentFields = ['componentId', 'component', 'reference', 'id'];
    const pinFields = ['pinId', 'pin', 'handle'];
    const componentIds = componentFields.filter(field => field in rawEndpoint).map(field => toText(rawEndpoint[field]));
    const rawPinIds = pinFields.filter(field => field in rawEndpoint).map(field => toText(rawEndpoint[field]));
    const componentId = componentIds[0];
    const rawPinId = rawPinIds[0];
    const labelFields = ['label', 'net', ...(componentIds.length === 0 && rawPinIds.length === 0 ? ['name'] : [])];
    const labels = labelFields.filter(field => field in rawEndpoint).map(field => toText(rawEndpoint[field]));
    if (labels.length > 0) {
      if (componentIds.length > 0 || rawPinIds.length > 0 || labels.some(label => !label) ||
          new Set(labels.map(label => canonicalLabel(label ?? ''))).size > 1) {
        errors.push(`Wire ${wireDescription} has contradictory or malformed label/pin fields on its ${endpointRole} endpoint.`);
        return undefined;
      }
      return { kind: 'label', label: labels[0]! };
    }
    if (componentIds.length > 0 && (componentIds.some(id => !id) ||
        new Set(componentIds.map(id => componentsById.get(id!)?.id ?? id)).size > 1)) {
      errors.push(`Wire ${wireDescription} has contradictory component fields on its ${endpointRole} endpoint.`);
      return undefined;
    }

    if (componentId) {
      const component = componentsById.get(componentId);

      if (!component) {
        errors.push(`Wire ${wireDescription} references missing component ${componentId} on its ${endpointRole} endpoint.`);
        return undefined;
      }

      if (rawPinIds.length > 0 && (rawPinIds.some(id => !id || !resolvePinId(component, id)) ||
          new Set(rawPinIds.map(id => resolvePinId(component, id!))).size > 1)) {
        errors.push(`Wire ${wireDescription} has contradictory or invalid pin fields for ${component.id} on its ${endpointRole} endpoint.`);
        return undefined;
      }

      if (!rawPinId) {
        if (component.pins.length === 1) {
          return { kind: 'pin', componentId: component.id, pinId: component.pins[0].id };
        }

        errors.push(`Wire ${wireDescription} is missing a pin reference for ${componentId} on its ${endpointRole} endpoint.`);
        return undefined;
      }

      const pinId = resolvePinId(component, rawPinId);

      if (!pinId) {
        errors.push(`Wire ${wireDescription} references invalid pin ${componentId}.${rawPinId} on its ${endpointRole} endpoint.`);
        return undefined;
      }

      return { kind: 'pin', componentId: component.id, pinId };
    }
  }

  const text = toText(rawEndpoint);

  if (!text) {
    errors.push(`Wire ${wireDescription} is missing its ${endpointRole} reference.`);
    return undefined;
  }

  const separatorIndex = text.indexOf('.');
  if (separatorIndex < 0 ? !validToken(rawEndpoint) :
      !validToken(text.slice(0, separatorIndex)) || !validToken(text.slice(separatorIndex + 1))) {
    errors.push(`Wire ${wireDescription} has an invalid or oversized ${endpointRole} endpoint identity.`);
    return undefined;
  }

  if (separatorIndex >= 0) {
    const componentId = text.slice(0, separatorIndex).trim();
    const rawPinId = text.slice(separatorIndex + 1).trim();
    const component = componentsById.get(componentId);

    if (!component) {
      errors.push(`Wire ${wireDescription} references missing component ${componentId} on its ${endpointRole} endpoint.`);
      return undefined;
    }

    const pinId = resolvePinId(component, rawPinId);

    if (!pinId) {
      errors.push(`Wire ${wireDescription} references invalid pin ${componentId}.${rawPinId} on its ${endpointRole} endpoint.`);
      return undefined;
    }

    return { kind: 'pin', componentId: component.id, pinId };
  }

  const directComponent = componentsById.get(text);

  if (directComponent) {
    if (directComponent.pins.length === 1) {
      return {
        kind: 'pin',
        componentId: directComponent.id,
        pinId: directComponent.pins[0].id,
      };
    }

    warnings.push(`Wire ${wireDescription} references component ${text} without a pin name; treating it as an invalid endpoint.`);
    errors.push(`Wire ${wireDescription} is missing a pin reference for ${text} on its ${endpointRole} endpoint.`);
    return undefined;
  }

  return {
    kind: 'label',
    label: text,
  };
}

function normalizeWireEndpoint(
  wire: NormalizedWireInput, role: 'source' | 'target', componentsById: Map<string, Component>,
  warnings: string[], errors: string[],
): EndpointReference | undefined {
  const fields = role === 'source' ? ['source', 'from', 'start'] : ['target', 'to', 'destination', 'end'];
  const description = wire.id ?? `#${wire.rawIndex + 1}`;
  const handleField = `${role}Handle`;
  const hasHandle = handleField in wire.raw;
  const candidates: EndpointReference[] = [];
  const before = errors.length;
  fields.filter(field => field in wire.raw).forEach(field => {
    let raw = wire.raw[field];
    if (field === role && hasHandle) {
      const handle = toText(wire.raw[handleField]);
      if (!handle || !toText(raw)) {
        errors.push(`Wire ${description} has a malformed React Flow ${role}/handle pair.`);
        return;
      }
      const text = toText(raw)!;
      // A dotted source is also accepted, but must agree with the handle.
      if (componentsById.has(text) || !text.includes('.')) {
        raw = { componentId: text, pinId: handle };
      } else {
        const parsed = parseEndpointReference(raw, componentsById, warnings, errors, description, role);
        if (parsed?.kind !== 'pin' || resolvePinId(componentsById.get(parsed.componentId)!, handle) !== parsed.pinId) {
          errors.push(`Wire ${description} has contradictory ${role} and ${handleField} fields.`);
          return;
        }
        candidates.push(parsed);
        return;
      }
    }
    const parsed = parseEndpointReference(raw, componentsById, warnings, errors, description, role);
    if (parsed) candidates.push(parsed);
  });
  if (hasHandle && !(role in wire.raw)) errors.push(`Wire ${description} has ${handleField} without ${role}.`);
  if (candidates.length === 0 && errors.length === before) {
    errors.push(`Wire ${description} is missing its ${role} reference.`);
  }
  const keys = candidates.map(endpoint => endpointKey(endpoint.kind === 'label'
    ? labelConnection(endpoint.label) : endpoint));
  if (new Set(keys).size > 1) errors.push(`Wire ${description} has contradictory ${role} endpoint fields after canonicalization.`);
  return errors.length === before ? candidates[0] : undefined;
}

function toVisualConnection(source: EndpointReference, target: EndpointReference, id?: string): VisualConnection {
  return {
    id,
    source: source.kind === 'label' ? labelConnection(source.label) : { componentId: source.componentId, pinId: source.pinId },
    target: target.kind === 'label' ? labelConnection(target.label) : { componentId: target.componentId, pinId: target.pinId },
    sourceLabel: source.kind === 'label' ? source.label : undefined,
    targetLabel: target.kind === 'label' ? target.label : undefined,
  };
}

function extractLabels(net: Net, labelsByIdentity: Map<string, Set<string>>): Net {
  const labels: string[] = [];
  const pins: PinConnection[] = [];

  net.pins.forEach((pin) => {
    if (isLabelConnection(pin)) {
      labels.push(...(labelsByIdentity.get(pin.componentId) ?? [pin.componentId.slice(LABEL_COMPONENT_PREFIX.length)]));
      return;
    }

    pins.push(pin);
  });

  const uniqueLabels = Array.from(new Set(labels));
  const sortedLabels = [...uniqueLabels].sort();

  return {
    ...net,
    name: sortedLabels[0] ?? net.id,
    labels: sortedLabels.length > 0 ? sortedLabels : undefined,
    pins,
  };
}

function assignNetReferences(components: Component[], nets: Net[], resolvedPins: CompiledCircuit['resolvedPins']): void {
  const netByPin = new Map<string, string>();

  nets.forEach((net) => {
    net.pins.forEach((pin) => {
      netByPin.set(pinKey(pin.componentId, pin.pinId), net.id);
    });
  });

  components.forEach((component) => {
    component.pins = component.pins.map((pin) => ({
      ...pin,
      net: netByPin.get(pinKey(component.id, pin.id)),
    }));
  });

  resolvedPins.forEach((pin) => {
    pin.net = netByPin.get(pinKey(pin.componentId, pin.id));
  });
}

export class CircuitBuilder {
  static build(source: unknown): CompiledCircuit {
    return CircuitBuilder.buildDetailed(source).circuit;
  }

  static buildDetailed(source: unknown): CircuitBuildResult {
    try { source = prepareSource(source); }
    catch (error) { return failedBuild(error instanceof Error ? error.message : 'Invalid circuit input.'); }
    if (!isRecord(source)) return failedBuild('Circuit input must be a record.');
    if ('circuit' in source && !isRecord(source.circuit)) return failedBuild('Circuit wrapper must contain a record.');
    if ('data' in source && (!isRecord(source.data) || ('circuit' in source.data && !isRecord(source.data.circuit)))) {
      return failedBuild('Circuit data wrapper must contain a record.');
    }
    const root = extractRoot(source);
    for (const fields of [['components', 'nodes'], ['wires', 'connections', 'edges']]) {
      const present = fields.filter(key => key in root);
      for (const field of present) {
        const entries = root[field];
        if (!Array.isArray(entries)) return failedBuild(`Circuit ${field} must be an array.`);
        const limit = fields[0] === 'components' ? CIRCUIT_INPUT_LIMITS.components : CIRCUIT_INPUT_LIMITS.wires;
        if (entries.length > limit) return failedBuild(`Circuit ${field} exceeds the limit of ${limit}.`);
        for (let index = 0; index < entries.length; index++) {
          if (!isRecord(entries[index])) return failedBuild(`Malformed ${field} at index ${index}; expected a record.`);
        }
      }
      if (present.some(field => JSON.stringify(root[field]) !== JSON.stringify(root[present[0]]))) {
        return failedBuild(`Contradictory circuit collections: ${present.join(', ')}.`);
      }
    }
    const componentInputs = readComponents(root).map(normalizeComponentInput);
    const wireInputs = readWires(root).map(normalizeWireInput);
    const warnings: string[] = [];
    const errors: string[] = [];
    const components: Component[] = [];
    const componentsById = new Map<string, Component>();
    const componentIdCounts = new Map<string, number>();
    const reservedIds = new Set(componentInputs.map(input => input.reference).filter((id): id is string => !!id));
    const localCounters = new Map<string, number>();
    const rawComponents = readComponents(root);
    const validIdentity = (value: unknown): boolean => {
      const text = toText(value);
      return !!text && (typeof value === 'string' || (typeof value === 'number' && Number.isSafeInteger(value))) &&
        text.length <= CIRCUIT_INPUT_LIMITS.identifier && !/[\x00-\x1f\x7f]/.test(text);
    };
    for (const [index, raw] of rawComponents.entries()) {
      const description = toText(raw.id) ?? toText(raw.reference) ?? `#${index + 1}`;
      for (const field of ['id', 'reference', 'name']) {
        if (field in raw && !validIdentity(raw[field])) return failedBuild(`Invalid ${field} on component ${description}.`);
      }
      const types = ['type', 'component_type', 'kind'].filter(field => field in raw);
      if (types.some(field => typeof raw[field] !== 'string' || !validIdentity(raw[field])) ||
          new Set(types.map(field => normalizeComponentType(toText(raw[field]), toText(raw.value)))).size > 1) {
        return failedBuild(`Contradictory or malformed type on component ${description}.`);
      }
      if ('position' in raw && !isRecord(raw.position)) return failedBuild(`Invalid position on component ${description}.`);
      const position = isRecord(raw.position) ? raw.position : {};
      if (('x' in raw || 'x' in position) !== ('y' in raw || 'y' in position)) {
        return failedBuild(`Incomplete position on component ${description}.`);
      }
      for (const field of ['x', 'y']) {
        for (const record of [raw, position]) {
          if (field in record && (toNumber(record[field]) === undefined || Math.abs(toNumber(record[field])!) > CIRCUIT_INPUT_LIMITS.coordinate)) {
            return failedBuild(`Invalid or out-of-range ${field} on component ${description}.`);
          }
        }
        if (field in raw && field in position && toNumber(raw[field]) !== toNumber(position[field])) {
          return failedBuild(`Contradictory ${field} coordinates on component ${description}.`);
        }
      }
      if ('rotation' in raw && (toNumber(raw.rotation) === undefined &&
          !(typeof raw.rotation === 'string' && /^R[+-]?\d+(?:\.\d+)?$/i.test(raw.rotation.trim())) ||
          Math.abs(componentRotation(raw)) > CIRCUIT_INPUT_LIMITS.coordinate)) {
        return failedBuild(`Invalid rotation on component ${description}.`);
      }
      if ('mirror' in raw && toBoolean(raw.mirror) === undefined) return failedBuild(`Invalid mirror on component ${description}.`);
      if (raw.value != null && typeof raw.value !== 'string' && typeof raw.value !== 'number') {
        return failedBuild(`Invalid value on component ${description}.`);
      }
    }
    const wireIds = new Set<string>();
    for (const wire of wireInputs) {
      if ('id' in wire.raw && (!validIdentity(wire.raw.id) || wireIds.has(wire.id!))) {
        return failedBuild(`Invalid or duplicate wire ID at index ${wire.rawIndex}.`);
      }
      if (wire.id) wireIds.add(wire.id);
    }
    if (componentInputs.length === 0 && wireInputs.length === 0) warnings.push('Circuit is empty: no components or connections.');

    componentInputs.forEach((input) => {
      if (!input.reference) {
        warnings.push(`Missing reference for component at index ${input.rawIndex}; generated reference will be used.`);
      }

      if (!input.rawValue) {
        warnings.push(
          `Missing value for component ${input.reference ?? `#${input.rawIndex + 1}`}; library default will be used when available.`,
        );
      }

      if (!input.rawType) {
        errors.push(`Missing component type for component ${input.reference ?? `#${input.rawIndex + 1}`}.`);
        return;
      }

      if (!input.canonicalType || !componentLibrary.has(input.canonicalType)) {
        errors.push(
          `Unknown component type '${input.rawType}' on component ${input.reference ?? `#${input.rawIndex + 1}`}.`,
        );
        return;
      }

      let id = input.reference;
      if (!id) {
        const prefix = componentLibrary.getDefinition(input.canonicalType)!.prefix;
        let next = localCounters.get(prefix) ?? 0;
        do { next++; id = `${prefix}${next}`; } while (reservedIds.has(id));
        localCounters.set(prefix, next);
        reservedIds.add(id);
      }
      if (id.startsWith(LABEL_COMPONENT_PREFIX)) errors.push(`Component ID ${id} uses the reserved label identity prefix.`);
      const component = componentLibrary.createComponent(input.canonicalType, {
        id,
        name: input.reference,
        value: input.rawValue,
        position: input.position,
        rotation: input.rotation,
        mirror: input.mirror,
      });

      components.push(component);

      const duplicateCount = (componentIdCounts.get(component.id) ?? 0) + 1;
      componentIdCounts.set(component.id, duplicateCount);

      if (duplicateCount > 1) {
        errors.push(`Duplicate component ID detected: ${component.id}.`);
      }

      if (!componentsById.has(component.id)) {
        componentsById.set(component.id, component);
      }
    });

    // Resolve reference/name aliases only when they identify exactly one component.
    const aliasOwners = new Map<string, Set<string>>();
    rawComponents.forEach(raw => {
      const id = toText(raw.id) ?? toText(raw.reference) ?? toText(raw.name);
      if (!id || !componentsById.has(id)) return;
      [raw.reference, raw.name].forEach(value => {
        const alias = toText(value);
        if (!alias) return;
        const owners = aliasOwners.get(alias) ?? new Set<string>();
        owners.add(id);
        aliasOwners.set(alias, owners);
      });
    });
    aliasOwners.forEach((owners, alias) => {
      const direct = componentsById.get(alias);
      if (owners.size > 1 || (direct && !owners.has(direct.id))) {
        errors.push(`Ambiguous component alias/ID collision: ${alias}.`);
      } else if (!direct) componentsById.set(alias, componentsById.get([...owners][0])!);
    });
    const resolvedPins = components.flatMap((component) => resolvePins(component));
    const visualConnections: VisualConnection[] = [];
    const labelsByIdentity = new Map<string, Set<string>>();
    wireInputs.forEach(wireInput => {
      const sourceReference = normalizeWireEndpoint(wireInput, 'source', componentsById, warnings, errors);
      const targetReference = normalizeWireEndpoint(wireInput, 'target', componentsById, warnings, errors);
      if (!sourceReference || !targetReference) return;
      const connection = toVisualConnection(sourceReference, targetReference, wireInput.id);
      visualConnections.push(connection);
      // Keep every equivalent field's label spelling, without altering its identity.
      for (const role of ['source', 'target'] as const) {
        const endpoint = connection[role];
        if (!isLabelConnection(endpoint)) continue;
        const texts = labelsByIdentity.get(endpoint.componentId) ?? new Set<string>();
        const fields = role === 'source' ? ['source', 'from', 'start'] : ['target', 'to', 'destination', 'end'];
        fields.forEach(field => {
          if (!(field in wireInput.raw)) return;
          const parsed = parseEndpointReference(wireInput.raw[field], componentsById, [], [], '', role);
          if (parsed?.kind === 'label') texts.add(parsed.label);
        });
        labelsByIdentity.set(endpoint.componentId, texts);
      }
    });

    const nets = buildNets(visualConnections)
      .map(net => extractLabels(net, labelsByIdentity))
      .filter((net) => net.pins.length > 0 || (net.labels?.length ?? 0) > 0);

    assignNetReferences(components, nets, resolvedPins);

    const circuit: CompiledCircuit = {
      components,
      nets,
      connections: visualConnections,
      resolvedPins,
      validation: { valid: errors.length === 0, warnings: [...warnings], errors: [...errors] },
    };

    return {
      circuit,
      validationSeed: {
        warnings,
        errors,
      },
    };
  }
}
