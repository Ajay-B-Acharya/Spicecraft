import { NodeProps } from '@xyflow/react';

export function CircuitNode({ data, selected }: NodeProps) {
  const reference = (data && (data.reference as string)) || String(data?.id ?? '');
  const value = (data && (data.value as string)) || '';
  const type = (data && (data.type as string)) || '';

  const base = 'flex flex-col items-center justify-center rounded-lg shadow-sm transition-all';
  const sizeStyle = { width: 140, height: 80 } as React.CSSProperties;

  const bg = 'bg-slate-900';
  const border = selected ? 'ring-2 ring-purple-500 border-purple-400' : 'border border-indigo-600/20';
  const hover = 'hover:shadow-lg hover:ring-1 hover:ring-indigo-500/20';

  return (
    <div style={sizeStyle} className={`${base} ${bg} ${border} ${hover} p-2`}>
      <div className="text-white font-semibold">{reference}</div>
      <div className="text-sm text-slate-300">{value}</div>
      <div className="text-[11px] text-slate-400/90">{type}</div>
    </div>
  );
}
