import { Handle, Position, NodeProps } from '@xyflow/react';

export function GenericNode({ data }: NodeProps) {
  return (
    <div className="flex items-center justify-center p-2 min-w-8 min-h-8 border border-dashed border-gray-400 rounded-md bg-gray-50 text-xs font-semibold text-gray-700">
      <Handle type="target" position={Position.Left} id="target" />
      {(data.label || data.reference) as string}
      <Handle type="source" position={Position.Right} id="source" />
      {/* Fallback extra handles for any pin if needed */}
      <Handle type="source" position={Position.Top} id="1" className="opacity-0" />
      <Handle type="source" position={Position.Bottom} id="2" className="opacity-0" />
      <Handle type="source" position={Position.Left} id="3" className="opacity-0" />
      <Handle type="source" position={Position.Right} id="4" className="opacity-0" />
    </div>
  );
}
