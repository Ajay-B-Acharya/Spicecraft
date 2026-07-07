/**
 * Intelligent auto-layout engine.
 *
 * Orchestrates component placement using topology analysis, rule-based placement
 * strategy, grid snapping, and position optimization. The engine operates
 * exclusively on Circuit objects without React Flow or exporter dependencies so
 * future export targets (LTspice, KiCad, SVG, PDF) can reuse the same placement
 * logic.
 */
import { Circuit } from '../models/Circuit';
import { Component } from '../models/Component';
import { Grid } from './Grid';
import { LayoutAnalyzer } from './LayoutAnalyzer';
import { PlacementStrategy } from './PlacementStrategy';
import { PositionOptimizer } from './PositionOptimizer';
import {
  DEFAULT_LAYOUT_CONFIG,
  GridPosition,
  LayoutConfig,
  LayoutResult,
  PlacementResult,
} from './LayoutTypes';

function computeBounds(placements: Map<string, PlacementResult>): LayoutResult['bounds'] {
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

function computeGridBounds(placements: Map<string, PlacementResult>): LayoutResult['gridBounds'] {
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

function applyLayoutToCircuit(circuit: Circuit, layoutResult: LayoutResult): Circuit {
  const updatedComponents = circuit.components.map((component) => {
    const placement = layoutResult.placements.get(component.id);

    if (!placement) {
      return component;
    }

    return {
      ...component,
      position: placement.absolutePosition,
    };
  });

  return {
    ...circuit,
    components: updatedComponents,
  };
}

export class LayoutEngine {
  private readonly config: LayoutConfig;
  private readonly grid: Grid;
  private readonly optimizer: PositionOptimizer;

  constructor(config: LayoutConfig = DEFAULT_LAYOUT_CONFIG) {
    this.config = config;
    this.grid = new Grid(config.grid);
    this.optimizer = new PositionOptimizer();
  }

  layout(circuit: Circuit): Circuit {
    const layoutResult = this.computeLayout(circuit);
    return applyLayoutToCircuit(circuit, layoutResult);
  }

  computeLayout(circuit: Circuit): LayoutResult {
    const analysis = LayoutAnalyzer.analyze(circuit);
    const hints = PlacementStrategy.generateHints(circuit, analysis);
    let gridPlacements = PlacementStrategy.computePlacements(circuit, analysis, hints);

    if (this.config.enableOptimization) {
      gridPlacements = this.optimizer.optimize(gridPlacements, circuit);
    }

    const placements = new Map<string, PlacementResult>();

    gridPlacements.forEach((gridPosition, componentId) => {
      const absolutePosition = this.grid.toAbsolute(gridPosition);

      placements.set(componentId, {
        componentId,
        gridPosition,
        absolutePosition,
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
