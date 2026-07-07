/**
 * Circuit engine exports.
 *
 * Collects reusable EDA engine services while keeping them independent of UI,
 * storage, and exporter implementations.
 */
export {
  ComponentLibrary,
  componentLibrary,
  createComponent,
  getDefinition,
  has,
  list,
} from "./ComponentLibrary";
export { CircuitBuilder } from "./CircuitBuilder";
export { CircuitCompiler } from "./CircuitCompiler";
export { CircuitDebugger } from "./CircuitDebugger";
export { CircuitValidator, validateCircuit } from "./CircuitValidator";
export { resolvePin, resolvePins } from "./PinResolver";
export type { ResolvedPin } from "./PinResolver";
export {
  buildNets,
  buildNetsFromVisualEdges,
  visualEdgesToConnections,
} from "./NetBuilder";
