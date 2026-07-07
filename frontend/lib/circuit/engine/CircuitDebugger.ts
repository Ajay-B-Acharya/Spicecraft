/**
 * Circuit debug formatter.
 *
 * Produces a stable, human-readable text representation of the compiled
 * electrical model before any export step. This is intended for debugging,
 * inspection, and future developer tooling.
 */
import { Circuit } from '../models/Circuit';
import { Component } from '../models/Component';
import { Net } from '../models/Net';

function formatPinLabel(component: Component, pinId: string): string {
  const pin = component.pins.find((candidate) => candidate.id === pinId);
  const label = pin?.name ?? pinId;

  if (/^[0-9+-]+$/.test(pinId)) {
    return pinId;
  }

  return label.charAt(0).toUpperCase() + label.slice(1);
}

function formatNetPinReference(component: Component | undefined, pinId: string, componentId: string): string {
  if (!component) {
    return `${componentId}.${pinId}`;
  }

  if (/^[0-9+-]+$/.test(pinId)) {
    return `${componentId}.${pinId}`;
  }

  const pin = component.pins.find((candidate) => candidate.id === pinId);
  return `${componentId}.${pin?.name ?? pinId}`;
}

function netDisplayName(net: Net): string {
  return net.name ?? net.id;
}

export class CircuitDebugger {
  static format(circuit: Circuit): string {
    const componentsById = new Map(circuit.components.map((component) => [component.id, component]));
    const lines: string[] = ['Components', '----------', ''];

    circuit.components.forEach((component) => {
      lines.push(component.id || component.name || '<unknown>');
      lines.push(' Pins:');

      component.pins.forEach((pin) => {
        lines.push(` ${formatPinLabel(component, pin.id)} -> ${pin.net ?? 'UNCONNECTED'}`);
      });

      lines.push('');
    });

    lines.push('------------------------', '');
    lines.push('Nets', '');

    circuit.nets.forEach((net) => {
      lines.push(netDisplayName(net));

      (net.labels ?? []).forEach((label) => {
        lines.push(` ${label}`);
      });

      net.pins.forEach((pinReference) => {
        lines.push(
          ` ${formatNetPinReference(
            componentsById.get(pinReference.componentId),
            pinReference.pinId,
            pinReference.componentId,
          )}`,
        );
      });

      lines.push('');
    });

    return lines.join('\n').trimEnd();
  }

  static print(circuit: Circuit): string {
    const output = CircuitDebugger.format(circuit);
    console.log(output);
    return output;
  }
}
