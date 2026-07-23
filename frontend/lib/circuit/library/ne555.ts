/**
 * NE555 Timer IC component definition.
 *
 * The 555 timer is an 8-pin IC used for timing, pulse generation, and oscillator
 * circuits. Pin layout matches standard DIP package pinout.
 */
import { ComponentDefinition } from '../types';

const ne555: ComponentDefinition = {
  type: 'ne555',
  symbol: '555timer',
  prefix: 'U',
  defaultValue: 'NE555',
  defaultRotation: 0,
  pins: [
    {
      id: '1',
      name: 'GND',
      x: -48,
      y: 48,
      direction: 'left',
    },
    {
      id: '2',
      name: 'TRIG',
      x: -48,
      y: 16,
      direction: 'left',
    },
    {
      id: '3',
      name: 'OUT',
      x: 48,
      y: 16,
      direction: 'right',
    },
    {
      id: '4',
      name: 'RESET',
      x: -48,
      y: -48,
      direction: 'left',
    },
    {
      id: '5',
      name: 'CTRL',
      x: 48,
      y: -16,
      direction: 'right',
    },
    {
      id: '6',
      name: 'THR',
      x: -48,
      y: -16,
      direction: 'left',
    },
    {
      id: '7',
      name: 'DIS',
      x: 48,
      y: -48,
      direction: 'right',
    },
    {
      id: '8',
      name: 'VCC',
      x: 48,
      y: 48,
      direction: 'right',
    },
  ],
};

export default ne555;
