/**
 * Independent voltage and current source definitions.
 *
 * Source components use explicit polarity pin names so exporters and simulators
 * can preserve electrical intent without relying on visual orientation.
 */
import { ComponentDefinition } from '../types';

export const voltageSource: ComponentDefinition = {
  type: 'voltage_source',
  symbol: 'voltage',
  prefix: 'V',
  defaultValue: '5',
  defaultRotation: 0,
  pins: [
    {
      id: '+',
      name: 'positive',
      x: 0,
      y: -32,
      direction: 'top',
    },
    {
      id: '-',
      name: 'negative',
      x: 0,
      y: 32,
      direction: 'bottom',
    },
  ],
};

export const currentSource: ComponentDefinition = {
  type: 'current_source',
  symbol: 'current',
  prefix: 'I',
  defaultValue: '1m',
  defaultRotation: 0,
  pins: [
    {
      id: '+',
      name: 'positive',
      x: 0,
      y: -32,
      direction: 'top',
    },
    {
      id: '-',
      name: 'negative',
      x: 0,
      y: 32,
      direction: 'bottom',
    },
  ],
};

export default [voltageSource, currentSource];
