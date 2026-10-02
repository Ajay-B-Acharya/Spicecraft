/**
 * LED (Light Emitting Diode) component definition.
 *
 * LEDs are directional two-terminal devices. Pin IDs use standard anode/cathode
 * naming to avoid ambiguity. Anode is the positive terminal (current flows in)
 * and cathode is the negative terminal (current flows out).
 */
import { ComponentDefinition } from '../types';

const led: ComponentDefinition = {
  type: 'led',
  symbol: 'led',
  prefix: 'D',
  defaultValue: 'RED',
  defaultRotation: 0,
  pins: [
    {
      id: 'A',
      name: 'anode',
      x: -32,
      y: 0,
      direction: 'left',
    },
    {
      id: 'K',
      name: 'cathode',
      x: 32,
      y: 0,
      direction: 'right',
    },
  ],
};

export default led;
