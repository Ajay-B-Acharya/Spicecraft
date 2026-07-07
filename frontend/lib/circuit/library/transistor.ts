/**
 * Bipolar junction transistor component definitions.
 *
 * Defines separate NPN and PNP entries with explicit collector/base/emitter pin
 * names. Pin IDs match their semantic names so future netlist and ERC modules
 * can reason about transistor terminals without brittle handle mapping.
 */
import { ComponentDefinition } from '../types';

const transistorPins: ComponentDefinition['pins'] = [
  {
    id: 'collector',
    name: 'collector',
    x: 0,
    y: -32,
    direction: 'top',
  },
  {
    id: 'base',
    name: 'base',
    x: -32,
    y: 0,
    direction: 'left',
  },
  {
    id: 'emitter',
    name: 'emitter',
    x: 0,
    y: 32,
    direction: 'bottom',
  },
];

export const npnTransistor: ComponentDefinition = {
  type: 'npn_transistor',
  symbol: 'npn',
  prefix: 'Q',
  defaultValue: '2N3904',
  defaultRotation: 0,
  pins: transistorPins,
};

export const pnpTransistor: ComponentDefinition = {
  type: 'pnp_transistor',
  symbol: 'pnp',
  prefix: 'Q',
  defaultValue: '2N3906',
  defaultRotation: 0,
  pins: transistorPins,
};

export default [npnTransistor, pnpTransistor];
