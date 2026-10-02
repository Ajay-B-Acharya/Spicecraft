'use client';

/**
 * Unified Circuit Node for React Flow.
 *
 * This component renders any circuit component as a React Flow node. Handles
 * are generated dynamically from the component's pin definitions stored in the
 * ComponentLibrary, so adding a new component type automatically produces
 * correct handles without writing a new node file.
 *
 * Pin directions control geometry only, never electrical signal direction.
 * All handles work at either end of a wire through React Flow's Loose mode.
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

}

export function UnifiedCircuitNode({ data, selected }: UnifiedCircuitNodeProps) {
  const reference = data.reference ?? String(data.id ?? '');
  const value = data.value ?? '';
  const rawType = data.type ?? '';
  const componentType = data.componentType ?? rawType;

  // Retrieve pin definitions from ComponentLibrary.
  const definition = componentLibrary.getDefinition(componentType);
  const pins: Pin[] = data.netLabel
      ? [{ id: 'net', name: String(reference), x: 0, y: 0, direction: 'bottom' }]
      : definition?.pins ?? [];

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
        // Electrical pins are bidirectional; Loose connection mode accepts either endpoint.
                const handleType = 'source' as const;
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
            title={`${reference}.${pin.id} (${pin.name})`}
          />
        );
      })}

      <div className="text-[10px] text-purple-300 mb-1">
        {pins.map(pin => `${pin.id}: ${pin.name}`).join(' · ')}
      </div>
      {componentType === 'resistor' && (
        <svg width="88" height="24" viewBox="0 0 88 24" aria-label="Resistor" className="text-slate-300">
          <path d="M0 12 H18 L23 4 L31 20 L39 4 L47 20 L55 4 L63 20 L68 12 H88" fill="none" stroke="currentColor" strokeWidth="2" />
        </svg>
      )}
      {componentType === 'capacitor' && (
        <svg width="88" height="24" viewBox="0 0 88 24" aria-label="Capacitor" className="text-slate-300">
          <path d="M0 12 H38 M38 2 V22 M50 2 V22 M50 12 H88" fill="none" stroke="currentColor" strokeWidth="2" />
        </svg>
      )}
      {/^(npn|pnp)_transistor$/.test(componentType) && (
        <svg width="64" height="48" viewBox="0 0 64 48" aria-label="Bipolar transistor" className="text-slate-300">
          <path d="M0 24 H24 M24 12 V36 M24 18 L40 8 V0 M24 30 L40 40 V48" fill="none" stroke="currentColor" strokeWidth="2" />
          <path d={componentType === 'npn_transistor' ? 'M40 40 L31 37 L36 31 Z' : 'M26 31 L35 33 L30 39 Z'} fill="currentColor" />
        </svg>
      )}
      {/* Component label */}
      <div className="text-sm font-semibold text-white leading-tight">{reference}</div>
      {value && <div className="text-[11px] text-slate-300 leading-tight">{value}</div>}
      {rawType && <div className="text-[10px] text-slate-400/80 leading-tight">{rawType}</div>}

      {/* Fallback: no definition found */}
      {!definition && !data.netLabel && (
        <div className="text-[9px] text-red-400 mt-1">unknown type</div>
      )}
    </div>
  );
}

export default UnifiedCircuitNode;
