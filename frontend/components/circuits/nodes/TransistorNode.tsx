import { Handle, Position, NodeProps } from '@xyflow/react';

export function TransistorNode({ data }: NodeProps) {
  const base = 'flex flex-col items-center justify-center rounded-lg shadow-sm relative p-2';
  const sizeStyle = { width: 160, height: 90 } as React.CSSProperties;
  return (
    <div style={sizeStyle} className={`${base} bg-slate-900 border border-indigo-600/20`}>
      {/* Base on left */}
      <Handle type="target" position={Position.Left} id="B" className="w-3 h-3 rounded-full bg-purple-500 border-2 border-slate-900" />
      {/* Collector on top */}
      <Handle type="target" position={Position.Top} id="C" className="w-3 h-3 rounded-full bg-purple-500 border-2 border-slate-900" />
      <div className="flex flex-col items-center justify-center">
        <div className="text-sm font-semibold text-white">{data.reference as string}</div>
        <div className="text-[11px] text-slate-300">{data.value as string}</div>
        <div className="text-[11px] text-slate-400/90">{data.type as string}</div>
      </div>
      {/* Emitter on right */}
      <Handle type="source" position={Position.Right} id="E" className="w-3 h-3 rounded-full bg-purple-500 border-2 border-slate-900" />
    </div>
  );
}

export default TransistorNode;
