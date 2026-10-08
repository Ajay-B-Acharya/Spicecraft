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
  const netsByComponent = new Map<string, typeof compiled.nets>();
  compiled.nets.forEach(net => {
    new Set(net.pins.map(pin => pin.componentId)).forEach(id => {
      const nets = netsByComponent.get(id) ?? [];
      nets.push(net);
      netsByComponent.set(id, nets);
    });
  });
  const netsFor = (id: string) => netsByComponent.get(id) ?? [];
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
      position: x !== undefined && y !== undefined ? { ...component.position } : positions.get(component.id)!,
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
  const nodeIds = new Set(nodes.map(node => node.id));
  const nodePositions = new Map(nodes.map(node => [node.id, node.position]));
  let maxX = Math.max(80, ...nodes.map(node => node.position.x));
  let maxY = Math.max(80, ...nodes.map(node => node.position.y));
  compiled.nets.forEach((net, index) => {
    const pins = net.pins; // Compiler validation guarantees every endpoint exists.
    const anchorX = pins.map(pin => nodePositions.get(pin.componentId)?.x).find(x => x !== undefined) ?? 80;
    for (let i = 1; i < pins.length; i++) {
      connect(pins[0].componentId, pins[0].pinId, pins[i].componentId, pins[i].pinId, net.id);
    }
    (net.labels ?? []).forEach((label, labelIndex) => {
      const baseId = `net-label:${JSON.stringify([net.id, label])}`;
      let id = baseId;
      let suffix = 0;
      while (nodeIds.has(id)) id = `${baseId}:${++suffix}`;
      nodeIds.add(id);
      const ground = /^(GND|GROUND|0)$/i.test(label);
      const supply = /^(VCC|VDD|VEE|V\+|V-)$/i.test(label);
      const position = {
        x: supply || ground ? anchorX + labelIndex * STEP_X : maxX + STEP_X,
        y: supply ? 0 : ground ? maxY + STEP_Y : STEP_Y * (index + 1),
      };
      maxX = Math.max(maxX, position.x);
      maxY = Math.max(maxY, position.y);
      nodes.push({ id, type: 'unified', position,
        data: { reference: label, netLabel: true }, draggable: false });
      if (pins[0]) connect(id, 'net', pins[0].componentId, pins[0].pinId, net.id);
    });
  });
  return { nodes, edges, validation: compiled.validation };
}
