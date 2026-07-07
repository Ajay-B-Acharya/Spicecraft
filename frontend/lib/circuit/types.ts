/**
 * Shared circuit-engine type contracts.
 *
 * These types define reusable, UI-independent metadata used by the component
 * library and engine modules. Visual frameworks should adapt into these shapes
 * at system boundaries instead of leaking renderer-specific objects into the
 * electrical model.
 */
import { Circuit } from "./models/Circuit";
import { Component } from "./models/Component";
import { Pin } from "./models/Pin";

export type PinDirection = NonNullable<Pin["direction"]>;

export interface ComponentDefinition {
  type: string;
  symbol: string;
  prefix: string;
  defaultValue?: string;
  defaultRotation: number;
  pins: Pin[];
}

export interface CreateComponentOptions {
  id?: string;
  name?: string;
  value?: string;
  rotation?: number;
  mirror?: boolean;
  position?: Component["position"];
}

export interface PinConnection {
  componentId: string;
  pinId: string;
}

export interface VisualConnection {
  id?: string;
  source: PinConnection;
  target: PinConnection;
}

/**
 * Minimal edge shape accepted by NetBuilder adapters.
 *
 * This intentionally does not import React Flow. It only captures the generic
 * fields needed to translate a visual edge into two electrical pin endpoints.
 */
export interface VisualEdgeLike {
  id?: string;
  source: string;
  target: string;
  sourceHandle?: string | null;
  targetHandle?: string | null;
}

export interface VisualEdgeAdapterOptions {
  defaultSourcePinId?: string;
  defaultTargetPinId?: string;
  getSourcePinId?: (edge: VisualEdgeLike) => string | undefined;
  getTargetPinId?: (edge: VisualEdgeLike) => string | undefined;
}

export interface CircuitValidationResult {
  valid: boolean;
  warnings: string[];
  errors: string[];
}

export interface CircuitValidationSeed {
  warnings?: string[];
  errors?: string[];
}

export interface ResolvedPinLike extends Pin {
  componentId: string;
  componentName: string;
  absoluteX: number;
  absoluteY: number;
}

export interface CompiledCircuit extends Circuit {
  resolvedPins: ResolvedPinLike[];
  validation: CircuitValidationResult;
}

export interface CircuitBuildResult {
  circuit: CompiledCircuit;
  validationSeed: CircuitValidationSeed;
}
