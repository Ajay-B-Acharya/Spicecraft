/**
 * UI-independent circuit model.
 *
 * This is the top-level electrical design document consumed by future EDA
 * modules such as netlist export, ERC, simulation, routing, and PCB generation.
 */
import { Component } from './Component';
import { Net } from './Net';

export interface Circuit {
  components: Component[];

  nets: Net[];
}
