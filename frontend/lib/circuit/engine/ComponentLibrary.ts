/**
 * Component library manager.
 *
 * Provides the single access point for built-in component metadata and creates
 * initialized component instances from definitions. UI, exporters, parsers, and
 * future EDA modules should request component metadata here instead of hardcoding
 * symbols, prefixes, default values, or pins.
 */
import { componentDefinitions } from '../library';
import { Component } from '../models/Component';
import { Pin } from '../models/Pin';
import { ComponentDefinition, CreateComponentOptions } from '../types';

function clonePins(pins: Pin[]): Pin[] {
  return pins.map((pin) => ({ ...pin }));
}

export class ComponentLibrary {
  private readonly definitions: Map<string, ComponentDefinition>;

  private readonly instanceCounters = new Map<string, number>();

  constructor(definitions: ComponentDefinition[] = componentDefinitions) {
    this.definitions = new Map();

    definitions.forEach((definition) => {
      if (this.definitions.has(definition.type)) {
        throw new Error(`Duplicate component definition type: ${definition.type}`);
      }

      this.definitions.set(definition.type, {
        ...definition,
        pins: clonePins(definition.pins),
      });
    });
  }

  getDefinition(type: string): ComponentDefinition | undefined {
    const definition = this.definitions.get(type);

    if (!definition) {
      return undefined;
    }

    return {
      ...definition,
      pins: clonePins(definition.pins),
    };
  }

  createComponent(type: string, options: CreateComponentOptions = {}): Component {
    const definition = this.getRequiredDefinition(type);
    const id = options.id ?? this.nextId(definition.prefix);

    return {
      id,
      type: definition.type,
      name: options.name ?? id,
      value: options.value ?? definition.defaultValue,
      symbol: definition.symbol,
      prefix: definition.prefix,
      rotation: options.rotation ?? definition.defaultRotation,
      mirror: options.mirror,
      position: options.position ?? { x: 0, y: 0 },
      pins: clonePins(definition.pins),
    };
  }

  has(type: string): boolean {
    return this.definitions.has(type);
  }

  list(): ComponentDefinition[] {
    return Array.from(this.definitions.values()).map((definition) => ({
      ...definition,
      pins: clonePins(definition.pins),
    }));
  }

  private getRequiredDefinition(type: string): ComponentDefinition {
    const definition = this.getDefinition(type);

    if (!definition) {
      throw new Error(`Unknown component type: ${type}`);
    }

    return definition;
  }

  private nextId(prefix: string): string {
    const next = (this.instanceCounters.get(prefix) ?? 0) + 1;
    this.instanceCounters.set(prefix, next);

    return `${prefix}${next}`;
  }
}

export const componentLibrary = new ComponentLibrary();

export function getDefinition(type: string): ComponentDefinition | undefined {
  return componentLibrary.getDefinition(type);
}

export function createComponent(type: string, options?: CreateComponentOptions): Component {
  return componentLibrary.createComponent(type, options);
}

export function has(type: string): boolean {
  return componentLibrary.has(type);
}

export function list(): ComponentDefinition[] {
  return componentLibrary.list();
}
