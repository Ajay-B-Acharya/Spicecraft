/**
 * Net builder engine.
 *
 * Translates visual wire connectivity into electrical nets. The implementation
 * is UI-independent: callers may provide normalized VisualConnection objects or
 * adapt visual edge-like objects at the boundary without importing React Flow.
 */
import { Net } from '../models/Net';
import {
  PinConnection,
  VisualConnection,
  VisualEdgeAdapterOptions,
  VisualEdgeLike,
} from '../types';

class DisjointSet {
  private readonly parent = new Map<string, string>();

  add(item: string): void {
    if (!this.parent.has(item)) {
      this.parent.set(item, item);
    }
  }

  find(item: string): string {
    this.add(item);

    const parent = this.parent.get(item);

    if (!parent) {
      return item;
    }

    if (parent === item) {
      return item;
    }

    const root = this.find(parent);
    this.parent.set(item, root);

    return root;
  }

  union(left: string, right: string): void {
    const leftRoot = this.find(left);
    const rightRoot = this.find(right);

    if (leftRoot !== rightRoot) {
      this.parent.set(rightRoot, leftRoot);
    }
  }

  entries(): string[] {
    return Array.from(this.parent.keys());
  }
}

function endpointKey(endpoint: PinConnection): string {
  return `${endpoint.componentId}:${endpoint.pinId}`;
}

function parseEndpointKey(key: string): PinConnection {
  const separatorIndex = key.indexOf(':');

  return {
    componentId: key.slice(0, separatorIndex),
    pinId: key.slice(separatorIndex + 1),
  };
}

function dedupePins(pins: PinConnection[]): PinConnection[] {
  const seen = new Set<string>();
  const result: PinConnection[] = [];

  pins.forEach((pin) => {
    const key = endpointKey(pin);

    if (!seen.has(key)) {
      seen.add(key);
      result.push(pin);
    }
  });

  return result;
}

export function buildNets(connections: VisualConnection[], netPrefix = 'N'): Net[] {
  const disjointSet = new DisjointSet();

  connections.forEach((connection) => {
    const sourceKey = endpointKey(connection.source);
    const targetKey = endpointKey(connection.target);

    disjointSet.add(sourceKey);
    disjointSet.add(targetKey);
    disjointSet.union(sourceKey, targetKey);
  });

  const groupedPins = new Map<string, PinConnection[]>();

  disjointSet.entries().forEach((key) => {
    const root = disjointSet.find(key);
    const pins = groupedPins.get(root) ?? [];
    pins.push(parseEndpointKey(key));
    groupedPins.set(root, pins);
  });

  return Array.from(groupedPins.values()).map((pins, index) => ({
    id: `${netPrefix}${index + 1}`,
    pins: dedupePins(pins),
  }));
}

export function visualEdgesToConnections(
  edges: VisualEdgeLike[],
  options: VisualEdgeAdapterOptions = {},
): VisualConnection[] {
  return edges.flatMap((edge) => {
    const sourcePinId = options.getSourcePinId?.(edge) ?? edge.sourceHandle ?? options.defaultSourcePinId;
    const targetPinId = options.getTargetPinId?.(edge) ?? edge.targetHandle ?? options.defaultTargetPinId;

    if (!sourcePinId || !targetPinId) {
      return [];
    }

    return [
      {
        id: edge.id,
        source: {
          componentId: edge.source,
          pinId: sourcePinId,
        },
        target: {
          componentId: edge.target,
          pinId: targetPinId,
        },
      },
    ];
  });
}

export function buildNetsFromVisualEdges(
  edges: VisualEdgeLike[],
  options?: VisualEdgeAdapterOptions,
  netPrefix?: string,
): Net[] {
  return buildNets(visualEdgesToConnections(edges, options), netPrefix);
}
