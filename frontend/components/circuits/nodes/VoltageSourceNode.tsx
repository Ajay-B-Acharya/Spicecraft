import { Handle, Position, NodeProps } from '@xyflow/react';

export function VoltageSourceNode({ data }: NodeProps) {
  return (
    <div className="flex flex-col items-center justify-center bg-transparent w-16 py-2 relative">
      <Handle type="target" position={Position.Top} id="+" className="w-2 h-2 !bg-blue-500" />
      <div className="flex items-center justify-center w-10 h-10 border-2 border-gray-600 rounded-full my-1 relative">
        <span className="absolute top-1 text-[10px]">+</span>
        <span className="absolute bottom-1 text-[10px]">-</span>
      </div>
      <div className="text-xs font-bold">{data.reference as string}</div>
      <div className="text-[10px] text-gray-500">{data.value as string}</div>
      <Handle type="source" position={Position.Bottom} id="-" className="w-2 h-2 !bg-blue-500" />
    </div>
  );
}
