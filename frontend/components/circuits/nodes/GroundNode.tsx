import { Handle, Position, NodeProps } from '@xyflow/react';

export function GroundNode({ data }: NodeProps) {
  return (
    <div className="flex flex-col items-center justify-center bg-transparent w-16 py-1 relative">
      <Handle type="target" position={Position.Top} id="1" className="w-2 h-2 !bg-blue-500" />
      <div className="w-px h-4 bg-gray-600 mb-0"></div>
      <div className="w-6 border-b-2 border-gray-600 mb-[2px]"></div>
      <div className="w-4 border-b-2 border-gray-600 mb-[2px]"></div>
      <div className="w-2 border-b-2 border-gray-600"></div>
    </div>
  );
}
