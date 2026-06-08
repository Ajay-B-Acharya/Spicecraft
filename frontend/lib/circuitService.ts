import { api } from './api';

export interface CircuitNode {
  [key: string]: unknown;
}

export interface CircuitComponent extends CircuitNode {
  id: string;
  type: string;
  value: string | null;
}

export interface CircuitWire extends CircuitNode {
  source: string;
  destination: string;
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
  return {
    ...wire,
    from: toDisplayString(wire.from ?? wire.source, wire.source),
    to: toDisplayString(wire.to ?? wire.destination, wire.destination),
  };
}

function toDisplayString(value: unknown, fallback = '-'): string {
  if (typeof value === 'string' && value.trim()) return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return fallback;
}

function normalizeComponent(component: CircuitNode, index: number): CircuitComponent {
  return {
    ...component,
    id: toDisplayString(component.id ?? component.reference ?? component.name, `C${index + 1}`),
    type: toDisplayString(component.type ?? component.component_type ?? component.kind),
    value:
      component.value === null || component.value === undefined
        ? null
        : toDisplayString(component.value),
  };
}

function normalizeWire(wire: CircuitNode, index: number): CircuitWire {
  return {
    ...wire,
    source: toDisplayString(wire.source ?? wire.from ?? wire.start, `Node ${index + 1}`),
    destination: toDisplayString(wire.destination ?? wire.to ?? wire.end),
  };
}

function normalizeCircuit(circuit: CircuitApiShape): Circuit {
  const tags = Array.isArray(circuit.tags)
    ? circuit.tags.map((tag) => toDisplayString(tag)).filter((tag) => tag !== '-')
    : [];

  return {
    id: toDisplayString(circuit.id, ''),
    name: toDisplayString(circuit.name, 'Untitled Circuit'),
    description: toDisplayString(circuit.description, 'No description available.'),
    category: toDisplayString(circuit.category, 'Uncategorized'),
    tags,
    components: Array.isArray(circuit.components)
      ? circuit.components.map(normalizeComponent)
      : [],
    wires: Array.isArray(circuit.wires) ? circuit.wires.map(normalizeWire) : [],
  };
}

export const circuitService = {
  async getCircuits(): Promise<Circuit[]> {
    const data = await api.get<CircuitApiShape[]>('/circuits');
    return data.map(normalizeCircuit);
  },

  async getCircuit(id: string): Promise<Circuit> {
    const data = await api.get<CircuitApiShape>(`/circuits/${id}`);
    return normalizeCircuit(data);
  },

  async updateCircuit(id: string, circuit: Circuit): Promise<Circuit> {
    const payload = {
      id: circuit.id,
      name: circuit.name,
      description: circuit.description,
      category: circuit.category,
      tags: circuit.tags,
      components: circuit.components.map(serializeComponent),
      wires: circuit.wires.map(serializeWire),
    };

    const data = await api.put<CircuitApiShape>(`/circuits/${id}`, payload);
    return normalizeCircuit(data);
  },
};
