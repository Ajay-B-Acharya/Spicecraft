/** Adapts compiled electrical nets into editable pin-to-pin schematic nodes. */
import type { Node, Edge } from '@xyflow/react';
import { CircuitCompiler } from '@/lib/circuit/engine/CircuitCompiler';
import type { Circuit } from '@/lib/circuitService';
import type { CircuitValidationResult } from '@/lib/circuit/types';

const STEP_X = 220;
const STEP_Y = 160;

/** Derives a visual view without altering the source circuit or its connectivity. */
export function buildCircuitFlow(circuit: Circuit): { nodes: Node[]; edges: Edge[]; validation: CircuitValidationResult } {
  const compiled = CircuitCompiler.compile(circuit);
  if (!compiled.validation.valid) return { nodes: [], edges: [], validation: compiled.validation };
  const positions = new Map<string, { x: number; y: number }>();
  const netsFor = (id: string) => compiled.nets.filter(net => net.pins.some(pin => pin.componentId === id));
  const hasLabel = (id: string, pattern: RegExp) => netsFor(id).some(net =>
    [net.name ?? '', ...(net.labels ?? [])].some(label => pattern.test(label)),
  );
  const occupied = new Set<string>();
  const place = (id: string, col: number, row: number) => {
    while (occupied.has(`${col},${row}`)) col++;
    occupied.add(`${col},${row}`);
    positions.set(id, { x: STEP_X * col + 80, y: STEP_Y * row + 80 });
  };

  // Anchor each transistor stage, then group supporting parts by terminal nets.
  const transistors = compiled.components.filter(c => /^(npn|pnp)_transistor$/.test(c.type));
  transistors.forEach((transistor, stage) => {
    const col = stage * 5 + 2;
    place(transistor.id, col, 2);
    const terminal = (name: string) => compiled.nets.find(net => net.pins.some(ref =>
      ref.componentId === transistor.id && transistor.pins.find(pin => pin.id === ref.pinId)?.name === name,
    ));
    for (const name of ['base', 'collector', 'emitter']) {
      const net = terminal(name);
      if (!net) continue;
      compiled.components.filter(c => c.id !== transistor.id && !positions.has(c.id) &&
        net.pins.some(pin => pin.componentId === c.id)).forEach(component => {
        const supply = hasLabel(component.id, /^(VCC|VDD|VEE|V\+|V-)$/i);
        const ground = hasLabel(component.id, /^(GND|GROUND|0)$/i);
        if (name === 'base') place(component.id, col - 1, supply ? 1 : ground ? 3 : 2);
        else if (name === 'collector') place(component.id, col + (component.type === 'capacitor' ? 1 : 0), component.type === 'capacitor' ? 2 : 1);
        else place(component.id, col, 3);
      });
    }
  });
  compiled.components.forEach((component, index) => {
    if (!positions.has(component.id)) place(component.id, index % 4, Math.floor(index / 4) + 1);
  });

  const nodes: Node[] = compiled.components.map(component => {
    const raw = circuit.components.find(c => c.id === component.id || c.reference === component.id);
    const saved = raw?.position as { x?: unknown; y?: unknown } | undefined;
    const x = saved?.x ?? raw?.x;
    const y = saved?.y ?? raw?.y;
    return {
      id: component.id,
      type: 'unified',
      position: typeof x === 'number' && Number.isFinite(x) && typeof y === 'number' && Number.isFinite(y)
        ? { x, y } : positions.get(component.id)!,
      data: { reference: component.id, value: component.value, type: component.type, componentType: component.type },
    };
  });
  const edges: Edge[] = [];
  const connect = (source: string, sourceHandle: string, target: string, targetHandle: string, netId: string) => {
    edges.push({
      id: JSON.stringify([netId, source, sourceHandle, target, targetHandle]),
      source, sourceHandle, target, targetHandle,
      type: 'smoothstep', data: { netId }, style: { stroke: '#7c3aed', strokeWidth: 2 },
      deletable: false,
    });
  };
  compiled.nets.forEach((net, index) => {
    const pins = net.pins; // Compiler validation guarantees every endpoint exists.
    for (let i = 1; i < pins.length; i++) {
      connect(pins[0].componentId, pins[0].pinId, pins[i].componentId, pins[i].pinId, net.id);
    }
    (net.labels ?? []).forEach((label, labelIndex) => {
      const id = `net-label:${JSON.stringify([net.id, label])}`;
      const ground = /^(GND|GROUND|0)$/i.test(label);
      const supply = /^(VCC|VDD|VEE|V\+|V-)$/i.test(label);
      const xs = nodes.filter(node => pins.some(pin => pin.componentId === node.id)).map(node => node.position.x);
      const maxY = Math.max(80, ...nodes.map(node => node.position.y));
      nodes.push({ id, type: 'unified', position: {
        x: supply || ground ? (xs[0] ?? 80) + labelIndex * STEP_X : Math.max(80, ...nodes.map(node => node.position.x)) + STEP_X,
        y: supply ? 0 : ground ? maxY + STEP_Y : STEP_Y * (index + 1),
      }, data: { reference: label, netLabel: true }, draggable: false });
      if (pins[0]) connect(id, 'net', pins[0].componentId, pins[0].pinId, net.id);
    });
  });
  return { nodes, edges, validation: compiled.validation };
}
