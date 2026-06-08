"use client";

import { useMemo, useEffect, useRef } from 'react';
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

export function CircuitSchematic({ circuit }: CircuitSchematicProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  const reactFlowRef = useRef<any>(null);
  // Translate CircuitComponents and generic wire endpoints into ReactFlow nodes
  useEffect(() => {
    const flowNodes: Node[] = [];
    // Explicit components -> every component becomes a default React Flow node
    const componentRefs = new Set<string>();

    circuit.components?.forEach((comp, index) => {
      const ref = (comp.reference as string) || (comp.id as string) || `c${index}`;
      componentRefs.add(ref);

      // If coordinates are missing, generate them: x = index * 200, y = 150
      const x = (typeof comp.x === 'number') ? comp.x : index * 200;
      const y = (typeof comp.y === 'number') ? comp.y : 150;

      // Use default node (no custom nodeTypes) and minimal data for debugging
      flowNodes.push({
        id: ref,
        position: { x, y },
        data: { label: ref },
      });
    });

    console.log('Loaded circuit', { id: circuit.id, name: circuit.name });
    console.log('Component count', circuit.components?.length ?? 0);
    console.log('Generated node count', flowNodes.length);

    // Layout groups: resistors top, transistors center, capacitors bottom, others top
    const resistors = [] as any[];
    const transistors = [] as any[];
    const capacitors = [] as any[];
    const others = [] as any[];

    (circuit.components ?? []).forEach((comp, i) => {
      const typeStr = (comp.type as string || '').toLowerCase();
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

    const buildRow = (items: any[], y: number) => {
      const count = items.length;
      const totalWidth = (count - 1) * spacingX;
      const startX = centerX - totalWidth / 2;
      return items.map((it, idx) => {
        const ref = (it.comp.reference as string) || (it.comp.id as string) || `c${it.i}`;
        const x = startX + idx * spacingX;
        const typeStr = (it.comp.type as string || '').toLowerCase();
        let nodeType = 'circuit';
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

    // Add a temporary obvious debug node to verify selection behavior
    const debugNode: Node = { id: 'debug', position: { x: 300, y: 300 }, data: { label: 'DEBUG NODE' } } as Node;

    const nodesWithDebug = [...finalNodes, debugNode];
    setNodes(nodesWithDebug);
    setEdges([]);

    // fit view after nodes are set
    setTimeout(() => reactFlowRef.current?.fitView?.(), 50);
  }, [circuit, setNodes]);

  // Translate CircuitWires into ReactFlow edges
  useEffect(() => {
    // Generate edges between valid component nodes only
    const flowEdges: Edge[] = [];
    const validComponents = new Set(nodes.map(n => n.id));

    console.log('Attempting to generate edges. Valid components:', Array.from(validComponents));

    const ignoreList = new Set(['VCC', 'GND', 'OUT', 'VIN']);
    const seen = new Set<string>();

    circuit.wires?.forEach((wire, i) => {
      const fromStr = (wire.from || wire.source) as string;
      const toStr = (wire.to || wire.destination) as string;
      if (!fromStr || !toStr) return;

      const sourceParts = fromStr.includes('.') ? fromStr.split('.') : [fromStr];
      const targetParts = toStr.includes('.') ? toStr.split('.') : [toStr];
      const sourceBase = sourceParts[0];
      const targetBase = targetParts[0];
      const sourceHandle = sourceParts[1];
      const targetHandle = targetParts[1];

      // Ignore special nets
      if (ignoreList.has(sourceBase.toUpperCase()) || ignoreList.has(targetBase.toUpperCase())) {
        console.log('Ignoring special endpoint in wire', { from: sourceBase, to: targetBase });
        return;
      }

      // Both must be valid component nodes
      if (!validComponents.has(sourceBase) || !validComponents.has(targetBase)) {
        console.warn('Skipping edge because endpoint is not a component node', { wire, sourceBase, targetBase });
        return;
      }

      const wireId = typeof wire.id === 'string' && wire.id ? wire.id : `e-${i}-${sourceBase}-${targetBase}`;
      if (seen.has(wireId)) return; // dedupe
      seen.add(wireId);

      // Validate handles exist for the given node types
      const getNodeType = (id: string) => nodes.find(n => n.id === id)?.type as string | undefined;
      const nodeTypeToAllowedHandles: Record<string, string[]> = {
        resistor: ['1', '2'],
        capacitor: ['1', '2'],
        transistor: ['B', 'C', 'E'],
        circuit: [],
      };

      const srcType = getNodeType(sourceBase) ?? 'circuit';
      const tgtType = getNodeType(targetBase) ?? 'circuit';

      let edge: Edge = {
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
        if (allowed.length === 0 || allowed.includes(sourceHandle)) edge.sourceHandle = sourceHandle;
        else {
          console.warn('Source handle not allowed for node type, skipping handle binding', { wire, sourceBase, sourceHandle, srcType });
        }
      }

      if (targetHandle) {
        const allowed = nodeTypeToAllowedHandles[tgtType] ?? [];
        if (allowed.length === 0 || allowed.includes(targetHandle)) edge.targetHandle = targetHandle;
        else {
          console.warn('Target handle not allowed for node type, skipping handle binding', { wire, targetBase, targetHandle, tgtType });
        }
      }

      flowEdges.push(edge);
    });

    console.log('Generated edges after validation', flowEdges.map((e: Edge) => ({ id: e.id, source: e.source, target: e.target })));

    setEdges(flowEdges);
  }, [circuit, nodes, setEdges]);

  return (
    <div className="w-full h-[600px] border border-border rounded-md bg-slate-900/60 overflow-hidden relative">
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
        <Controls className="bg-slate-800/60 rounded-md shadow-md" />
        <MiniMap nodeStrokeColor={(n) => '#7c3aed'} nodeColor={(n) => '#0f172a'} maskColor={'rgba(15,23,42,0.6)'} />
        <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
      </ReactFlow>
    </div>
  );
}
