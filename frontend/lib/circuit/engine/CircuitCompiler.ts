/**
 * High-level circuit compiler.
 *
 * This is the future entry point for exporters and analysis modules. It turns
 * AI-generated circuit JSON into a validated, UI-independent electrical model by
 * delegating parsing/building to CircuitBuilder and validation to
 * CircuitValidator.
 */
import { CircuitBuilder } from './CircuitBuilder';
import { CircuitValidator } from './CircuitValidator';
import { CompiledCircuit } from '../types';

export class CircuitCompiler {
  static compile(source: unknown): CompiledCircuit {
    const { circuit, validationSeed } = CircuitBuilder.buildDetailed(source);
    const validation = CircuitValidator.validate(circuit, validationSeed);

    return {
      ...circuit,
      validation,
    };
  }
}
