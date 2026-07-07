/**
 * Capacitor component definition.
 *
 * Provides UI-independent capacitor metadata for schematic, netlist, simulation,
 * and export modules.
 */
import { ComponentDefinition } from '../types';

const capacitor: ComponentDefinition = {
  type: 'capacitor',
  symbol: 'cap',
  prefix: 'C',
  defaultValue: '100n',
  defaultRotation: 0,
  pins: [
    {
      id: '1',
      name: 'left',
      x: -32,
      y: 0,
      direction: 'left',
    },
    {
      id: '2',
      name: 'right',
      x: 32,
      y: 0,
      direction: 'right',
    },
  ],
};

export default capacitor;
