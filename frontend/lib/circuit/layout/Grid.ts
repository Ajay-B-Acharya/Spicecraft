/**
 * Grid coordinate system.
 *
 * Provides deterministic grid-based positioning that snaps components to clean
 * schematic coordinates. Every layout operation uses this grid so future
 * exporters produce aligned, professional-looking schematics.
 */
import { GridConfig, GridPosition } from './LayoutTypes';

export class Grid {
  constructor(private readonly config: GridConfig) {}

  toAbsolute(gridPosition: GridPosition): { x: number; y: number } {
    const originX = this.config.originX ?? 0;
    const originY = this.config.originY ?? 0;

    return {
      x: originX + this.config.marginX + gridPosition.col * this.config.spacingX,
      y: originY + this.config.marginY + gridPosition.row * this.config.spacingY,
    };
  }

  toGrid(absolutePosition: { x: number; y: number }): GridPosition {
    const originX = this.config.originX ?? 0;
    const originY = this.config.originY ?? 0;
    const col = Math.round((absolutePosition.x - originX - this.config.marginX) / this.config.spacingX);
    const row = Math.round((absolutePosition.y - originY - this.config.marginY) / this.config.spacingY);

    return { col, row };
  }

  snap(absolutePosition: { x: number; y: number }): { x: number; y: number } {
    return this.toAbsolute(this.toGrid(absolutePosition));
  }

  distance(left: GridPosition, right: GridPosition): number {
    const dx = right.col - left.col;
    const dy = right.row - right.row;

    return Math.sqrt(dx * dx + dy * dy);
  }

  manhattanDistance(left: GridPosition, right: GridPosition): number {
    return Math.abs(right.col - left.col) + Math.abs(right.row - left.row);
  }

  isOccupied(position: GridPosition, occupied: Set<string>): boolean {
    return occupied.has(this.key(position));
  }

  key(position: GridPosition): string {
    return `${position.col},${position.row}`;
  }

  parse(key: string): GridPosition {
    const [col, row] = key.split(',').map(Number);
    return { col, row };
  }
}
