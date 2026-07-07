/**
 * Position optimizer.
 *
 * Post-placement refinement that prevents overlaps, aligns rows and columns,
 * reduces whitespace, and maintains EDA readability conventions. The optimizer
 * operates on grid coordinates so output remains snapped to the schematic grid.
 */
import { Circuit } from '../models/Circuit';
import { GridPosition } from './LayoutTypes';

interface OptimizationPass {
  name: string;
  apply(placements: Map<string, GridPosition>, circuit: Circuit): Map<string, GridPosition>;
}

class RemoveOverlapsPass implements OptimizationPass {
  name = 'remove-overlaps';

  apply(placements: Map<string, GridPosition>, circuit: Circuit): Map<string, GridPosition> {
    const optimized = new Map(placements);
    const occupied = new Set<string>();
    const key = (pos: GridPosition) => `${pos.col},${pos.row}`;

    const sortedComponents = circuit.components
      .map((component) => ({
        component,
        position: optimized.get(component.id)!,
      }))
      .sort((left, right) => {
        if (left.position.row !== right.position.row) {
          return left.position.row - right.position.row;
        }

        return left.position.col - right.position.col;
      });

    sortedComponents.forEach(({ component, position }) => {
      let currentPosition = position;
      let attempts = 0;
      const maxAttempts = 100;

      while (occupied.has(key(currentPosition)) && attempts < maxAttempts) {
        currentPosition = {
          col: currentPosition.col + 1,
          row: currentPosition.row,
        };
        attempts++;
      }

      optimized.set(component.id, currentPosition);
      occupied.add(key(currentPosition));
    });

    return optimized;
  }
}

class CompactColumnsPass implements OptimizationPass {
  name = 'compact-columns';

  apply(placements: Map<string, GridPosition>, circuit: Circuit): Map<string, GridPosition> {
    const componentsByCol = new Map<number, string[]>();

    placements.forEach((position, componentId) => {
      const components = componentsByCol.get(position.col) ?? [];
      components.push(componentId);
      componentsByCol.set(position.col, components);
    });

    const usedCols = Array.from(componentsByCol.keys()).sort((a, b) => a - b);
    const colMapping = new Map<number, number>();

    usedCols.forEach((col, index) => {
      colMapping.set(col, index);
    });

    const optimized = new Map<string, GridPosition>();

    placements.forEach((position, componentId) => {
      const newCol = colMapping.get(position.col) ?? position.col;
      optimized.set(componentId, {
        col: newCol,
        row: position.row,
      });
    });

    return optimized;
  }
}

class CompactRowsPass implements OptimizationPass {
  name = 'compact-rows';

  apply(placements: Map<string, GridPosition>, circuit: Circuit): Map<string, GridPosition> {
    const componentsByRow = new Map<number, string[]>();

    placements.forEach((position, componentId) => {
      const components = componentsByRow.get(position.row) ?? [];
      components.push(componentId);
      componentsByRow.set(position.row, components);
    });

    const usedRows = Array.from(componentsByRow.keys()).sort((a, b) => a - b);
    const rowMapping = new Map<number, number>();

    usedRows.forEach((row, index) => {
      rowMapping.set(row, index);
    });

    const optimized = new Map<string, GridPosition>();

    placements.forEach((position, componentId) => {
      const newRow = rowMapping.get(position.row) ?? position.row;
      optimized.set(componentId, {
        col: position.col,
        row: newRow,
      });
    });

    return optimized;
  }
}

class AlignRowsPass implements OptimizationPass {
  name = 'align-rows';

  apply(placements: Map<string, GridPosition>, circuit: Circuit): Map<string, GridPosition> {
    const componentsByRow = new Map<number, string[]>();

    placements.forEach((position, componentId) => {
      const components = componentsByRow.get(position.row) ?? [];
      components.push(componentId);
      componentsByRow.set(position.row, components);
    });

    const optimized = new Map(placements);

    componentsByRow.forEach((componentIds, row) => {
      if (componentIds.length <= 1) {
        return;
      }

      const cols = componentIds.map((id) => placements.get(id)!.col).sort((a, b) => a - b);
      const sortedIds = [...componentIds].sort((a, b) => {
        const posA = placements.get(a)!;
        const posB = placements.get(b)!;
        return posA.col - posB.col;
      });

      sortedIds.forEach((componentId, index) => {
        optimized.set(componentId, {
          col: cols[index],
          row,
        });
      });
    });

    return optimized;
  }
}

export class PositionOptimizer {
  private readonly passes: OptimizationPass[] = [
    new RemoveOverlapsPass(),
    new AlignRowsPass(),
    new CompactColumnsPass(),
    new CompactRowsPass(),
  ];

  optimize(placements: Map<string, GridPosition>, circuit: Circuit): Map<string, GridPosition> {
    let optimized = new Map(placements);

    this.passes.forEach((pass) => {
      optimized = pass.apply(optimized, circuit);
    });

    return optimized;
  }
}
