/**
 * Diode component definition.
 *
 * Uses proper anode/cathode pin names while preserving simple numeric pin IDs
 * for compatibility with common schematic handle conventions.
 */
import { ComponentDefinition } from '../types';

const diode: ComponentDefinition = {
  type: 'diode',
  symbol: 'diode',
  prefix: 'D',
  defaultValue: '1N4148',
  defaultRotation: 0,
  pins: [
    {
      id: '1',
      name: 'anode',
      x: -32,
      y: 0,
      direction: 'left',
    },
    {
      id: '2',
      name: 'cathode',
      x: 32,
      y: 0,
      direction: 'right',
    },
  ],
};

export default diode;
