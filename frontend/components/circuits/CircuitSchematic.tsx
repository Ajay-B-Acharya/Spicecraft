"use client";

import { useMemo, useEffect } from 'react';
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

import { ResistorNode } from './nodes/ResistorNode';
import { CapacitorNode } from './nodes/CapacitorNode';
import { VoltageSourceNode } from './nodes/VoltageSourceNode';
import { GroundNode } from './nodes/GroundNode';
import { GenericNode } from './nodes/GenericNode';
import { Circuit, CircuitComponent, CircuitWire } from '@/lib/circuitService';

const nodeTypes = {
  resistor: ResistorNode,
  capacitor: CapacitorNode,
  'voltage-source': VoltageSourceNode,
  ground: GroundNode,
  generic: GenericNode,
};

interface CircuitSchematicProps {
  circuit: Circuit;
}

export function CircuitSchematic({ circuit }: CircuitSchematicProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  // Translate CircuitComponents and generic wire endpoints into ReactFlow nodes
  useEffect(() => {
    const flowNodes: Node[] = [];
    // Explicit components -> every component becomes a node
    const componentRefs = new Set<string>();

    circuit.components?.forEach((comp, index) => {
      const ref = (comp.reference as string) || (comp.id as string) || `c${index}`;
      componentRefs.add(ref);

      // If coordinates are missing, generate them: x = index * 200, y = 150
      const x = (typeof comp.x === 'number') ? comp.x : index * 200;
      const y = (typeof comp.y === 'number') ? comp.y : 150;

      const typeStr = (comp.type as string)?.toLowerCase();
      let nodeType = 'generic';

      if (typeStr === 'resistor') nodeType = 'resistor';
      else if (typeStr === 'capacitor') nodeType = 'capacitor';
      else if (typeStr === 'voltage_source' || typeStr === 'vdc' || typeStr === 'voltage source') nodeType = 'voltage-source';
      else if (typeStr === 'ground' || typeStr === 'gnd') nodeType = 'ground';

      flowNodes.push({
        id: ref,
        type: nodeType,
        position: { x, y },
        data: {
          ...comp,
          reference: ref,
          value: typeof comp.value === 'string' ? comp.value : '',
        },
      });
    });

    console.log('Loaded circuit', { id: circuit.id, name: circuit.name });
    console.log('Generated nodes', flowNodes.map(n => ({ id: n.id, position: n.position, type: n.type })));

    setNodes(flowNodes);
  }, [circuit, setNodes]);

  // Translate CircuitWires into ReactFlow edges
  useEffect(() => {
    const flowEdges: Edge[] = [];

    // Build set of valid component ids (references)
    const validComponents = new Set<string>();
    circuit.components?.forEach((c, i) => {
      const ref = (c.reference as string) || (c.id as string) || `c${i}`;
      validComponents.add(ref);
    });

    circuit.wires?.forEach((wire, i) => {
      const fromStr = (wire.from || wire.source) as string;
      const toStr = (wire.to || wire.destination) as string;
      if (!fromStr || !toStr) return;

      // Extract base component id before '.' if present (R1.1 -> R1)
      const sourceBase = fromStr.includes('.') ? fromStr.split('.')[0] : fromStr;
      const targetBase = toStr.includes('.') ? toStr.split('.')[0] : toStr;

      // Ignore endpoints that are not components
      if (!validComponents.has(sourceBase) || !validComponents.has(targetBase)) {
        return;
      }

      const sourceHandle = fromStr.includes('.') ? fromStr.split('.')[1] : null;
      const targetHandle = toStr.includes('.') ? toStr.split('.')[1] : null;

      const wireId = typeof wire.id === 'string' && wire.id ? wire.id : `e-${i}-${sourceBase}-${targetBase}`;

      flowEdges.push({
        id: wireId,
        source: sourceBase,
        target: targetBase,
        sourceHandle: sourceHandle || null,
        targetHandle: targetHandle || null,
        type: 'smoothstep',
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: '#6b7280'
        },
        style: { stroke: '#6b7280', strokeWidth: 2 }
      });
    });

    console.log('Generated edges', flowEdges.map(e => ({ id: e.id, source: e.source, target: e.target })));

    setEdges(flowEdges);
  }, [circuit, setEdges]);

  return (
    <div className="w-full h-full min-h-[500px] border border-border rounded-md bg-muted/20 overflow-hidden">
      {/* Debug badge */}
      <div className="absolute right-4 top-4 z-20 bg-white/90 rounded-md border px-3 py-1 text-xs shadow">
        <div className="font-medium">Debug</div>
        <div className="flex gap-2 mt-1">
          <div>Components: {circuit.components?.length ?? 0}</div>
          <div>Nodes: {nodes.length}</div>
        </div>
        <div className="flex gap-2">
          <div>Wires: {circuit.wires?.length ?? 0}</div>
          <div>Edges: {edges.length}</div>
        </div>
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        nodesDraggable={false} // View-only for now, but architecture supports true easily
        nodesConnectable={false}
        elementsSelectable={true}
        attributionPosition="bottom-right"
        proOptions={{ hideAttribution: true }}
      >
        <Controls />
        <MiniMap />
        <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
      </ReactFlow>
    </div>
  );
}
