/**
 * Component grouping recognition.
 *
 * Detects common circuit patterns like voltage dividers, RC filters, bias
 * networks, and amplifier stages. Grouped components should be placed near each
 * other to improve schematic readability.
 */
import { Circuit } from '../models/Circuit';
import { Component } from '../models/Component';
import { CircuitAnalysis, ComponentGroup } from './LayoutTypes';

function getSharedNets(compA: Component, compB: Component): string[] {
  const netsA = new Set(compA.pins.map((pin) => pin.net).filter((net): net is string => typeof net === 'string'));
  const netsB = compB.pins.map((pin) => pin.net).filter((net): net is string => typeof net === 'string');

  return netsB.filter((net) => netsA.has(net));
}

function isVoltageDivider(components: Component[], circuit: Circuit): ComponentGroup | null {
  if (components.length !== 2) {
    return null;
  }

  const [comp1, comp2] = components;

  if (comp1.type !== 'resistor' || comp2.type !== 'resistor') {
    return null;
  }

  const sharedNets = getSharedNets(comp1, comp2);

  if (sharedNets.length !== 1) {
    return null;
  }

  const allNets = new Set([
    ...comp1.pins.map((pin) => pin.net),
    ...comp2.pins.map((pin) => pin.net),
  ].filter((net): net is string => typeof net === 'string'));

  if (allNets.size !== 3) {
    return null;
  }

  return {
    type: 'voltage_divider',
    components: [comp1.id, comp2.id],
  };
}

function isRCFilter(components: Component[], circuit: Circuit): ComponentGroup | null {
  if (components.length !== 2) {
    return null;
  }

  const [comp1, comp2] = components;
  const hasResistor = comp1.type === 'resistor' || comp2.type === 'resistor';
  const hasCapacitor = comp1.type === 'capacitor' || comp2.type === 'capacitor';

  if (!hasResistor || !hasCapacitor) {
    return null;
  }

  const sharedNets = getSharedNets(comp1, comp2);

  if (sharedNets.length !== 1) {
    return null;
  }

  const resistor = comp1.type === 'resistor' ? comp1 : comp2;
  const capacitor = comp1.type === 'capacitor' ? comp1 : comp2;
  const resistorNets = resistor.pins.map((pin) => pin.net).filter((net): net is string => typeof net === 'string');
  const capacitorNets = capacitor.pins.map((pin) => pin.net).filter((net): net is string => typeof net === 'string');
  const sharedNet = sharedNets[0];
  const resistorOtherNet = resistorNets.find((net) => net !== sharedNet);
  const capacitorOtherNet = capacitorNets.find((net) => net !== sharedNet);

  if (!resistorOtherNet || !capacitorOtherNet) {
    return null;
  }

  const resistorOtherNetObj = circuit.nets.find((net) => (net.name ?? net.id) === resistorOtherNet);
  const capacitorOtherNetObj = circuit.nets.find((net) => (net.name ?? net.id) === capacitorOtherNet);

  if (!resistorOtherNetObj || !capacitorOtherNetObj) {
    return null;
  }

  const resistorIsInput = resistorOtherNetObj.pins.length > capacitorOtherNetObj.pins.length;

  return {
    type: 'rc_filter',
    components: [comp1.id, comp2.id],
    isHighPass: !resistorIsInput,
  };
}

function isBiasNetwork(components: Component[], circuit: Circuit, analysis: CircuitAnalysis): ComponentGroup | null {
  const resistors = components.filter((comp) => comp.type === 'resistor');

  if (resistors.length < 1 || resistors.length > 3) {
    return null;
  }

  const connectedTransistors = new Set<string>();

  resistors.forEach((resistor) => {
    const resistorNets = resistor.pins.map((pin) => pin.net).filter((net): net is string => typeof net === 'string');

    circuit.components.forEach((comp) => {
      if (comp.type === 'npn_transistor' || comp.type === 'pnp_transistor') {
        const basePin = comp.pins.find((pin) => pin.id === 'base');

        if (basePin && basePin.net && resistorNets.includes(basePin.net)) {
          connectedTransistors.add(comp.id);
        }
      }
    });
  });

  if (connectedTransistors.size === 1) {
    return {
      type: 'bias_network',
      components: resistors.map((r) => r.id),
      target: Array.from(connectedTransistors)[0],
    };
  }

  return null;
}

function isAmplifierStage(components: Component[], circuit: Circuit, analysis: CircuitAnalysis): ComponentGroup | null {
  const transistors = components.filter((comp) => comp.type === 'npn_transistor' || comp.type === 'pnp_transistor');

  if (transistors.length !== 1) {
    return null;
  }

  const transistor = transistors[0];
  const transistorNets = transistor.pins.map((pin) => pin.net).filter((net): net is string => typeof net === 'string');
  const relatedComponents = components.filter((comp) => {
    if (comp.id === transistor.id) {
      return false;
    }

    const compNets = comp.pins.map((pin) => pin.net).filter((net): net is string => typeof net === 'string');
    return compNets.some((net) => transistorNets.includes(net));
  });

  if (relatedComponents.length >= 2) {
    return {
      type: 'amplifier_stage',
      components: [transistor.id, ...relatedComponents.map((c) => c.id)],
      transistor: transistor.id,
    };
  }

  return null;
}

export class ComponentGrouping {
  static detectGroups(circuit: Circuit, analysis: CircuitAnalysis): ComponentGroup[] {
    const groups: ComponentGroup[] = [];
    const grouped = new Set<string>();
    const components = circuit.components;

    for (let i = 0; i < components.length; i++) {
      if (grouped.has(components[i].id)) {
        continue;
      }

      for (let j = i + 1; j < components.length; j++) {
        if (grouped.has(components[j].id)) {
          continue;
        }

        const pair = [components[i], components[j]];
        let group: ComponentGroup | null = null;

        group = isVoltageDivider(pair, circuit);

        if (!group) {
          group = isRCFilter(pair, circuit);
        }

        if (group) {
          groups.push(group);
          group.components.forEach((id) => grouped.add(id));
          break;
        }
      }
    }

    const remainingComponents = components.filter((comp) => !grouped.has(comp.id));

    for (let i = 0; i < remainingComponents.length; i++) {
      const candidateGroup: Component[] = [remainingComponents[i]];

      for (let j = i + 1; j < remainingComponents.length; j++) {
        if (grouped.has(remainingComponents[j].id)) {
          continue;
        }

        candidateGroup.push(remainingComponents[j]);
      }

      if (candidateGroup.length > 1) {
        let group: ComponentGroup | null = null;

        group = isBiasNetwork(candidateGroup, circuit, analysis);

        if (!group) {
          group = isAmplifierStage(candidateGroup, circuit, analysis);
        }

        if (group) {
          groups.push(group);
          group.components.forEach((id) => grouped.add(id));
        }
      }
    }

    return groups;
  }
}
