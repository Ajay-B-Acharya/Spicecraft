'use client';

import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import {
  circuitService,
  type Circuit,
  type CircuitComponent,
} from '@/lib/circuitService';

export function useCircuitEditor(circuit: Circuit | null) {
  const [savedCircuit, setSavedCircuit] = useState<Circuit | null>(circuit);
  const [draft, setDraft] = useState<Circuit | null>(circuit);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setSavedCircuit(circuit);
    setDraft(circuit);
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

  const saveChanges = async (): Promise<Circuit | null> => {
    if (!draft || !hasUnsavedChanges) return draft;

    try {
      setSaving(true);
      const updatedCircuit = await circuitService.updateCircuit(draft.id, draft);
      setSavedCircuit(updatedCircuit);
      setDraft(updatedCircuit);
      toast.success('Circuit saved');
      return updatedCircuit;
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save circuit');
      return null;
    } finally {
      setSaving(false);
    }
  };

  const resetDraft = (nextCircuit: Circuit) => {
    setSavedCircuit(nextCircuit);
    setDraft(nextCircuit);
  };

  return {
    circuit: draft,
    saving,
    hasUnsavedChanges,
    updateComponentValue,
    saveChanges,
    resetDraft,
  };
}
