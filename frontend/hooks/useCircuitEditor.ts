'use client';

import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import {
  circuitService,
  type Circuit,
} from '@/lib/circuitService';

export function useCircuitEditor(circuit: Circuit | null) {
  const [savedCircuit, setSavedCircuit] = useState<Circuit | null>(circuit);
  const [draft, setDraft] = useState<Circuit | null>(circuit);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const saveInFlight = useRef(false);
  const sourceRevision = useRef(0);
  const savedRef = useRef(savedCircuit);
  savedRef.current = savedCircuit;

  useEffect(() => {
    sourceRevision.current++;
    const previous = savedRef.current;
    setSavedCircuit(circuit);
    setDraft(current => current && circuit && current.id === circuit.id &&
      JSON.stringify(current) !== JSON.stringify(previous) ? current : circuit);
    setSaveError(null);
    return () => { sourceRevision.current++; };
  }, [circuit]);

  const hasUnsavedChanges =
    draft !== null &&
    savedCircuit !== null &&
    JSON.stringify(draft) !== JSON.stringify(savedCircuit);

  const updateComponentValue = (componentId: string, value: string) => {
    setDraft((currentDraft) => {
      if (!currentDraft) return currentDraft;

      return {
        ...currentDraft,
        components: currentDraft.components.map((component) =>
          component.id === componentId
            ? {
                ...component,
                value: value.trim() ? value : null,
              }
            : component,
        ),
      };
    });
  };

  /** Adds electrical connectivity independently of node positions. */
  const connectPins = (source: string, sourcePin: string, target: string, targetPin: string) => {
    const from = `${source}.${sourcePin}`;
    const to = `${target}.${targetPin}`;
    setDraft(current => {
      if (!current) return current;
      if (current.wires.some(wire => {
        const a = wire.from ?? wire.source;
        const b = wire.to ?? wire.destination;
        return (a === from && b === to) || (a === to && b === from);
      })) return current;
      return { ...current, wires: [...current.wires, { source: from, destination: to, from, to }] };
    });
  };

  /** Stores visual coordinates without changing wires or nets. */
  const updateComponentPosition = (id: string, position: { x: number; y: number }) => {
    setDraft(current => current ? {
      ...current,
      components: current.components.map(component => component.id === id || component.reference === id
        ? { ...component, position: { ...position }, x: position.x, y: position.y } : component),
    } : current);
  };

  const saveChanges = async (): Promise<Circuit | null> => {
    if (saveInFlight.current) return null;
    if (!draft || !hasUnsavedChanges) return draft;
    const revision = sourceRevision.current;
    const submitted = draft;

    try {
      saveInFlight.current = true;
      setSaving(true);
      setSaveError(null);
      const updatedCircuit = await circuitService.updateCircuit(submitted.id, submitted);
      if (revision !== sourceRevision.current) return null;
      setSavedCircuit(updatedCircuit);
      setDraft(current => current === submitted ? updatedCircuit : current);
      toast.success('Circuit saved');
      return updatedCircuit;
    } catch (err) {
      if (revision !== sourceRevision.current) return null;
      const message = err instanceof Error ? err.message : 'Failed to save circuit';
      setSaveError(message);
      toast.error(message);
      return null;
    } finally {
      saveInFlight.current = false;
      setSaving(false);
    }
  };

  const resetDraft = (nextCircuit: Circuit) => {
    sourceRevision.current++;
    setSavedCircuit(nextCircuit);
    setDraft(nextCircuit);
    setSaveError(null);
  };

  return {
    circuit: draft,
    saving,
    saveError,
    hasUnsavedChanges,
    updateComponentValue,
    connectPins,
    updateComponentPosition,
    saveChanges,
    resetDraft,
  };
}
