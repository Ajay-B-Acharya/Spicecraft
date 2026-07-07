/**
 * Auto-layout engine exports.
 *
 * Provides intelligent, topology-driven component placement for professional
 * schematic layout without UI or exporter dependencies.
 */
export { ComponentGrouping } from "./ComponentGrouping";
export { Grid } from "./Grid";
export { LayoutAnalyzer } from "./LayoutAnalyzer";
export { LayoutDebugger } from "./LayoutDebugger";
export { LayoutEngine } from "./LayoutEngine";
export { OrientationStrategy } from "./OrientationStrategy";
export type { ComponentOrientation } from "./OrientationStrategy";
export { PlacementStrategy } from "./PlacementStrategy";
export { PositionOptimizer } from "./PositionOptimizer";
export type {
  CircuitAnalysis,
  ComponentAnalysis,
  ComponentClassification,
  ComponentGroup,
  GridConfig,
  GridPosition,
  LayoutConfig,
  LayoutResult,
  PlacementHint,
  PlacementResult,
} from "./LayoutTypes";
export { DEFAULT_GRID_CONFIG, DEFAULT_LAYOUT_CONFIG } from "./LayoutTypes";
