/**
 * Ground reference component definition.
 *
 * Ground is represented as a single-pin electrical reference. Exporters may map
 * this component to tool-specific ground constructs such as SPICE node 0.
 */
import { ComponentDefinition } from '../types';

const ground: ComponentDefinition = {
  type: 'ground',
  symbol: 'gnd',
  prefix: 'GND',
  defaultValue: '0',
  defaultRotation: 0,
  pins: [
    {
      id: '0',
      name: 'ground',
      x: 0,
      y: 0,
      direction: 'top',
    },
  ],
};

export default ground;
