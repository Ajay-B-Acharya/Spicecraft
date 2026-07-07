/**
 * Component placement strategy.
 *
 * Produces grid positions for components using topology-driven rules that follow
 * EDA conventions: supplies at the top, ground at the bottom, signal flow from
 * left to right, active devices in the center. The strategy is rule-based so it
 * adapts to arbitrary AI-generated circuits without hardcoded templates.
 */
import { Circuit } from '../models/Circuit';
import { Component } from '../models/Component';
import { CircuitAnalysis } from './LayoutTypes';
import { GridPosition, PlacementHint } from './LayoutTypes';

interface PlacementSlot {
  component: Component;
  gridPosition: GridPosition;
  hint: PlacementHint;
}

function isTransistor(component: Component): boolean {
  return component.type === 'npn_transistor' || component.type === 'pnp_transistor';
}

function getConnectedComponents(
  component: Component,
  circuit: Circuit,
  analysis: CircuitAnalysis,
): string[] {
  const componentAnalysis = analysis.componentAnalyses.get(component.id);

  if (!componentAnalysis) {
    return [];
  }

  const connectedNets = new Set(componentAnalysis.connectedNets);
  const connected: string[] = [];

  circuit.components.forEach((other) => {
    if (other.id === component.id) {
      return;
    }

    const otherAnalysis = analysis.componentAnalyses.get(other.id);

    if (!otherAnalysis) {
      return;
    }

    const hasSharedNet = otherAnalysis.connectedNets.some((net) => connectedNets.has(net));

    if (hasSharedNet) {
      connected.push(other.id);
    }
  });

  return connected;
}

export class PlacementStrategy {
  static generateHints(circuit: Circuit, analysis: CircuitAnalysis): PlacementHint[] {
    const hints: PlacementHint[] = [];
    const { classification } = analysis;
    let baseCol = 0;

    classification.supplies.forEach((componentId, index) => {
      hints.push({
        componentId,
        preferredCol: baseCol + index * 2,
        preferredRow: 0,
        anchor: 'top',
        weight: 100,
      });
    });

    classification.grounds.forEach((componentId, index) => {
      hints.push({
        componentId,
        preferredCol: baseCol + index * 2,
        preferredRow: 6,
        anchor: 'bottom',
        weight: 100,
      });
    });

    classification.inputs.forEach((componentId, index) => {
      hints.push({
        componentId,
        preferredCol: 0,
        preferredRow: 2 + index,
        anchor: 'left',
        weight: 90,
      });
    });

    classification.outputs.forEach((componentId, index) => {
      hints.push({
        componentId,
        preferredCol: 8,
        preferredRow: 2 + index,
        anchor: 'right',
        weight: 90,
      });
    });

    const activeComponents = circuit.components.filter((component) =>
      classification.active.includes(component.id),
    );

    activeComponents.forEach((component, index) => {
      const col = 3 + index * 2;
      const row = 3;

      hints.push({
        componentId: component.id,
        preferredCol: col,
        preferredRow: row,
        anchor: 'center',
        weight: 80,
      });

      if (isTransistor(component)) {
        const connected = getConnectedComponents(component, circuit, analysis);

        connected.forEach((connectedId) => {
          const connectedComponent = circuit.components.find((c) => c.id === connectedId);

          if (!connectedComponent) {
            return;
          }

          const connectedAnalysis = analysis.componentAnalyses.get(connectedId);

          if (!connectedAnalysis) {
            return;
          }

          if (connectedComponent.type === 'resistor') {
            const sharedNets = connectedAnalysis.connectedNets.filter((net) =>
              analysis.componentAnalyses.get(component.id)?.connectedNets.includes(net),
            );

            const hasBase = component.pins.some((pin) => pin.id === 'base' && sharedNets.includes(pin.net ?? ''));
            const hasCollector = component.pins.some(
              (pin) => pin.id === 'collector' && sharedNets.includes(pin.net ?? ''),
            );
            const hasEmitter = component.pins.some(
              (pin) => pin.id === 'emitter' && sharedNets.includes(pin.net ?? ''),
            );

            if (hasBase) {
              hints.push({
                componentId: connectedId,
                preferredCol: col - 1,
                preferredRow: row,
                weight: 60,
              });
            }

            if (hasCollector) {
              hints.push({
                componentId: connectedId,
                preferredCol: col,
                preferredRow: row - 1,
                weight: 60,
              });
            }

            if (hasEmitter) {
              hints.push({
                componentId: connectedId,
                preferredCol: col,
                preferredRow: row + 1,
                weight: 60,
              });
            }
          }
        });
      }
    });

    classification.coupling.forEach((componentId) => {
      const component = circuit.components.find((c) => c.id === componentId);

      if (!component) {
        return;
      }

      const connected = getConnectedComponents(component, circuit, analysis);
      const inputConnected = connected.some((id) => classification.inputs.includes(id));
      const outputConnected = connected.some((id) => classification.outputs.includes(id));

      if (inputConnected) {
        hints.push({
          componentId,
          preferredCol: 1,
          preferredRow: 2,
          weight: 50,
        });
      } else if (outputConnected) {
        hints.push({
          componentId,
          preferredCol: 7,
          preferredRow: 2,
          weight: 50,
        });
      }
    });

    classification.decoupling.forEach((componentId, index) => {
      hints.push({
        componentId,
        preferredCol: 1 + index,
        preferredRow: 1,
        weight: 40,
      });
    });

    return hints;
  }

  static computePlacements(
    circuit: Circuit,
    analysis: CircuitAnalysis,
    hints: PlacementHint[],
  ): Map<string, GridPosition> {
    const placements = new Map<string, GridPosition>();
    const occupied = new Set<string>();
    const hintsByComponent = new Map<string, PlacementHint>();

    hints.forEach((hint) => {
      hintsByComponent.set(hint.componentId, hint);
    });

    const sortedHints = [...hints].sort((left, right) => right.weight - left.weight);

    sortedHints.forEach((hint) => {
      let position: GridPosition = {
        col: hint.preferredCol ?? 0,
        row: hint.preferredRow ?? 0,
      };

      const key = (pos: GridPosition) => `${pos.col},${pos.row}`;
      let attempts = 0;
      const maxAttempts = 100;

      while (occupied.has(key(position)) && attempts < maxAttempts) {
        position = {
          col: position.col + 1,
          row: position.row,
        };
        attempts++;
      }

      if (attempts >= maxAttempts) {
        position = {
          col: placements.size % 5,
          row: Math.floor(placements.size / 5) + 1,
        };
      }

      placements.set(hint.componentId, position);
      occupied.add(key(position));
    });

    circuit.components.forEach((component) => {
      if (!placements.has(component.id)) {
        let position: GridPosition = {
          col: placements.size % 5,
          row: Math.floor(placements.size / 5) + 1,
        };

        const key = (pos: GridPosition) => `${pos.col},${pos.row}`;
        let attempts = 0;
        const maxAttempts = 100;

        while (occupied.has(key(position)) && attempts < maxAttempts) {
          position = {
            col: position.col + 1,
            row: position.row,
          };
          attempts++;
        }

        placements.set(component.id, position);
        occupied.add(key(position));
      }
    });

    return placements;
  }
}
