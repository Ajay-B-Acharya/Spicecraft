'use client';

/**
 * Unified Circuit Node for React Flow.
 *
 * This component renders any circuit component as a React Flow node. Handles
 * are generated dynamically from the component's pin definitions stored in the
 * ComponentLibrary, so adding a new component type automatically produces
 * correct handles without writing a new node file.
 *
 * Pin direction → React Flow Handle position mapping:
 *   left   → Position.Left   (type: target)
 *   right  → Position.Right  (type: source)
 *   top    → Position.Top    (type: target)
 *   bottom → Position.Bottom (type: source)
 */
import React from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { componentLibrary } from '@/lib/circuit/engine/ComponentLibrary';
import { Pin } from '@/lib/circuit/models/Pin';

type PinDirection = NonNullable<Pin['direction']>;

// Determines which React Flow Position to use for a given pin direction.
function directionToPosition(direction: PinDirection | undefined): Position {
  switch (direction) {
    case 'top':
      return Position.Top;
    case 'bottom':
      return Position.Bottom;
    case 'right':
      return Position.Right;
    case 'left':
    default:
      return Position.Left;
  }
}

// Determines handle type: inputs (left/top) are targets; outputs (right/bottom) are sources.
function directionToHandleType(direction: PinDirection | undefined): 'source' | 'target' {
  if (direction === 'right' || direction === 'bottom') {
    return 'source';
  }
  return 'target';
}

const PIN_HANDLE_STYLE =
  'w-3 h-3 rounded-full bg-purple-500 border-2 border-slate-900 hover:bg-purple-400 transition-colors';

// Percentage offset along the node edge so handles are spread evenly.
function computeHandleStyle(
  direction: PinDirection | undefined,
  pinIndex: number,
  totalPinsOnEdge: number,
): React.CSSProperties {
  if (totalPinsOnEdge <= 1) {
    return {};
  }

  const pct = ((pinIndex + 1) / (totalPinsOnEdge + 1)) * 100;

  if (direction === 'left' || direction === 'right') {
    return { top: `${pct}%` };
  }

  return { left: `${pct}%` };
}

interface UnifiedCircuitNodeData {
  reference?: string;
  value?: string;
  type?: string;
  componentType?: string; // Canonical type key matching ComponentLibrary
  [key: string]: unknown;
}

interface UnifiedCircuitNodeProps extends NodeProps {
  data: UnifiedCircuitNodeData;
  selected?: boolean;
}

export function UnifiedCircuitNode({ data, selected }: UnifiedCircuitNodeProps) {
  const reference = data.reference ?? String(data.id ?? '');
  const value = data.value ?? '';
  const rawType = data.type ?? '';
  const componentType = data.componentType ?? rawType;

  // Retrieve pin definitions from ComponentLibrary.
  const definition = componentLibrary.getDefinition(componentType);
  const pins = definition?.pins ?? [];

  // Count how many pins sit on each edge for even spacing.
  const pinsPerEdge = new Map<string, number>();
  const pinEdgeIndex = new Map<string, number>();

  pins.forEach((pin) => {
    const dir = pin.direction ?? 'left';
    const count = pinsPerEdge.get(dir) ?? 0;
    pinEdgeIndex.set(pin.id, count);
    pinsPerEdge.set(dir, count + 1);
  });

  const border = selected
    ? 'ring-2 ring-purple-500 border-purple-400'
    : 'border border-indigo-600/20';

  return (
    <div
      style={{ minWidth: 120, minHeight: 64 }}
      className={`relative flex flex-col items-center justify-center rounded-lg shadow-sm bg-slate-900 p-2 ${border}`}
    >
      {/* Dynamic handles generated from pin definitions */}
      {pins.map((pin) => {
        const dir = pin.direction ?? 'left';
        const edgeTotal = pinsPerEdge.get(dir) ?? 1;
        const edgeIndex = pinEdgeIndex.get(pin.id) ?? 0;
        const handleType = directionToHandleType(dir);
        const position = directionToPosition(dir);
        const style = computeHandleStyle(dir, edgeIndex, edgeTotal);

        return (
          <Handle
            key={pin.id}
            id={pin.id}
            type={handleType}
            position={position}
            style={style}
            className={PIN_HANDLE_STYLE}
            title={pin.name}
          />
        );
      })}

      {/* Component label */}
      <div className="text-sm font-semibold text-white leading-tight">{reference}</div>
      {value && <div className="text-[11px] text-slate-300 leading-tight">{value}</div>}
      {rawType && <div className="text-[10px] text-slate-400/80 leading-tight">{rawType}</div>}

      {/* Fallback: no definition found */}
      {!definition && (
        <div className="text-[9px] text-red-400 mt-1">unknown type</div>
      )}
    </div>
  );
}

export default UnifiedCircuitNode;
