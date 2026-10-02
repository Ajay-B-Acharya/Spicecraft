/**
 * Pin System Debugger.
 *
 * Provides human-readable inspection of component pins, resolved coordinates,
 * React Flow handle mappings, electrical nets, and connection validity.
 * Use this during development and testing to identify handle mismatches,
 * missing pin definitions, or invalid electrical connections.
 *
 * Usage:
 *   PinSystemDebugger.printPins(component)
 *   PinSystemDebugger.printResolvedPins(circuit)
 *   PinSystemDebugger.printHandleMap(circuit)
 *   PinSystemDebugger.printConnections(circuit)
 *   PinSystemDebugger.validateHandles(circuit)
 */
import { Component } from '../models/Component';
import { Circuit } from '../models/Circuit';
import { Pin } from '../models/Pin';
import { Net } from '../models/Net';
import { ResolvedPin, resolvePins } from './PinResolver';
import { CompiledCircuit, CircuitValidationResult, VisualEdgeLike } from '../types';
import { CircuitValidator } from './CircuitValidator';
import { canonicalLabel, endpointKey } from './NetBuilder';

// ─── Formatting helpers ───────────────────────────────────────────────────────

function padRight(str: string, width: number): string {
  return str.padEnd(width, ' ');
}

function coordStr(x: number, y: number): string {
  return `(${x}, ${y})`;
}

function formatPin(pin: Pin, absoluteX?: number, absoluteY?: number): string {
  const abs =
    absoluteX !== undefined && absoluteY !== undefined
      ? `  abs:${coordStr(absoluteX, absoluteY)}`
      : '';
  const dir = pin.direction ? `  dir:${pin.direction}` : '';
  const net = pin.net ? `  net:${pin.net}` : '';
  return `  ${padRight(pin.id, 12)} rel:${coordStr(pin.x, pin.y)}${dir}${abs}  [${pin.name}]${net}`;
}

// ─── Public API ───────────────────────────────────────────────────────────────

export class PinSystemDebugger {
  /**
   * Print all pins for a single component with their relative coordinates.
   *
   * Example output:
   *   R1 (resistor)
   *     1            rel:(-32, 0)  dir:left   [left]
   *     2            rel:(32, 0)   dir:right  [right]
   */
  static formatPins(component: Component): string {
    const lines: string[] = [`${component.id} (${component.type})`];

    if (component.pins.length === 0) {
      lines.push('  <no pins>');
    } else {
      component.pins.forEach((pin) => {
        lines.push(formatPin(pin));
      });
    }

    return lines.join('\n');
  }

  static printPins(component: Component): string {
    const output = PinSystemDebugger.formatPins(component);
    console.log(output);
    return output;
  }

  /**
   * Print all resolved (absolute-coordinate) pins for all components in a
   * circuit. Rotation and mirror transformations are applied.
   *
   * Example output:
   *   R1 (resistor)  pos:(220, 160)  rot:0  mirror:false
   *     1            rel:(-32, 0)  dir:left   abs:(188, 160)  [left]
   *     2            rel:(32, 0)   dir:right  abs:(252, 160)  [right]
   */
  static formatResolvedPins(circuit: Circuit): string {
    const lines: string[] = ['Resolved Pins', '─────────────', ''];

    circuit.components.forEach((component) => {
      const resolved = resolvePins(component);
      const resolvedById = new Map<string, ResolvedPin>(
        resolved.map((rp) => [rp.id, rp]),
      );

      const pos = `pos:${coordStr(component.position.x, component.position.y)}`;
      const rot = `rot:${component.rotation}`;
      const mir = `mirror:${component.mirror ?? false}`;
      lines.push(`${component.id} (${component.type})  ${pos}  ${rot}  ${mir}`);

      component.pins.forEach((pin) => {
        const rp = resolvedById.get(pin.id);
        lines.push(formatPin(pin, rp?.absoluteX, rp?.absoluteY));
      });

      lines.push('');
    });

    return lines.join('\n').trimEnd();
  }

  static printResolvedPins(circuit: Circuit): string {
    const output = PinSystemDebugger.formatResolvedPins(circuit);
    console.log(output);
    return output;
  }

  /**
   * Print a mapping of React Flow handle IDs to their pin definitions.
   * This reflects exactly what IDs the dynamic UnifiedCircuitNode would emit.
   *
   * Example output:
   *   React Flow Handle Map
   *   ─────────────────────
   *
   *   R1 (resistor)
   *     handle:"1"  type:target  position:Left  pin:[left]
   *     handle:"2"  type:source  position:Right pin:[right]
   *
   *   Q1 (npn_transistor)
   *     handle:"C"  type:target  position:Top   pin:[collector]
   *     handle:"B"  type:target  position:Left  pin:[base]
   *     handle:"E"  type:source  position:Bottom pin:[emitter]
   */
  static formatHandleMap(circuit: Circuit): string {
    const lines: string[] = ['React Flow Handle Map', '─────────────────────', ''];

    circuit.components.forEach((component) => {
      lines.push(`${component.id} (${component.type})`);

      if (component.pins.length === 0) {
        lines.push('  <no handles>');
      } else {
        component.pins.forEach((pin) => {
          const dir = pin.direction ?? 'left';
          const handleType = 'source'; // All electrical handles use React Flow Loose mode.
          const position =
            dir === 'top' ? 'Top' : dir === 'bottom' ? 'Bottom' : dir === 'right' ? 'Right' : 'Left';
          lines.push(
            `  handle:"${padRight(pin.id + '"', 12)} type:${padRight(handleType, 8)} position:${padRight(position, 8)} pin:[${pin.name}]`,
          );
        });
      }

      lines.push('');
    });

    return lines.join('\n').trimEnd();
  }

  static printHandleMap(circuit: Circuit): string {
    const output = PinSystemDebugger.formatHandleMap(circuit);
    console.log(output);
    return output;
  }

  /**
   * Print all electrical nets and the pin connections they contain.
   *
   * Example output:
   *   Electrical Nets
   *   ───────────────
   *
   *   VCC
   *     labels: [VCC]
   *     R1.1  (resistor, left)
   *     R3.2  (resistor, right)
   *
   *   N1
   *     R1.2  (resistor, right)
   *     ↓ Q1.B  (npn_transistor, base)
   */
  static formatConnections(circuit: Circuit): string {
    const componentsById = new Map(circuit.components.map((c) => [c.id, c]));
    const lines: string[] = ['Electrical Nets', '───────────────', ''];

    if (circuit.nets.length === 0) {
      lines.push('  <no nets>');
      return lines.join('\n');
    }

    circuit.nets.forEach((net) => {
      const displayName = net.name ?? net.id;
      lines.push(displayName);

      if (net.labels && net.labels.length > 0) {
        lines.push(`  labels: [${net.labels.join(', ')}]`);
      }

      net.pins.forEach((pinRef, i) => {
        const component = componentsById.get(pinRef.componentId);
        const pin = component?.pins.find((p) => p.id === pinRef.pinId);
        const desc = pin ? `${component!.type}, ${pin.name}` : component?.type ?? 'unknown';
        const arrow = i > 0 ? '↓ ' : '  ';
        lines.push(`  ${arrow}${pinRef.componentId}.${pinRef.pinId}  (${desc})`);
      });

      lines.push('');
    });

    return lines.join('\n').trimEnd();
  }

  static printConnections(circuit: Circuit): string {
    const output = PinSystemDebugger.formatConnections(circuit);
    console.log(output);
    return output;
  }

  /** Validate source equivalence, pin identities and reciprocal net membership. */
  static validateNets(circuit: Circuit): CircuitValidationResult {
    return CircuitValidator.validate(circuit, 'validation' in circuit ? (circuit as CompiledCircuit).validation : {});
  }

  /** Validate electrical graph and, when supplied, exact rendered edge handles. */
  static validateHandles(circuit: Circuit, edges: VisualEdgeLike[] = []): string[] {
    return [...new Set([
      ...PinSystemDebugger.validateNets(circuit).errors,
      ...PinSystemDebugger.findInvalidConnections(circuit, edges),
    ])];
  }

  static tracePin(circuit: Circuit, componentId: string, pinId: string): string {
    const component = circuit.components.find(item => item.id === componentId);
    const pin = component?.pins.find(item => item.id === pinId);
    if (!pin) return `Invalid pin ${componentId}.${pinId}.`;
    const nets = circuit.nets.filter(net => net.pins.some(ref => ref.componentId === componentId && ref.pinId === pinId));
    const connections = (circuit.connections ?? []).filter(connection => [connection.source, connection.target].some(ref =>
      ref.componentId === componentId && ref.pinId === pinId));
    return [
      `Handle ${componentId}.${pinId} -> pin [${pin.name}] -> net ID ${pin.net ?? '<unconnected>'}`,
      `Net membership: ${nets.map(net => net.id).join(', ') || '<none>'}`,
      ...connections.map(connection => `Source edge ${connection.id ?? '<unnamed>'}: ${endpointKey(connection.source)} -> ${endpointKey(connection.target)}`),
    ].join('\n');
  }

  static traceNet(circuit: Circuit, netId: string): string {
    const net = circuit.nets.find(item => item.id === netId);
    if (!net) return `Invalid net ID ${netId}.`;
    return [
      `Net ID ${net.id} (${net.name ?? net.id}), labels: [${(net.labels ?? []).join(', ')}]`,
      ...net.pins.map(ref => PinSystemDebugger.tracePin(circuit, ref.componentId, ref.pinId)),
    ].join('\n');
  }

  static findInvalidConnections(circuit: Circuit, edges: VisualEdgeLike[] = []): string[] {
    const errors = PinSystemDebugger.validateNets(circuit).errors.filter(message => /connection|source|pin|overlap|reciprocal/i.test(message));
    edges.forEach((edge, index) => {
      const description = edge.id ?? `#${index + 1}`;
      const endpoints = [[edge.source, edge.sourceHandle], [edge.target, edge.targetHandle]] as const;
      const memberships: string[][] = [];
      endpoints.forEach(([componentId, handle]) => {
        if (componentId.startsWith('net-label:')) {
          const labelNets = circuit.nets.filter(net => (net.labels ?? []).some(label =>
            componentId === `net-label:${JSON.stringify([net.id, label])}`));
          const ids = handle === 'net' ? labelNets.map(net => net.id) : [];
          memberships.push(ids);
          if (ids.length !== 1) errors.push(`Edge ${description}: label handle ${componentId}.${handle ?? '<missing>'} does not identify one electrical net.`);
          return;
        }
        const component = circuit.components.find(item => item.id === componentId);
        const pin = component?.pins.find(item => item.id === handle);
        if (!handle || !pin) {
          errors.push(`Edge ${description}: handle ${componentId}.${handle ?? '<missing>'} has no canonical component pin.`);
          memberships.push([]);
          return;
        }
        const ids = circuit.nets.filter(net => net.pins.some(ref => ref.componentId === componentId && ref.pinId === handle)).map(net => net.id);
        memberships.push(ids);
        if (ids.length !== 1 || pin.net !== ids[0]) errors.push(`Edge ${description}: handle ${componentId}.${handle} -> pin -> net ID mapping is not unambiguous/reciprocal.`);
      });
      if (edge.source === edge.target && edge.sourceHandle === edge.targetHandle) errors.push(`Edge ${description} is a self-connection.`);
      if (!memberships[0].some(id => memberships[1].includes(id))) errors.push(`Edge ${description} endpoints do not share an electrical net.`);
    });
    return [...new Set(errors)];
  }

  /**
   * Run all validations and print a summary report.
   */
  static report(circuit: Circuit | CompiledCircuit): string {
    const lines: string[] = ['Pin System Validation Report', '═══════════════════════════', ''];

    const errors = PinSystemDebugger.validateHandles(circuit);

    if (errors.length === 0) {
      lines.push('✓ All nets reference valid pins.');
    } else {
      lines.push(`✗ ${errors.length} validation error(s):`);
      errors.forEach((e) => lines.push(`  • ${e}`));
    }

    lines.push('');

    // Report compiled circuit validation if available
    if ('validation' in circuit) {
      const v = circuit.validation;
      if (v.errors.length === 0 && v.warnings.length === 0) {
        lines.push('✓ Circuit compilation: clean.');
      } else {
        if (v.errors.length > 0) {
          lines.push(`✗ Compiler errors (${v.errors.length}):`);
          v.errors.forEach((e) => lines.push(`  • ${e}`));
        }
        if (v.warnings.length > 0) {
          lines.push(`⚠ Compiler warnings (${v.warnings.length}):`);
          v.warnings.forEach((w) => lines.push(`  • ${w}`));
        }
      }
    }

    lines.push('');
    lines.push(`Components : ${circuit.components.length}`);
    lines.push(`Nets       : ${circuit.nets.length}`);
    lines.push(
      `Total pins : ${circuit.components.reduce((s, c) => s + c.pins.length, 0)}`,
    );

    return lines.join('\n');
  }

  static printReport(circuit: Circuit | CompiledCircuit): string {
    const output = PinSystemDebugger.report(circuit);
    console.log(output);
    return output;
  }
}
