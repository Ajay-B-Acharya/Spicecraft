import { Handle, Position, NodeProps } from '@xyflow/react';

export function CapacitorNode({ data }: NodeProps) {
  const base = 'flex flex-col items-center justify-center rounded-lg shadow-sm relative p-2';
  const sizeStyle = { width: 140, height: 80 } as React.CSSProperties;
  return (
    <div style={sizeStyle} className={`${base} bg-slate-900 border border-indigo-600/20`}>
      <Handle type="target" position={Position.Left} id="1" className="w-3 h-3 rounded-full bg-purple-500 border-2 border-slate-900" />
      <div className="flex flex-col items-center justify-center h-12 my-1 relative">
        <div className="w-12 border-b-2 border-slate-600 mb-1"></div>
        <div className="w-12 border-t-2 border-slate-600 mt-1"></div>
      </div>
      <div className="text-sm font-semibold text-white">{data.reference as string}</div>
      <div className="text-[11px] text-slate-300">{data.value as string}</div>
      <Handle type="source" position={Position.Right} id="2" className="w-3 h-3 rounded-full bg-purple-500 border-2 border-slate-900" />
    </div>
  );
}
