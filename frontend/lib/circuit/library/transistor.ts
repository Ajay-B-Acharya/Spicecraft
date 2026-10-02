/**
 * Bipolar junction transistor component definitions.
 *
 * Defines separate NPN and PNP entries with explicit collector/base/emitter pin
 * names. Pin IDs use uppercase single-letter conventions (C, B, E) to match
 * standard schematic notation and backend pin map definitions.
 *
 * Alias mapping in CircuitBuilder resolves alternate references ("collector",
 * "base", "emitter", "1", "2", "3") back to these canonical IDs.
 */
import { ComponentDefinition } from '../types';

const transistorPins: ComponentDefinition['pins'] = [
  {
    id: 'C',
    name: 'collector',
    x: 0,
    y: -32,
    direction: 'top',
  },
  {
    id: 'B',
    name: 'base',
    x: -32,
    y: 0,
    direction: 'left',
  },
  {
    id: 'E',
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
