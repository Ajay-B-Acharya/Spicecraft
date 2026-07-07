/**
 * Circuit topology analyzer.
 *
 * Classifies components by electrical role (input, output, supply, ground,
 * active, passive) using net connectivity patterns and component types. This
 * topology data guides the placement strategy so the layout engine produces
 * EDA-compliant schematics without hardcoded circuit templates.
 */
import { Circuit } from '../models/Circuit';
import { Component } from '../models/Component';
import { Net } from '../models/Net';
import { CircuitAnalysis, ComponentAnalysis, ComponentClassification } from './LayoutTypes';

const SUPPLY_LABELS = new Set(['VCC', 'VDD', 'VEE', 'VSS', 'V+', 'V-', 'SUPPLY', 'POWER']);
const GROUND_LABELS = new Set(['GND', 'GROUND', 'VSS', '0']);
const INPUT_LABELS = new Set(['VIN', 'INPUT', 'IN', 'SIG', 'SIGNAL']);
const OUTPUT_LABELS = new Set(['VOUT', 'OUTPUT', 'OUT']);

const ACTIVE_TYPES = new Set([
  'npn_transistor',
  'pnp_transistor',
  'voltage_source',
  'current_source',
]);

const PASSIVE_TYPES = new Set(['resistor', 'capacitor', 'inductor', 'diode']);

function normalizeLabel(label: string): string {
  return label.trim().toUpperCase().replace(/[^A-Z0-9]/g, '');
}

function isLabelMatch(label: string, referenceSet: Set<string>): boolean {
  const normalized = normalizeLabel(label);
  return referenceSet.has(normalized);
}

function classifyNetByLabel(net: Net): {
  isSupply: boolean;
  isGround: boolean;
  isInput: boolean;
  isOutput: boolean;
} {
  const labels = [net.name, ...(net.labels ?? [])].filter((label): label is string => typeof label === 'string');

  return {
    isSupply: labels.some((label) => isLabelMatch(label, SUPPLY_LABELS)),
    isGround: labels.some((label) => isLabelMatch(label, GROUND_LABELS)),
    isInput: labels.some((label) => isLabelMatch(label, INPUT_LABELS)),
    isOutput: labels.some((label) => isLabelMatch(label, OUTPUT_LABELS)),
  };
}

function isCouplingCapacitor(component: Component, circuit: Circuit): boolean {
  if (component.type !== 'capacitor') {
    return false;
  }

  const connectedNets = component.pins.map((pin) => pin.net).filter((net): net is string => typeof net === 'string');

  if (connectedNets.length !== 2) {
    return false;
  }

  const nets = circuit.nets.filter((net) => connectedNets.includes(net.name ?? net.id));
  return nets.some((net) => {
    const classification = classifyNetByLabel(net);
    return classification.isInput || classification.isOutput;
  });
}

function isDecouplingCapacitor(component: Component, circuit: Circuit): boolean {
  if (component.type !== 'capacitor') {
    return false;
  }

  const connectedNets = component.pins.map((pin) => pin.net).filter((net): net is string => typeof net === 'string');

  if (connectedNets.length !== 2) {
    return false;
  }

  const nets = circuit.nets.filter((net) => connectedNets.includes(net.name ?? net.id));
  const hasSupply = nets.some((net) => classifyNetByLabel(net).isSupply);
  const hasGround = nets.some((net) => classifyNetByLabel(net).isGround);

  return hasSupply && hasGround;
}

function analyzeComponent(component: Component, circuit: Circuit): ComponentAnalysis {
  const connectedNets = component.pins.map((pin) => pin.net).filter((net): net is string => typeof net === 'string');
  const uniqueNets = Array.from(new Set(connectedNets));
  const degree = uniqueNets.length;
  const nets = circuit.nets.filter((net) => uniqueNets.includes(net.name ?? net.id));
  const isSupply = nets.some((net) => classifyNetByLabel(net).isSupply);
  const isGround = nets.some((net) => classifyNetByLabel(net).isGround);
  const isInput = nets.some((net) => classifyNetByLabel(net).isInput);
  const isOutput = nets.some((net) => classifyNetByLabel(net).isOutput);
  const isActive = ACTIVE_TYPES.has(component.type);
  const isPassive = PASSIVE_TYPES.has(component.type);
  const isCoupling = isCouplingCapacitor(component, circuit);
  const isDecoupling = isDecouplingCapacitor(component, circuit);

  return {
    componentId: component.id,
    degree,
    connectedNets: uniqueNets,
    isInput,
    isOutput,
    isGround,
    isSupply,
    isActive,
    isPassive,
    isCoupling,
    isDecoupling,
  };
}

export class LayoutAnalyzer {
  static analyze(circuit: Circuit): CircuitAnalysis {
    const componentAnalyses = new Map<string, ComponentAnalysis>();
    const classification: ComponentClassification = {
      inputs: [],
      outputs: [],
      grounds: [],
      supplies: [],
      active: [],
      passive: [],
      coupling: [],
      decoupling: [],
    };

    circuit.components.forEach((component) => {
      const analysis = analyzeComponent(component, circuit);
      componentAnalyses.set(component.id, analysis);

      if (analysis.isInput) {
        classification.inputs.push(component.id);
      }

      if (analysis.isOutput) {
        classification.outputs.push(component.id);
      }

      if (analysis.isGround) {
        classification.grounds.push(component.id);
      }

      if (analysis.isSupply) {
        classification.supplies.push(component.id);
      }

      if (analysis.isActive) {
        classification.active.push(component.id);
      }

      if (analysis.isPassive && !analysis.isCoupling && !analysis.isDecoupling) {
        classification.passive.push(component.id);
      }

      if (analysis.isCoupling) {
        classification.coupling.push(component.id);
      }

      if (analysis.isDecoupling) {
        classification.decoupling.push(component.id);
      }
    });

    const netDegrees = new Map<string, number>();
    circuit.nets.forEach((net) => {
      netDegrees.set(net.name ?? net.id, net.pins.length);
    });

    const signalFlow = new Map<string, number>();
    circuit.components.forEach((component, index) => {
      signalFlow.set(component.id, index);
    });

    return {
      classification,
      componentAnalyses,
      netDegrees,
      signalFlow,
    };
  }
}
