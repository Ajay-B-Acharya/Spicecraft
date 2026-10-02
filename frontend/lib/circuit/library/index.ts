/**
 * Canonical component definition registry.
 *
 * This module gathers all built-in component definitions in one place. Engine
 * code should access definitions through ComponentLibrary so future user-defined
 * and package-provided parts can be added without changing consumers.
 */
import resistor from './resistor';
import capacitor from './capacitor';
import inductor from './inductor';
import diode from './diode';
import led from './led';
import { npnTransistor, pnpTransistor } from './transistor';
import { currentSource, voltageSource } from './voltage';
import ground from './ground';
import ne555 from './ne555';
import { ComponentDefinition } from '../types';

export const componentDefinitions: ComponentDefinition[] = [
  resistor,
  capacitor,
  inductor,
  diode,
  led,
  npnTransistor,
  pnpTransistor,
  voltageSource,
  currentSource,
  ground,
  ne555,
];

export {
  resistor,
  capacitor,
  inductor,
  diode,
  led,
  npnTransistor,
  pnpTransistor,
  voltageSource,
  currentSource,
  ground,
  ne555,
};
