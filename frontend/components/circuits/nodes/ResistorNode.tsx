import { Handle, Position, NodeProps } from '@xyflow/react';

export function ResistorNode({ data }: NodeProps) {
  return (
    <div className="flex flex-col items-center justify-center border-2 border-gray-500 bg-white w-20 py-2 rounded shadow-sm relative">
      <Handle type="target" position={Position.Left} id="1" className="w-2 h-2 !bg-blue-500" />
      <div className="w-10 h-3 border-2 border-gray-500 bg-gray-100 flex items-center justify-center text-[8px] font-mono shadow-inner">
        {data.value as string}
      </div>
      <div className="text-xs font-bold mt-1">{data.reference as string}</div>
      <Handle type="source" position={Position.Right} id="2" className="w-2 h-2 !bg-blue-500" />
    </div>
  );
}
