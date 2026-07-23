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
import { CompiledCircuit } from '../types';

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
          const handleType = dir === 'right' || dir === 'bottom' ? 'source' : 'target';
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

  /**
   * Validate that all circuit nets reference valid component pins.
   * Returns a list of validation errors. An empty list means all nets are clean.
   *
   * Checks:
   *   - Every net has at least 2 pins
   *   - Every net references a component that exists in the circuit
   *   - Every net pin reference points to a pin that exists on that component
   *   - No duplicate pin references within a net
   */
  static validateHandles(circuit: Circuit): string[] {
    const errors: string[] = [];
    const componentsById = new Map(circuit.components.map((c) => [c.id, c]));

    circuit.nets.forEach((net) => {
      const netName = net.name ?? net.id;

      if (net.pins.length < 2) {
        errors.push(
          `Net "${netName}": has only ${net.pins.length} pin(s), needs at least 2 for a valid connection.`,
        );
      }

      const seenKeys = new Set<string>();

      net.pins.forEach((pinRef) => {
        const key = `${pinRef.componentId}:${pinRef.pinId}`;

        if (seenKeys.has(key)) {
          errors.push(`Net "${netName}": duplicate pin reference ${key}.`);
        }
        seenKeys.add(key);

        const component = componentsById.get(pinRef.componentId);

        if (!component) {
          errors.push(
            `Net "${netName}": references component "${pinRef.componentId}" which does not exist in the circuit.`,
          );
          return;
        }

        const pinExists = component.pins.some((p) => p.id === pinRef.pinId);

        if (!pinExists) {
          errors.push(
            `Net "${netName}": references pin "${pinRef.pinId}" on component "${pinRef.componentId}" (${component.type}), ` +
              `but that pin does not exist. Valid pins: [${component.pins.map((p) => p.id).join(', ')}].`,
          );
        }
      });
    });

    // Also check that every component pin that has a net assignment exists
    circuit.components.forEach((component) => {
      component.pins.forEach((pin) => {
        if (!pin.net) {
          return; // unconnected pins are allowed
        }

        const net = circuit.nets.find((n) => (n.name ?? n.id) === pin.net);

        if (!net) {
          errors.push(
            `Component "${component.id}" pin "${pin.id}" references net "${pin.net}" which does not exist.`,
          );
        }
      });
    });

    return errors;
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
