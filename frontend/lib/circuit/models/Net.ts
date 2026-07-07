/**
 * Electrical net model.
 *
 * A net is a set of component pins that are electrically connected. It contains
 * no drawing or routing information so it can be shared by exporters, ERC,
 * simulation, and PCB-oriented modules. Optional labels preserve user- or
 * AI-provided named-net references such as VCC, GND, VIN, or OUT.
 */
export interface Net {
  id: string;

  name?: string;

  labels?: string[];

  pins: {
    componentId: string;

    pinId: string;
  }[];
}
