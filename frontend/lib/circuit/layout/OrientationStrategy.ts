/**
 * Component orientation strategy.
 *
 * Determines appropriate rotation and mirroring for components based on their
 * placement, electrical role, and schematic conventions. Sources should face
 * downward, signal flow should be horizontal, and transistors should be oriented
 * consistently.
 */
import { Component } from '../models/Component';
import { CircuitAnalysis, GridPosition } from './LayoutTypes';

export interface ComponentOrientation {
  rotation: number;
  mirror: boolean;
}

function isVerticalPlacement(position: GridPosition, neighborPositions: GridPosition[]): boolean {
  if (neighborPositions.length === 0) {
    return false;
  }

  const verticalNeighbors = neighborPositions.filter(
    (neighbor) => neighbor.col === position.col && neighbor.row !== position.row,
  );
  const horizontalNeighbors = neighborPositions.filter(
    (neighbor) => neighbor.row === position.row && neighbor.col !== position.col,
  );

  return verticalNeighbors.length > horizontalNeighbors.length;
}

function getNeighborDirection(position: GridPosition, neighborPositions: GridPosition[]): 'left' | 'right' | 'up' | 'down' | 'mixed' {
  if (neighborPositions.length === 0) {
    return 'right';
  }

  const left = neighborPositions.filter((neighbor) => neighbor.col < position.col && neighbor.row === position.row).length;
  const right = neighborPositions.filter((neighbor) => neighbor.col > position.col && neighbor.row === position.row).length;
  const up = neighborPositions.filter((neighbor) => neighbor.row < position.row && neighbor.col === position.col).length;
  const down = neighborPositions.filter((neighbor) => neighbor.row > position.row && neighbor.col === position.col).length;

  const max = Math.max(left, right, up, down);

  if (max === 0) {
    return 'mixed';
  }

  if (left === max) {
    return 'left';
  }

  if (right === max) {
    return 'right';
  }

  if (up === max) {
    return 'up';
  }

  return 'down';
}

export class OrientationStrategy {
  static determineOrientation(
    component: Component,
    position: GridPosition,
    neighborPositions: GridPosition[],
    analysis: CircuitAnalysis,
  ): ComponentOrientation {
    const componentAnalysis = analysis.componentAnalyses.get(component.id);

    if (!componentAnalysis) {
      return { rotation: 0, mirror: false };
    }

    if (component.type === 'voltage_source' || component.type === 'current_source') {
      return { rotation: 90, mirror: false };
    }

    if (component.type === 'ground') {
      return { rotation: 0, mirror: false };
    }

    if (component.type === 'resistor' || component.type === 'capacitor' || component.type === 'inductor' || component.type === 'diode') {
      const isVertical = isVerticalPlacement(position, neighborPositions);
      return { rotation: isVertical ? 90 : 0, mirror: false };
    }

    if (component.type === 'npn_transistor' || component.type === 'pnp_transistor') {
      const direction = getNeighborDirection(position, neighborPositions);

      if (direction === 'left') {
        return { rotation: 0, mirror: true };
      }

      return { rotation: 0, mirror: false };
    }

    return { rotation: 0, mirror: false };
  }

  static assignOrientations(
    components: Component[],
    placements: Map<string, GridPosition>,
    analysis: CircuitAnalysis,
  ): Map<string, ComponentOrientation> {
    const orientations = new Map<string, ComponentOrientation>();
    const componentsById = new Map(components.map((comp) => [comp.id, comp]));
    const connectionsByComponent = new Map<string, Set<string>>();

    components.forEach((component) => {
      const connectedComponents = new Set<string>();

      component.pins.forEach((pin) => {
        if (!pin.net) {
          return;
        }

        components.forEach((other) => {
          if (other.id === component.id) {
            return;
          }

          const otherConnected = other.pins.some((otherPin) => otherPin.net === pin.net);

          if (otherConnected) {
            connectedComponents.add(other.id);
          }
        });
      });

      connectionsByComponent.set(component.id, connectedComponents);
    });

    components.forEach((component) => {
      const position = placements.get(component.id);

      if (!position) {
        orientations.set(component.id, { rotation: 0, mirror: false });
        return;
      }

      const connected = connectionsByComponent.get(component.id) ?? new Set();
      const neighborPositions = Array.from(connected)
        .map((id) => placements.get(id))
        .filter((pos): pos is GridPosition => pos !== undefined);

      const orientation = OrientationStrategy.determineOrientation(
        component,
        position,
        neighborPositions,
        analysis,
      );

      orientations.set(component.id, orientation);
    });

    return orientations;
  }
}
