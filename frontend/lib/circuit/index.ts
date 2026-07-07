/**
 * SpiceCraft circuit engine public API.
 *
 * This package contains the UI-independent electrical model, component library,
 * and engine utilities that will become the single source of truth for future
 * EDA features such as LTspice export, KiCad export, SPICE netlists, ERC,
 * simulation, auto-routing, and PCB generation.
 */
export type {
  CircuitBuildResult,
  CircuitValidationResult,
  CircuitValidationSeed,
  CompiledCircuit,
  ComponentDefinition,
  CreateComponentOptions,
  PinConnection,
  PinDirection,
  ResolvedPinLike,
  VisualConnection,
  VisualEdgeAdapterOptions,
  VisualEdgeLike,
} from "./types";
export * from "./models";
export * from "./library";
export * from "./engine";
