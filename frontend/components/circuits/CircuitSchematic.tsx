'use client';

/** Displays the canonical electrical graph; visual movement never creates connectivity. */
import { useEffect } from 'react';
import {
  ReactFlow, MiniMap, Controls, Background, BackgroundVariant, ConnectionMode,
  type Node, type Edge, type Connection, useNodesState, useEdgesState,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { UnifiedCircuitNode } from './nodes/UnifiedCircuitNode';
import { buildCircuitFlow } from './circuitFlowAdapter';
import type { Circuit } from '@/lib/circuitService';

export { buildCircuitFlow } from './circuitFlowAdapter';
const nodeTypes = { unified: UnifiedCircuitNode };

interface CircuitSchematicProps {
  circuit: Circuit;
  onConnectPins?: (source: string, sourcePin: string, target: string, targetPin: string) => void;
  onPositionChange?: (id: string, position: { x: number; y: number }) => void;
}

/** Renders pin handles and persists explicit connections through the editor draft. */
export function CircuitSchematic({ circuit, onConnectPins, onPositionChange }: CircuitSchematicProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  useEffect(() => {
    const flow = buildCircuitFlow(circuit);
    setNodes(flow.nodes);
    setEdges(flow.edges);
  }, [circuit, setNodes, setEdges]);

  const isValidConnection = (connection: Connection | Edge) => Boolean(
    connection.sourceHandle && connection.targetHandle &&
    !(connection.source === connection.target && connection.sourceHandle === connection.targetHandle) &&
    !nodes.find(node => node.id === connection.source)?.data.netLabel &&
    !nodes.find(node => node.id === connection.target)?.data.netLabel,
  );

  return (
    <div className="relative h-[600px] w-full overflow-hidden rounded-md border border-border bg-slate-900/60">
      <ReactFlow
        nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes} fitView nodesDraggable nodesConnectable={Boolean(onConnectPins)}
        connectionMode={ConnectionMode.Loose} isValidConnection={isValidConnection}
        onConnect={connection => {
          if (connection.sourceHandle && connection.targetHandle && isValidConnection(connection)) {
            onConnectPins?.(connection.source, connection.sourceHandle, connection.target, connection.targetHandle);
          }
        }}
        onNodeDragStop={(_, node) => {
          if (!node.data.netLabel) onPositionChange?.(node.id, node.position);
        }}
        deleteKeyCode={null} elementsSelectable attributionPosition="bottom-right" proOptions={{ hideAttribution: true }}
      >
        <Controls />
        <MiniMap nodeStrokeColor={() => '#7c3aed'} nodeColor={() => '#0f172a'} maskColor="rgba(15,23,42,0.6)" />
        <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
      </ReactFlow>
    </div>
  );
}
