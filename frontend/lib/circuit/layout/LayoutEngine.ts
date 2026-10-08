/**
 * Intelligent auto-layout engine.
 *
 * Orchestrates component placement using topology analysis, rule-based placement
 * strategy, grid snapping, and position optimization. The engine operates
 * exclusively on Circuit objects without React Flow or exporter dependencies so
 * future export targets (LTspice, KiCad, SVG, PDF) can reuse the same placement
 * logic.
 */
import { Circuit } from "../models/Circuit";
import { Component } from "../models/Component";
import { CIRCUIT_INPUT_LIMITS } from "../engine/CircuitBuilder";
import { CircuitValidator } from "../engine/CircuitValidator";
import { resolvePins } from "../engine/PinResolver";
import type { CircuitValidationResult } from "../types";
import { Grid } from "./Grid";
import { LayoutAnalyzer } from "./LayoutAnalyzer";
import { OrientationStrategy } from "./OrientationStrategy";
import { PlacementStrategy } from "./PlacementStrategy";
import { PositionOptimizer } from "./PositionOptimizer";
import {
  DEFAULT_LAYOUT_CONFIG,
  GridPosition,
  LayoutConfig,
  LayoutResult,
  PlacementResult,
} from "./LayoutTypes";

function computeBounds(
  placements: Map<string, PlacementResult>,
): LayoutResult["bounds"] {
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;

  placements.forEach((placement) => {
    const { x, y } = placement.absolutePosition;
    minX = Math.min(minX, x);
    maxX = Math.max(maxX, x);
    minY = Math.min(minY, y);
    maxY = Math.max(maxY, y);
  });

  if (placements.size === 0) {
    minX = 0;
    maxX = 0;
    minY = 0;
    maxY = 0;
  }

  return {
    minX,
    maxX,
    minY,
    maxY,
    width: maxX - minX,
    height: maxY - minY,
  };
}

function computeGridBounds(
  placements: Map<string, PlacementResult>,
): LayoutResult["gridBounds"] {
  let minCol = Infinity;
  let maxCol = -Infinity;
  let minRow = Infinity;
  let maxRow = -Infinity;

  placements.forEach((placement) => {
    const { col, row } = placement.gridPosition;
    minCol = Math.min(minCol, col);
    maxCol = Math.max(maxCol, col);
    minRow = Math.min(minRow, row);
    maxRow = Math.max(maxRow, row);
  });

  if (placements.size === 0) {
    minCol = 0;
    maxCol = 0;
    minRow = 0;
    maxRow = 0;
  }

  return {
    minCol,
    maxCol,
    minRow,
    maxRow,
    cols: maxCol - minCol + 1,
    rows: maxRow - minRow + 1,
  };
}

function applyLayoutToCircuit(
  circuit: Circuit,
  layoutResult: LayoutResult,
): Circuit {
  const updatedComponents = circuit.components.map((component) => {
    const placement = layoutResult.placements.get(component.id);

    if (!placement) {
      return component;
    }

    return {
      ...component,
      position: placement.absolutePosition,
      rotation: placement.rotation,
      mirror: placement.mirror,
    };
  });

  return {
    ...circuit,
    components: updatedComponents,
    ...('resolvedPins' in circuit ? { resolvedPins: updatedComponents.flatMap(resolvePins) } : {}),
  };
}

export class LayoutEngine {
  private readonly config: LayoutConfig;
  private readonly grid: Grid;
  private readonly optimizer: PositionOptimizer;

  constructor(config: LayoutConfig = DEFAULT_LAYOUT_CONFIG) {
    this.config = { ...config, grid: { ...config.grid } };
    this.grid = new Grid(this.config.grid);
    this.optimizer = new PositionOptimizer();
  }

  layout(circuit: Circuit): Circuit {
    const layoutResult = this.computeLayout(circuit);
    return applyLayoutToCircuit(circuit, layoutResult);
  }

  computeLayout(circuit: Circuit): LayoutResult {
    if (circuit.components.length > CIRCUIT_INPUT_LIMITS.components ||
        circuit.nets.length > CIRCUIT_INPUT_LIMITS.wires ||
        (circuit.connections?.length ?? 0) > CIRCUIT_INPUT_LIMITS.wires ||
        circuit.components.reduce((total, component) => total + component.pins.length, 0) > CIRCUIT_INPUT_LIMITS.pins ||
        circuit.nets.reduce((total, net) => total + net.pins.length + (net.labels?.length ?? 0), 0) > CIRCUIT_INPUT_LIMITS.wires * 2) {
      throw new Error('Circuit exceeds layout size limits.');
    }
    const previous = 'validation' in circuit ? circuit.validation as CircuitValidationResult : undefined;
    if (previous && (!previous.valid || previous.errors.length > 0)) {
      throw new Error(`Cannot lay out an invalid circuit: ${previous.errors.join('; ')}`);
    }
    const validation = CircuitValidator.validate(circuit);
    if (!validation.valid) throw new Error(`Cannot lay out an invalid circuit: ${validation.errors.join('; ')}`);
    if (circuit.components.some(component => !Number.isFinite(component.rotation) ||
        !Number.isFinite(component.position.x) || !Number.isFinite(component.position.y) ||
        Math.abs(component.position.x) > CIRCUIT_INPUT_LIMITS.coordinate ||
        Math.abs(component.position.y) > CIRCUIT_INPUT_LIMITS.coordinate)) {
      throw new Error('Circuit contains invalid layout geometry.');
    }
    if (this.config.preserveUserPositions) {
      const placements = new Map<string, PlacementResult>(circuit.components.map(component => [component.id, {
        componentId: component.id,
        gridPosition: this.grid.toGrid(component.position),
        absolutePosition: { ...component.position },
        rotation: component.rotation,
        mirror: component.mirror ?? false,
      }]));
      return { placements, bounds: computeBounds(placements), gridBounds: computeGridBounds(placements) };
    }
    const analysis = LayoutAnalyzer.analyze(circuit);
    const hints = PlacementStrategy.generateHints(circuit, analysis);
    let gridPlacements = PlacementStrategy.computePlacements(
      circuit,
      analysis,
      hints,
    );

    if (this.config.enableOptimization) {
      gridPlacements = this.optimizer.optimize(gridPlacements, circuit);
    }

    const orientations = OrientationStrategy.assignOrientations(
      circuit.components,
      gridPlacements,
      analysis,
    );

    const placements = new Map<string, PlacementResult>();

    gridPlacements.forEach((gridPosition, componentId) => {
      const absolutePosition = this.grid.toAbsolute(gridPosition);
      const orientation = orientations.get(componentId) ?? {
        rotation: 0,
        mirror: false,
      };

      placements.set(componentId, {
        componentId,
        gridPosition,
        absolutePosition,
        rotation: orientation.rotation,
        mirror: orientation.mirror,
      });
    });

    const bounds = computeBounds(placements);
    const gridBounds = computeGridBounds(placements);

    return {
      placements,
      bounds,
      gridBounds,
    };
  }

  static layout(circuit: Circuit, config?: LayoutConfig): Circuit {
    const engine = new LayoutEngine(config);
    return engine.layout(circuit);
  }
}
