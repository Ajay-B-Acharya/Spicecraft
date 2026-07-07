/**
 * Electrical component instance model.
 *
 * This model represents a real circuit element independently of any visual
 * renderer. UI nodes, exporters, routers, and simulators should adapt to this
 * shape rather than storing their own component metadata.
 */
import { Pin } from './Pin';

export interface Component {
  id: string;

  type: string;

  name: string;

  value?: string;

  symbol: string;

  prefix: string;

  rotation: number;

  mirror?: boolean;

  position: {
    x: number;

    y: number;
  };

  pins: Pin[];
}
