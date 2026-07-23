"use client";

/**
 * CircuitSchematic component.
 *
 * Renders a React Flow schematic from a SpiceCraft circuit JSON object.
 * Nodes are built from the electrical component model; handles are generated
 * dynamically from ComponentLibrary pin definitions via UnifiedCircuitNode.
 * Edges are derived from compiled electrical nets, guaranteeing every edge
 * connects a real source pin to a real target pin.
 *
 * The raw circuit JSON is compiled through CircuitBuilder so component types
 * are normalized, pins are resolved, and nets are validated before any visual
 * representation is produced.
 */

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

import { UnifiedCircuitNode } from './nodes/UnifiedCircuitNode';
import { CircuitBuilder } from '@/lib/circuit/engine/CircuitBuilder';
import { componentLibrary } from '@/lib/circuit/engine/ComponentLibrary';
import { Circuit, CircuitComponent, CircuitWire } from '@/lib/circuitService';
import { CompiledCircuit } from '@/lib/circuit/types';

// All component types use the same dynamic node renderer.
const nodeTypes = {
  unified: UnifiedCircuitNode,
};

interface CircuitSchematicProps {
  circuit: Circuit;
}

// ─── Node layout constants ────────────────────────────────────────────────────

const SPACING_X = 220;
const SPACING_Y = 180;
const ORIGIN_X = 80;
const ORIGIN_Y = 80;
const COLS = 4;

// ─── Type normalization ───────────────────────────────────────────────────────

/**
 * Determine the canonical component type that ComponentLibrary recognizes.
 * Mirrors the alias table in CircuitBuilder so rendering stays consistent.
 */
function resolveComponentType(rawType: string, rawValue?: string): string {
  const type = rawType.trim().toLowerCase();
  const value = (rawValue ?? '').trim().toLowerCase();

  // Value-based overrides first
  if (['bc547', '2n3904', '2n2222', 'npn', 's8050'].includes(value)) return 'npn_transistor';
  if (['bc557', '2n3906', 'pnp', 's8550'].includes(value)) return 'pnp_transistor';
  if (value === 'ne555' || value === '555') return 'ne555';

  const aliases: Record<string, string> = {
    resistor: 'resistor', res: 'resistor',
    capacitor: 'capacitor', cap: 'capacitor',
    inductor: 'inductor', ind: 'inductor',
    diode: 'diode',
    led: 'led',
    transistor: 'npn_transistor', npn: 'npn_transistor', bjt: 'npn_transistor',
    pnp: 'pnp_transistor',
    voltage: 'voltage_source', voltage_source: 'voltage_source',
    current: 'current_source', current_source: 'current_source',
    ground: 'ground', gnd: 'ground',
    ne555: 'ne555', '555': 'ne555', ic: 'ne555', timer: 'ne555',
  };

  return aliases[type] ?? type;
}

// ─── Edge validation ──────────────────────────────────────────────────────────

/**
 * Verify that a given handle ID exists on the component in ComponentLibrary.
 * If the handle is absent from the definition, we drop the edge endpoint so
 * React Flow never tries to connect to a non-existent handle.
 */
function resolveHandleId(
  componentType: string,
  rawHandleId: string | undefined,
): string | undefined {
  if (!rawHandleId) return undefined;
  const definition = componentLibrary.getDefinition(componentType);
  if (!definition) return undefined;
  const match = definition.pins.find((p) => p.id === rawHandleId);
  return match ? match.id : undefined;
}

// ─── Main builder ─────────────────────────────────────────────────────────────

export function buildCircuitFlow(circuit: Circuit): { nodes: Node[]; edges: Edge[] } {
  // ── Step 1: Compile through CircuitBuilder ──────────────────────────────
  // This normalizes component types, resolves pin coordinates, builds nets,
  // and stamps net names onto individual pins.
  let compiled: CompiledCircuit | null = null;
  try {
    compiled = CircuitBuilder.build(circuit as unknown);
  } catch {
    // Fallback: continue with raw circuit data if compiler fails
    compiled = null;
  }

  // ── Step 2: Build Node list ─────────────────────────────────────────────
  const rawComponents: CircuitComponent[] = circuit.components ?? [];
  const nodes: Node[] = [];
  const componentTypeById = new Map<string, string>();

  rawComponents.forEach((comp, index) => {
    const ref = (comp.reference as string) || (comp.id as string) || `C${index + 1}`;
    const rawType = (comp.type as string) ?? '';
    const rawValue = comp.value as string | undefined;
    const componentType = resolveComponentType(rawType, rawValue);

    componentTypeById.set(ref, componentType);

    // Use position from the compiled circuit if available (LayoutEngine applied),
    // otherwise fall back to a simple grid layout.
    let x: number;
    let y: number;

    if (compiled) {
      const compiledComp = compiled.components.find((c) => c.id === ref);
      if (compiledComp) {
        x = compiledComp.position.x;
        y = compiledComp.position.y;
      } else {
        x = ORIGIN_X + (index % COLS) * SPACING_X;
        y = ORIGIN_Y + Math.floor(index / COLS) * SPACING_Y;
      }
    } else {
      x = typeof comp.x === 'number' ? comp.x : ORIGIN_X + (index % COLS) * SPACING_X;
      y = typeof comp.y === 'number' ? comp.y : ORIGIN_Y + Math.floor(index / COLS) * SPACING_Y;
    }

    nodes.push({
      id: ref,
      type: 'unified',
      position: { x, y },
      data: {
        reference: ref,
        value: rawValue ?? '',
        type: rawType,
        componentType,
      },
    });
  });

  const validNodeIds = new Set(nodes.map((n) => n.id));

  // ── Step 3: Build Edge list ──────────────────────────────────────────────
  // Prefer building edges from compiled nets (clean pin references); fall back
  // to raw wires if compilation failed.
  const edges: Edge[] = [];
  const seen = new Set<string>();

  // Special net labels to suppress as node endpoints
  const SPECIAL_NODES = new Set(['VCC', 'GND', 'VDD', 'PWR', 'VIN', 'VOUT', 'IN', 'OUT', '0']);

  if (compiled && compiled.nets.length > 0) {
    // Build edges from compiled nets.
    // Each net has N pins; we create a chain: pins[0]→pins[1], pins[1]→pins[2], …
    compiled.nets.forEach((net) => {
      const componentPins = net.pins.filter(
        (p) => validNodeIds.has(p.componentId),
      );

      for (let i = 0; i < componentPins.length - 1; i++) {
        const src = componentPins[i];
        const tgt = componentPins[i + 1];

        const srcType = componentTypeById.get(src.componentId) ?? '';
        const tgtType = componentTypeById.get(tgt.componentId) ?? '';
        const srcHandle = resolveHandleId(srcType, src.pinId) ?? src.pinId;
        const tgtHandle = resolveHandleId(tgtType, tgt.pinId) ?? tgt.pinId;

        const edgeId = `${net.id}-${src.componentId}.${src.pinId}-${tgt.componentId}.${tgt.pinId}`;
        if (seen.has(edgeId)) continue;
        seen.add(edgeId);

        edges.push({
          id: edgeId,
          source: src.componentId,
          target: tgt.componentId,
          sourceHandle: srcHandle,
          targetHandle: tgtHandle,
          type: 'smoothstep',
          label: net.name,
          markerEnd: { type: MarkerType.ArrowClosed, color: '#7c3aed' },
          style: {
            stroke: '#7c3aed',
            strokeWidth: 2,
            filter: 'drop-shadow(0 0 6px rgba(124,58,237,0.25))',
            opacity: 0.95,
          },
        } as Edge);
      }
    });
  } else {
    // Fallback: build edges from raw wires
    (circuit.wires ?? []).forEach((wire: CircuitWire, i) => {
      const fromStr = (wire.from || wire.source) as string;
      const toStr = (wire.to || wire.destination) as string;
      if (!fromStr || !toStr) return;

      const [sourceBase, sourceHandle] = fromStr.includes('.')
        ? fromStr.split('.', 2)
        : [fromStr, undefined];
      const [targetBase, targetHandle] = toStr.includes('.')
        ? toStr.split('.', 2)
        : [toStr, undefined];

      // Skip edges that begin or end on power/ground labels (no corresponding node)
      if (SPECIAL_NODES.has(sourceBase.toUpperCase()) || SPECIAL_NODES.has(targetBase.toUpperCase())) {
        return;
      }

      if (!validNodeIds.has(sourceBase) || !validNodeIds.has(targetBase)) return;

      const wireId =
        typeof wire.id === 'string' && wire.id ? wire.id : `e-${i}-${sourceBase}-${targetBase}`;
      if (seen.has(wireId)) return;
      seen.add(wireId);

      const srcType = componentTypeById.get(sourceBase) ?? '';
      const tgtType = componentTypeById.get(targetBase) ?? '';

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
        const resolved = resolveHandleId(srcType, sourceHandle);
        if (resolved) edge.sourceHandle = resolved;
      }

      if (targetHandle) {
        const resolved = resolveHandleId(tgtType, targetHandle);
        if (resolved) edge.targetHandle = resolved;
      }

      edges.push(edge);
    });
  }

  return { nodes, edges };
}

// ─── React component ──────────────────────────────────────────────────────────

export function CircuitSchematic({ circuit }: CircuitSchematicProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const reactFlowRef = useRef<unknown>(null);

  useEffect(() => {
    const { nodes: finalNodes, edges: finalEdges } = buildCircuitFlow(circuit);
    setNodes(finalNodes);
    setEdges(finalEdges);
    setTimeout(() => {
      if (reactFlowRef.current && typeof (reactFlowRef.current as { fitView?: () => void }).fitView === 'function') {
        (reactFlowRef.current as { fitView: () => void }).fitView();
      }
    }, 50);
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
        <MiniMap
          nodeStrokeColor={() => '#7c3aed'}
          nodeColor={() => '#0f172a'}
          maskColor="rgba(15,23,42,0.6)"
        />
        <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
      </ReactFlow>
    </div>
  );
}
