/** Validates canonical pins, reciprocal net membership and source/net equivalence. */
import { Circuit } from '../models/Circuit';
import { Component } from '../models/Component';
import { Pin } from '../models/Pin';
import { componentLibrary } from './ComponentLibrary';
import { buildNets, canonicalLabel, endpointKey, isLabelConnection, labelConnection } from './NetBuilder';
import { CircuitValidationResult, CircuitValidationSeed, PinConnection, ResolvedPinLike } from '../types';

function hasText(value: string | undefined): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function netSignature(pins: PinConnection[], labels: string[] = []): string {
  return JSON.stringify([...new Set([
    ...pins.map(endpointKey), ...labels.map(label => endpointKey(labelConnection(label))),
  ])].sort());
}

export class CircuitValidator {
  static validate(circuit: Circuit, seed: CircuitValidationSeed = {}): CircuitValidationResult {
    const warnings = [...(seed.warnings ?? [])];
    const errors = [...(seed.errors ?? [])];
    const componentsById = new Map<string, Component>();
    const pinsByKey = new Map<string, Pin>();
    const membership = new Map<string, string[]>();
    const netsById = new Map<string, Circuit['nets'][number]>();
    const labelsByIdentity = new Map<string, string>();
    if (circuit.components.length === 0 && circuit.nets.length === 0) warnings.push('Circuit is empty: no components or connections.');

    circuit.components.forEach(component => {
      if (!hasText(component.id)) errors.push('Missing component reference.');
      if (componentsById.has(component.id)) errors.push(`Duplicate component ID detected: ${component.id}.`);
      else componentsById.set(component.id, component);
      const definition = componentLibrary.getDefinition(component.type);
      if (!definition) errors.push(`Unknown component type '${component.type}' on component ${component.id || '<unknown>'}.`);
      if (!hasText(component.value)) warnings.push(`Missing value on component ${component.id || '<unknown>'}.`);
      if (component.pins.length === 0) errors.push(`Component ${component.id || '<unknown>'} has no pins.`);
      const ids = new Set<string>();
      component.pins.forEach(pin => {
        const key = endpointKey({ componentId: component.id, pinId: pin.id });
        if (!hasText(pin.id)) errors.push(`Missing pin identity on component ${component.id}.`);
        if (ids.has(pin.id)) errors.push(`Duplicate pin identity ${component.id}.${pin.id}.`);
        ids.add(pin.id);
        if (definition && !definition.pins.some(expected => expected.id === pin.id)) {
          errors.push(`Invalid pin identity ${component.id}.${pin.id} for ${component.type}.`);
        }
        if (!pinsByKey.has(key)) pinsByKey.set(key, pin);
      });
      definition?.pins.forEach(pin => {
        if (!ids.has(pin.id)) errors.push(`Component ${component.id} is missing expected pin ${pin.id} (${pin.name}).`);
      });
    });

    circuit.nets.forEach(net => {
      const display = `${net.id}${net.name && net.name !== net.id ? ` (${net.name})` : ''}`;
      if (!hasText(net.id)) errors.push('Missing net ID.');
      if (netsById.has(net.id)) errors.push(`Duplicate net ID: ${net.id}.`);
      else netsById.set(net.id, net);
      const labels = net.labels ?? [];
      const identities = new Set(labels.map(canonicalLabel));
      if (identities.has('GND') && identities.has('VCC')) errors.push(`Net ${display} has conflicting GND/VCC labels.`);
      labels.forEach(label => {
        if (!hasText(label)) errors.push(`Net ${display} has an empty label.`);
        const identity = canonicalLabel(label);
        const owner = labelsByIdentity.get(identity);
        if (owner !== undefined && owner !== net.id) errors.push(`Label ${label} overlaps nets ${owner} and ${net.id}.`);
        labelsByIdentity.set(identity, net.id);
      });
      if (net.pins.length === 0) warnings.push(`Net ${display} has no connected component pins.`);
      else if (net.pins.length === 1 && labels.length === 0) warnings.push(`Net ${display} has only one component pin and no labeled port; it is floating.`);
      const seen = new Set<string>();
      net.pins.forEach(ref => {
        const key = endpointKey(ref);
        if (seen.has(key)) errors.push(`Net ${display} contains duplicate pin reference ${ref.componentId}.${ref.pinId}.`);
        seen.add(key);
        const owners = membership.get(key) ?? [];
        if (!owners.includes(net.id)) owners.push(net.id);
        membership.set(key, owners);
        const component = componentsById.get(ref.componentId);
        const pin = pinsByKey.get(key);
        if (!component) errors.push(`Net ${display} references missing component ${ref.componentId}.`);
        else if (!pin) errors.push(`Net ${display} references invalid pin ${ref.componentId}.${ref.pinId}.`);
        else if (pin.net !== net.id) errors.push(`Net ${net.id} membership for ${ref.componentId}.${ref.pinId} is not reciprocal: pin.net is ${pin.net ?? '<unassigned>'}.`);
      });
    });

    membership.forEach((owners, key) => {
      if (owners.length > 1) errors.push(`Pin ${key} overlaps multiple nets: ${owners.join(', ')}.`);
    });
    circuit.components.forEach(component => {
      if (!component.pins.some(pin => (membership.get(endpointKey({ componentId: component.id, pinId: pin.id }))?.length ?? 0) > 0)) {
        warnings.push(`Component ${component.id || '<unknown>'} is floating.`);
      }
      component.pins.forEach(pin => {
        const owners = membership.get(endpointKey({ componentId: component.id, pinId: pin.id })) ?? [];
        if (pin.net !== undefined) {
          if (!netsById.has(pin.net)) errors.push(`Pin ${component.id}.${pin.id} references missing net ID ${pin.net}.`);
          else if (!owners.includes(pin.net)) errors.push(`Pin ${component.id}.${pin.id} references net ${pin.net} without reciprocal membership.`);
        }
        if (owners.length === 0) {
          const optional = pin.optional || (component.type === 'ne555' && pin.id === '5');
          warnings.push(optional
            ? `Optional pin ${component.id}.${pin.id} (${pin.name}) is unconnected; permitted.`
            : `Expected pin ${component.id}.${pin.id} (${pin.name}) is floating/unconnected${component.type === 'ne555' && pin.id === '4' ? '; RESET must be driven for reliable operation' : ''}.`);
        }
      });
    });

    if ('resolvedPins' in circuit && Array.isArray(circuit.resolvedPins)) {
      const seen = new Set<string>();
      (circuit.resolvedPins as ResolvedPinLike[]).forEach(pin => {
        const key = endpointKey({ componentId: pin.componentId, pinId: pin.id });
        if (seen.has(key)) errors.push(`Duplicate resolved pin identity ${pin.componentId}.${pin.id}.`);
        seen.add(key);
        const definition = pinsByKey.get(key);
        if (!definition) errors.push(`Resolved pin ${pin.componentId}.${pin.id} has no component pin.`);
        else if (definition.net !== pin.net) errors.push(`Resolved pin ${pin.componentId}.${pin.id} net ID disagrees with its component pin.`);
      });
      pinsByKey.forEach((_pin, key) => { if (!seen.has(key)) errors.push(`Missing resolved pin ${key}.`); });
    }

    if (circuit.connections !== undefined) {
      const seen = new Set<string>();
      circuit.connections.forEach((connection, index) => {
        const description = connection.id ?? `#${index + 1}`;
        const keys = [connection.source, connection.target].map(endpointKey);
        if (keys[0] === keys[1]) errors.push(`Connection ${description} is a self-connection to the same endpoint.`);
        const pair = JSON.stringify([...keys].sort());
        if (seen.has(pair)) warnings.push(`Duplicate source connection ${description}.`);
        seen.add(pair);
        for (const endpoint of [connection.source, connection.target]) {
          if (!isLabelConnection(endpoint) && !pinsByKey.has(endpointKey(endpoint))) {
            errors.push(`Connection ${description} references invalid pin ${endpoint.componentId}.${endpoint.pinId}.`);
          }
        }
      });
      // Compare complete partitions, not just the presence of each source pair:
      // extra merges, split nets, missing edges and invented pins/labels all fail.
      const expected = buildNets(circuit.connections).map(net => netSignature(net.pins));
      const actual = circuit.nets.map(net => netSignature(net.pins, net.labels));
      if (JSON.stringify([...expected].sort()) !== JSON.stringify([...actual].sort())) {
        errors.push('Source connections and electrical nets are not equivalent: missing, extra, split, or merged connectivity.');
      }
    }

    // Conservative DC-return diagnostic only. Capacitors and active-device
    // internal paths are deliberately excluded; no source wires are invented.
    const returnNets = new Set(circuit.nets.filter(net =>
      (net.labels ?? []).some(label => ['GND', 'VCC'].includes(canonicalLabel(label))) ||
      net.pins.some(ref => componentsById.get(ref.componentId)?.type === 'ground'),
    ).map(net => net.id));
    const dcLinks = new Map<string, Set<string>>();
    circuit.components.filter(component => ['resistor', 'inductor', 'voltage_source'].includes(component.type)).forEach(component => {
      const ids = component.pins.map(pin => pin.net).filter(hasText);
      ids.forEach(id => {
        const links = dcLinks.get(id) ?? new Set<string>();
        ids.forEach(other => links.add(other));
        dcLinks.set(id, links);
      });
    });
    circuit.components.filter(component => /^(npn|pnp)_transistor$/.test(component.type)).forEach(component => {
      const emitter = component.pins.find(pin => pin.id === 'E');
      if (!emitter?.net) return; // Already covered by the expected-pin warning.
      const pending = [emitter.net];
      const visited = new Set<string>();
      let found = false;
      while (pending.length) {
        const id = pending.pop()!;
        if (visited.has(id)) continue;
        visited.add(id);
        if (returnNets.has(id)) { found = true; break; }
        pending.push(...(dcLinks.get(id) ?? []));
      }
      if (!found) warnings.push(`Transistor ${component.id}.E has no evident DC emitter return to GND/VCC through explicit resistive/inductive paths; capacitors do not provide a DC return.`);
    });

    const uniqueErrors = [...new Set(errors)];
    return { valid: uniqueErrors.length === 0, warnings: [...new Set(warnings)], errors: uniqueErrors };
  }
}

export function validateCircuit(circuit: Circuit, seed?: CircuitValidationSeed): CircuitValidationResult {
  return CircuitValidator.validate(circuit, seed);
}
