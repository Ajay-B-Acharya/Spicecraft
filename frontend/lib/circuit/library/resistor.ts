/**
 * Resistor component definition.
 *
 * Defines the canonical electrical metadata for resistor instances. This file is
 * part of the component library and should be consumed through ComponentLibrary
 * rather than duplicated by UI or exporter modules.
 */
import { ComponentDefinition } from '../types';

const resistor: ComponentDefinition = {
  type: 'resistor',
  symbol: 'res',
  prefix: 'R',
  defaultValue: '1k',
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

export default resistor;
