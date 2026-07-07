/**
 * Inductor component definition.
 *
 * Provides the canonical inductor symbol metadata and pin layout for the circuit
 * engine.
 */
import { ComponentDefinition } from '../types';

const inductor: ComponentDefinition = {
  type: 'inductor',
  symbol: 'ind',
  prefix: 'L',
  defaultValue: '10u',
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

export default inductor;
