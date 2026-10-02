/**
 * Circuit builder.
 *
 * Parses AI-style circuit JSON, instantiates canonical components through the
 * ComponentLibrary, resolves pin geometry, translates wire references into
 * electrical nets through the NetBuilder, and returns a complete UI-independent
 * circuit object. The builder does not depend on React Flow.
 */
import { buildNets } from './NetBuilder';
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

const LABEL_COMPONENT_PREFIX = '__label__:';
const LABEL_PIN_ID = 'label';
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
  source: unknown;
  target: unknown;
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

  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }

  return undefined;
}

function toNumber(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === 'string') {
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

function emptyValidation(): CircuitValidationResult {
  return {
    valid: true,
    warnings: [],
    errors: [],
  };
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

  const match = rotationText.match(/-?\d+/);
  return match ? Number(match[0]) : 0;
}

function normalizeComponentType(rawType?: string, rawValue?: string): string | undefined {
  const typeKey = rawType?.trim().toLowerCase();
  const valueKey = rawValue?.trim().toLowerCase();

  const pnpValues = new Set(['pnp', '2n3906', 'bc557', 's8550']);
  const npnValues = new Set(['npn', 'bc547', '2n3904', '2n2222', 's8050']);

  if (valueKey && pnpValues.has(valueKey)) {
    return 'pnp_transistor';
  }

  if (valueKey && npnValues.has(valueKey)) {
    return 'npn_transistor';
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
    ic: 'ne555',
    timer: 'ne555',
    '555timer': 'ne555',
  };

  if (typeKey && aliases[typeKey]) {
    return aliases[typeKey];
  }

  if (valueKey && aliases[valueKey]) {
    return aliases[valueKey];
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
    source: rawWire.source ?? rawWire.from ?? rawWire.start,
    target: rawWire.target ?? rawWire.to ?? rawWire.destination ?? rawWire.end,
  };
}

function labelPinConnection(label: string): PinConnection {
  return {
    componentId: `${LABEL_COMPONENT_PREFIX}${label}`,
    pinId: LABEL_PIN_ID,
  };
}

function isLabelConnection(connection: PinConnection): boolean {
  return connection.componentId.startsWith(LABEL_COMPONENT_PREFIX);
}

function labelFromConnection(connection: PinConnection): string {
  return connection.componentId.slice(LABEL_COMPONENT_PREFIX.length);
}

function pinKey(componentId: string, pinId: string): string {
  return `${componentId}:${pinId}`;
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
  if (isRecord(rawEndpoint)) {
    const label = toText(rawEndpoint.label) ?? toText(rawEndpoint.net) ?? toText(rawEndpoint.name);
    if (label) {
      return { kind: 'label', label };
    }

    const componentId =
      toText(rawEndpoint.componentId) ?? toText(rawEndpoint.component) ?? toText(rawEndpoint.reference) ?? toText(rawEndpoint.id);
    const rawPinId = toText(rawEndpoint.pinId) ?? toText(rawEndpoint.pin) ?? toText(rawEndpoint.handle);

    if (componentId) {
      const component = componentsById.get(componentId);

      if (!component) {
        errors.push(`Wire ${wireDescription} references missing component ${componentId} on its ${endpointRole} endpoint.`);
        return undefined;
      }

      if (!rawPinId) {
        if (component.pins.length === 1) {
          return { kind: 'pin', componentId, pinId: component.pins[0].id };
        }

        errors.push(`Wire ${wireDescription} is missing a pin reference for ${componentId} on its ${endpointRole} endpoint.`);
        return undefined;
      }

      const pinId = resolvePinId(component, rawPinId);

      if (!pinId) {
        errors.push(`Wire ${wireDescription} references invalid pin ${componentId}.${rawPinId} on its ${endpointRole} endpoint.`);
        return undefined;
      }

      return { kind: 'pin', componentId, pinId };
    }
  }

  const text = toText(rawEndpoint);

  if (!text) {
    errors.push(`Wire ${wireDescription} is missing its ${endpointRole} reference.`);
    return undefined;
  }

  const separatorIndex = text.indexOf('.');

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

    return { kind: 'pin', componentId, pinId };
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

function toVisualConnection(source: EndpointReference, target: EndpointReference, id?: string): VisualConnection {
  return {
    id,
    source: source.kind === 'label' ? labelPinConnection(source.label) : { componentId: source.componentId, pinId: source.pinId },
    target: target.kind === 'label' ? labelPinConnection(target.label) : { componentId: target.componentId, pinId: target.pinId },
  };
}

function extractLabels(net: Net): Net {
  const labels: string[] = [];
  const pins: PinConnection[] = [];

  net.pins.forEach((pin) => {
    if (isLabelConnection(pin)) {
      labels.push(labelFromConnection(pin));
      return;
    }

    pins.push(pin);
  });

  const uniqueLabels = Array.from(new Set(labels));
  const sortedLabels = [...uniqueLabels].sort((left, right) => left.localeCompare(right));

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
    const netName = net.name ?? net.id;

    net.pins.forEach((pin) => {
      netByPin.set(pinKey(pin.componentId, pin.pinId), netName);
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
    const root = extractRoot(source);
    const componentInputs = readComponents(root).map(normalizeComponentInput);
    const wireInputs = readWires(root).map(normalizeWireInput);
    const warnings: string[] = [];
    const errors: string[] = [];
    const components: Component[] = [];
    const componentsById = new Map<string, Component>();
    const componentIdCounts = new Map<string, number>();

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

      const component = componentLibrary.createComponent(input.canonicalType, {
        id: input.reference,
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

    const resolvedPins = components.flatMap((component) => resolvePins(component));

    const visualConnections: VisualConnection[] = [];

    wireInputs.forEach((wireInput) => {
      const wireDescription = wireInput.id ?? `#${wireInput.rawIndex + 1}`;
      const sourceReference = parseEndpointReference(
        wireInput.source,
        componentsById,
        warnings,
        errors,
        wireDescription,
        'source',
      );
      const targetReference = parseEndpointReference(
        wireInput.target,
        componentsById,
        warnings,
        errors,
        wireDescription,
        'target',
      );

      if (!sourceReference || !targetReference) {
        return;
      }

      visualConnections.push(toVisualConnection(sourceReference, targetReference, wireInput.id));
    });

    const nets = buildNets(visualConnections)
      .map(extractLabels)
      .filter((net) => net.pins.length > 0 || (net.labels?.length ?? 0) > 0);

    assignNetReferences(components, nets, resolvedPins);

    const circuit: CompiledCircuit = {
      components,
      nets,
      resolvedPins,
      validation: emptyValidation(),
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
