"use client";

import { useEffect, useRef } from 'react';
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  BackgroundVariant,
  Node,
  Edge,
  MarkerType,
  useNodesState,
  useEdgesState,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { CircuitNode } from './nodes/CircuitNode';
import { ResistorNode } from './nodes/ResistorNode';
import { CapacitorNode } from './nodes/CapacitorNode';
import TransistorNode from './nodes/TransistorNode';
import { Circuit, CircuitComponent, CircuitWire } from '@/lib/circuitService';

const nodeTypes = {
  circuit: CircuitNode,
  resistor: ResistorNode,
  capacitor: CapacitorNode,
  transistor: TransistorNode,
};

interface CircuitSchematicProps {
  circuit: Circuit;
}

type FlowStats = {
  components: number;
  nodes: number;
  wires: number;
  edges: number;
};

export function buildCircuitFlow(circuit: Circuit) {
  const nodes: Node[] = [];

  circuit.components?.forEach((comp, index) => {
    const ref = (comp.reference as string) || (comp.id as string) || `c${index}`;
    const x = typeof comp.x === 'number' ? comp.x : index * 200;
    const y = typeof comp.y === 'number' ? comp.y : 150;

    nodes.push({
      id: ref,
      position: { x, y },
      data: { label: ref },
    });
  });

  const resistors: Array<{ comp: CircuitComponent; i: number }> = [];
  const transistors: Array<{ comp: CircuitComponent; i: number }> = [];
  const capacitors: Array<{ comp: CircuitComponent; i: number }> = [];
  const others: Array<{ comp: CircuitComponent; i: number }> = [];

  (circuit.components ?? []).forEach((comp, i) => {
    const typeStr = ((comp.type as string) || '').toLowerCase();
    if (typeStr.includes('resistor')) resistors.push({ comp, i });
    else if (typeStr.includes('transistor') || typeStr.includes('ic')) transistors.push({ comp, i });
    else if (typeStr.includes('capacitor')) capacitors.push({ comp, i });
    else others.push({ comp, i });
  });

  const spacingX = 180;
  const centerX = 400;
  const topY = 100;
  const midY = 200;
  const bottomY = 320;

  const buildRow = (items: Array<{ comp: CircuitComponent; i: number }>, y: number) => {
    const count = items.length;
    const totalWidth = (count - 1) * spacingX;
    const startX = centerX - totalWidth / 2;

    return items.map((it, idx) => {
      const ref = (it.comp.reference as string) || (it.comp.id as string) || `c${it.i}`;
      const x = startX + idx * spacingX;
      const typeStr = ((it.comp.type as string) || '').toLowerCase();
      let nodeType: 'circuit' | 'resistor' | 'capacitor' | 'transistor' = 'circuit';

      if (typeStr.includes('resistor')) nodeType = 'resistor';
      else if (typeStr.includes('capacitor')) nodeType = 'capacitor';
      else if (typeStr.includes('transistor') || typeStr.includes('ic')) nodeType = 'transistor';

      return {
        id: ref,
        position: { x, y },
        data: { reference: ref, value: it.comp.value ?? '', type: it.comp.type ?? '' },
        type: nodeType,
      } as Node;
    });
  };

  const nodesTop = buildRow([...resistors, ...others], topY);
  const nodesMid = buildRow(transistors, midY);
  const nodesBottom = buildRow(capacitors, bottomY);
  const finalNodes = [...nodesTop, ...nodesMid, ...nodesBottom];

  const validComponents = new Set(finalNodes.map((node) => node.id));
  const ignoreList = new Set(['VCC', 'GND', 'OUT', 'VIN']);
  const seen = new Set<string>();
  const flowEdges: Edge[] = [];

  (circuit.wires ?? []).forEach((wire: CircuitWire, i) => {
    const fromStr = (wire.from || wire.source) as string;
    const toStr = (wire.to || wire.destination) as string;
    if (!fromStr || !toStr) return;

    const sourceParts = fromStr.includes('.') ? fromStr.split('.') : [fromStr];
    const targetParts = toStr.includes('.') ? toStr.split('.') : [toStr];
    const sourceBase = sourceParts[0];
    const targetBase = targetParts[0];
    const sourceHandle = sourceParts[1];
    const targetHandle = targetParts[1];

    if (ignoreList.has(sourceBase.toUpperCase()) || ignoreList.has(targetBase.toUpperCase())) {
      return;
    }

    if (!validComponents.has(sourceBase) || !validComponents.has(targetBase)) {
      return;
    }

    const wireId = typeof wire.id === 'string' && wire.id ? wire.id : `e-${i}-${sourceBase}-${targetBase}`;
    if (seen.has(wireId)) return;
    seen.add(wireId);

    const nodeTypeToAllowedHandles: Record<string, string[]> = {
      resistor: ['1', '2'],
      capacitor: ['1', '2'],
      transistor: ['B', 'C', 'E'],
      circuit: [],
    };

    const getNodeType = (id: string) => finalNodes.find((node) => node.id === id)?.type as string | undefined;
    const srcType = getNodeType(sourceBase) ?? 'circuit';
    const tgtType = getNodeType(targetBase) ?? 'circuit';

    const edge: Edge = {
      id: wireId,
      source: sourceBase,
      target: targetBase,
      type: 'smoothstep',
      markerEnd: { type: MarkerType.ArrowClosed, color: '#7c3aed' },
      style: {
        stroke: '#7c3aed',
        strokeWidth: 2,
        filter: 'drop-shadow(0 0 6px rgba(124,58,237,0.25))',
        opacity: 0.95,
      },
    } as Edge;

    if (sourceHandle) {
      const allowed = nodeTypeToAllowedHandles[srcType] ?? [];
      if (allowed.length === 0 || allowed.includes(sourceHandle)) {
        edge.sourceHandle = sourceHandle;
      }
    }

    if (targetHandle) {
      const allowed = nodeTypeToAllowedHandles[tgtType] ?? [];
      if (allowed.length === 0 || allowed.includes(targetHandle)) {
        edge.targetHandle = targetHandle;
      }
    }

    flowEdges.push(edge);
  });

  return { nodes: finalNodes, edges: flowEdges };
}

export function CircuitSchematic({ circuit }: CircuitSchematicProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  const reactFlowRef = useRef<any>(null);

  useEffect(() => {
    const { nodes: finalNodes, edges: finalEdges } = buildCircuitFlow(circuit);
    setNodes(finalNodes);
    setEdges(finalEdges);
    setTimeout(() => reactFlowRef.current?.fitView?.(), 50);
  }, [circuit, setNodes, setEdges]);

  return (
    <div className="relative h-[600px] w-full overflow-hidden rounded-md border border-border bg-slate-900/60">
      <ReactFlow
        ref={reactFlowRef}
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        nodesDraggable={true}
        nodesConnectable={false}
        elementsSelectable={true}
        attributionPosition="bottom-right"
        proOptions={{ hideAttribution: true }}
      >
        <Controls className="rounded-md bg-slate-800/60 shadow-md" />
        <MiniMap nodeStrokeColor={() => '#7c3aed'} nodeColor={() => '#0f172a'} maskColor={'rgba(15,23,42,0.6)'} />
        <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
      </ReactFlow>
    </div>
  );
}
