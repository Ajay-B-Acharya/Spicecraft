import { Handle, Position, NodeProps } from '@xyflow/react';

export function ResistorNode({ data }: NodeProps) {
  const base = 'flex flex-col items-center justify-center rounded-lg shadow-sm relative p-2';
  const sizeStyle = { width: 140, height: 80 } as React.CSSProperties;
  return (
    <div style={sizeStyle} className={`${base} bg-slate-900 border border-indigo-600/20`}>
      <Handle type="target" position={Position.Left} id="1" className="w-3 h-3 rounded-full bg-purple-500 border-2 border-slate-900" />
      <div className="w-20 h-4 border-2 border-slate-700 bg-slate-800 flex items-center justify-center text-[10px] font-mono text-slate-200 shadow-inner">
        {data.value as string}
      </div>
      <div className="text-sm font-semibold text-white mt-1">{data.reference as string}</div>
      <Handle type="source" position={Position.Right} id="2" className="w-3 h-3 rounded-full bg-purple-500 border-2 border-slate-900" />
    </div>
  );
}
