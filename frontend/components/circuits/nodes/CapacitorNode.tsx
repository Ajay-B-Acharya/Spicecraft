import { Handle, Position, NodeProps } from '@xyflow/react';

export function CapacitorNode({ data }: NodeProps) {
  return (
    <div className="flex flex-col items-center justify-center bg-transparent w-16 py-2 relative">
      <Handle type="target" position={Position.Top} id="1" className="w-2 h-2 !bg-blue-500" />
      <div className="flex flex-col items-center justify-center h-8 my-1 relative">
        <div className="w-8 border-b-2 border-gray-600 mb-1"></div>
        <div className="w-8 border-t-2 border-gray-600 mt-1"></div>
      </div>
      <div className="text-xs font-bold">{data.reference as string}</div>
      <div className="text-[10px] text-gray-500">{data.value as string}</div>
      <Handle type="source" position={Position.Bottom} id="2" className="w-2 h-2 !bg-blue-500" />
    </div>
  );
}
