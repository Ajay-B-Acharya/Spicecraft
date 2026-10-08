import { api } from './api';
import { ApiError } from './apiError';
import { CircuitCompiler } from './circuit/engine/CircuitCompiler';

export interface CircuitNode {
  [key: string]: unknown;
}

export interface CircuitComponent extends CircuitNode {
  id: string;
  type: string;
  value: string | null;
}

export interface CircuitWire extends CircuitNode {
  source?: unknown;
  destination?: unknown;
}

export interface Circuit {
  id: string;
  name: string;
  description: string;
  category: string;
  tags: string[];
  components: CircuitComponent[];
  wires: CircuitWire[];
}

type CircuitApiShape = Partial<Omit<Circuit, 'components' | 'wires'>> & {
  components?: CircuitNode[] | null;
  wires?: CircuitNode[] | null;
};

function serializeComponent(component: CircuitComponent): CircuitNode {
  return {
    ...component,
    reference: toDisplayString(component.reference ?? component.id, component.id),
    type: component.type,
    value: component.value,
  };
}

function serializeWire(wire: CircuitWire): CircuitNode {
  return { ...wire };
}

function toDisplayString(value: unknown, fallback = '-'): string {
  if (typeof value === 'string' && value.trim()) return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return fallback;
}

function normalizeComponent(component: CircuitNode, generatedId: string): CircuitComponent {
  return {
    ...component,
    id: generatedId,
    type: toDisplayString(component.type ?? component.component_type ?? component.kind),
    value:
      component.value === null || component.value === undefined
        ? null
        : String(component.value),
  };
}

function normalizeCircuit(circuit: CircuitApiShape): Circuit {
  if (!circuit || !Array.isArray(circuit.components) || !Array.isArray(circuit.wires)) {
    throw new ApiError('The API returned an invalid circuit document; components and wires must be arrays.', 502);
  }
  const compiled = CircuitCompiler.compile(circuit);
  if (!compiled.validation.valid) {
    throw new ApiError(`The API returned an invalid circuit.\n${compiled.validation.errors.join('\n')}`, 502, compiled.validation);
  }
  const tags = Array.isArray(circuit.tags)
    ? circuit.tags.map((tag) => toDisplayString(tag)).filter((tag) => tag !== '-')
    : [];

  return {
    id: toDisplayString(circuit.id, ''),
    name: toDisplayString(circuit.name, 'Untitled Circuit'),
    description: toDisplayString(circuit.description, 'No description available.'),
    category: toDisplayString(circuit.category, 'Uncategorized'),
    tags,
    components: circuit.components.map((component, index) => normalizeComponent(component, compiled.components[index].id)),
    wires: circuit.wires.map(wire => ({ ...wire })),
  };
}

export const circuitService = {
  async getCircuits(): Promise<Circuit[]> {
    const data = await api.get<CircuitApiShape[]>('/circuits');
    if (!Array.isArray(data)) throw new ApiError('The API returned an invalid circuit list.', 502);
    return data.map(normalizeCircuit);
  },

  async getCircuit(id: string): Promise<Circuit> {
    const data = await api.get<CircuitApiShape>(`/circuits/${encodeURIComponent(id)}`);
    return normalizeCircuit(data);
  },

  async updateCircuit(id: string, circuit: Circuit): Promise<Circuit> {
    const validation = CircuitCompiler.compile(circuit).validation;
    if (!validation.valid) throw new ApiError(`Cannot save an invalid circuit.\n${validation.errors.join('\n')}`, 422, validation);
    const payload = {
      id: circuit.id,
      name: circuit.name,
      description: circuit.description,
      category: circuit.category,
      tags: circuit.tags,
      components: circuit.components.map(serializeComponent),
      wires: circuit.wires.map(serializeWire),
    };

    const data = await api.put<CircuitApiShape>(`/circuits/${encodeURIComponent(id)}`, payload);
    return normalizeCircuit(data);
  },
};
