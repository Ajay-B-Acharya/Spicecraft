/**
 * Layout debug formatter.
 *
 * Produces human-readable text output showing component positions, grid
 * placements, and bounds for inspection before export. This helps debug layout
 * strategy issues and verify that the placement engine is working correctly.
 */
import { Circuit } from '../models/Circuit';
import { LayoutResult } from './LayoutTypes';

export class LayoutDebugger {
  static format(circuit: Circuit, layoutResult: LayoutResult): string {
    const lines: string[] = ['Component Positions', '-------------------', ''];

    const sortedPlacements = Array.from(layoutResult.placements.entries()).sort((left, right) => {
      const leftPos = left[1].gridPosition;
      const rightPos = right[1].gridPosition;

      if (leftPos.row !== rightPos.row) {
        return leftPos.row - rightPos.row;
      }

      return leftPos.col - rightPos.col;
    });

    sortedPlacements.forEach(([componentId, placement]) => {
      const component = circuit.components.find((c) => c.id === componentId);
      const label = component?.name ?? componentId;
      const absX = placement.absolutePosition.x;
      const absY = placement.absolutePosition.y;
      const gridCol = placement.gridPosition.col;
      const gridRow = placement.gridPosition.row;

      lines.push(`${label}`);
      lines.push(`  Grid: (${gridCol}, ${gridRow})`);
      lines.push(`  Absolute: (${absX}, ${absY})`);
      lines.push('');
    });

    lines.push('------------------------', '');
    lines.push('Layout Bounds', '');
    lines.push(`  Grid: ${layoutResult.gridBounds.cols} cols × ${layoutResult.gridBounds.rows} rows`);
    lines.push(
      `  Absolute: ${layoutResult.bounds.width} × ${layoutResult.bounds.height} (${layoutResult.bounds.minX}, ${layoutResult.bounds.minY}) to (${layoutResult.bounds.maxX}, ${layoutResult.bounds.maxY})`,
    );
    lines.push('');

    return lines.join('\n').trimEnd();
  }

  static print(circuit: Circuit, layoutResult: LayoutResult): string {
    const output = LayoutDebugger.format(circuit, layoutResult);
    console.log(output);
    return output;
  }

  static formatGrid(circuit: Circuit, layoutResult: LayoutResult): string {
    const { gridBounds } = layoutResult;
    const grid: string[][] = [];

    for (let row = gridBounds.minRow; row <= gridBounds.maxRow; row++) {
      const gridRow: string[] = [];

      for (let col = gridBounds.minCol; col <= gridBounds.maxCol; col++) {
        gridRow.push('.');
      }

      grid.push(gridRow);
    }

    layoutResult.placements.forEach((placement, componentId) => {
      const component = circuit.components.find((c) => c.id === componentId);
      const label = component?.id ?? componentId;
      const row = placement.gridPosition.row - gridBounds.minRow;
      const col = placement.gridPosition.col - gridBounds.minCol;

      if (row >= 0 && row < grid.length && col >= 0 && col < grid[row].length) {
        grid[row][col] = label.substring(0, 4).padEnd(4);
      }
    });

    const lines: string[] = ['Grid Layout', '-----------', ''];

    grid.forEach((row, rowIndex) => {
      lines.push(row.join(' '));
    });

    lines.push('');

    return lines.join('\n');
  }

  static printGrid(circuit: Circuit, layoutResult: LayoutResult): string {
    const output = LayoutDebugger.formatGrid(circuit, layoutResult);
    console.log(output);
    return output;
  }
}
