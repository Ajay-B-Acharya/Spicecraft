/**
 * Electrical pin model.
 *
 * A pin is a UI-independent connection point owned by a component. Coordinates
 * are relative to the component origin and are resolved into schematic-space
 * coordinates by the PinResolver engine.
 */
export interface Pin {
  id: string;
  name: string;

  x: number;
  y: number;

  direction?: 'left' | 'right' | 'top' | 'bottom';

  net?: string;
}
