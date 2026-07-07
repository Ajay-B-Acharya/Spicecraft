/**
 * Circuit validation engine.
 *
 * Validates a UI-independent circuit object and returns accumulated warnings and
 * errors without throwing. Compiler and future importers can seed additional
 * parse/build diagnostics so all issues are reported together.
 */
import { Circuit } from '../models/Circuit';
import { Component } from '../models/Component';
import { componentLibrary } from './ComponentLibrary';
import { CircuitValidationResult, CircuitValidationSeed } from '../types';

function hasText(value: string | undefined): boolean {
  return typeof value === 'string' && value.trim().length > 0;
}

function uniqueMessages(messages: string[]): string[] {
  return Array.from(new Set(messages));
}

function isComponentConnected(component: Component): boolean {
  return component.pins.some((pin) => hasText(pin.net));
}

export class CircuitValidator {
  static validate(circuit: Circuit, seed: CircuitValidationSeed = {}): CircuitValidationResult {
    const warnings = [...(seed.warnings ?? [])];
    const errors = [...(seed.errors ?? [])];
    const componentIdCounts = new Map<string, number>();
    const componentsById = new Map<string, Component>();

    circuit.components.forEach((component) => {
      const currentCount = (componentIdCounts.get(component.id) ?? 0) + 1;
      componentIdCounts.set(component.id, currentCount);

      if (!componentsById.has(component.id)) {
        componentsById.set(component.id, component);
      }

      if (!hasText(component.id)) {
        errors.push('Missing component reference.');
      }

      if (!componentLibrary.has(component.type)) {
        errors.push(`Unknown component type '${component.type}' on component ${component.id || '<unknown>'}.`);
      }

      if (!hasText(component.value)) {
        warnings.push(`Missing value on component ${component.id || '<unknown>'}.`);
      }

      if (component.pins.length === 0) {
        errors.push(`Component ${component.id || '<unknown>'} has no pins.`);
      }
    });

    componentIdCounts.forEach((count, componentId) => {
      if (componentId && count > 1) {
        errors.push(`Duplicate component ID detected: ${componentId}.`);
      }
    });

    circuit.nets.forEach((net) => {
      const netName = net.name ?? net.id;

      if (net.pins.length < 2) {
        warnings.push(`Net ${netName} has fewer than two connected component pins.`);
      }

      net.pins.forEach((pinReference) => {
        const component = componentsById.get(pinReference.componentId);

        if (!component) {
          errors.push(`Net ${netName} references missing component ${pinReference.componentId}.`);
          return;
        }

        const hasPin = component.pins.some((pin) => pin.id === pinReference.pinId);

        if (!hasPin) {
          errors.push(`Net ${netName} references invalid pin ${pinReference.componentId}.${pinReference.pinId}.`);
        }
      });
    });

    circuit.components.forEach((component) => {
      if (!isComponentConnected(component)) {
        warnings.push(`Component ${component.id || '<unknown>'} is floating.`);
      }
    });

    const uniqueWarnings = uniqueMessages(warnings);
    const uniqueErrors = uniqueMessages(errors);

    return {
      valid: uniqueErrors.length === 0,
      warnings: uniqueWarnings,
      errors: uniqueErrors,
    };
  }
}

export function validateCircuit(circuit: Circuit, seed?: CircuitValidationSeed): CircuitValidationResult {
  return CircuitValidator.validate(circuit, seed);
}
