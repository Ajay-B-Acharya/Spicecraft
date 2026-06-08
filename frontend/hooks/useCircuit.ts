'use client';

import { useCallback, useEffect, useState } from 'react';
import { onAuthStateChanged } from 'firebase/auth';
import { auth } from '@/lib/firebase';
import { circuitService, type Circuit } from '@/lib/circuitService';

export function useCircuit(circuitId: string) {
  const [circuit, setCircuit] = useState<Circuit | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  const fetchCircuit = useCallback(async () => {
    if (!circuitId) {
      setCircuit(null);
      setNotFound(true);
      setLoading(false);
      return;
    }

    if (!auth.currentUser) return;

    try {
      setLoading(true);
      setError(null);
      setNotFound(false);
      const data = await circuitService.getCircuit(circuitId);
      setCircuit(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load circuit';
      setCircuit(null);
      setNotFound(message.toLowerCase().includes('not found') || message.includes('404'));
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [circuitId]);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      if (user) {
        void fetchCircuit();
        return;
      }

      setCircuit(null);
      setError(null);
      setNotFound(false);
      setLoading(false);
    });

    return unsubscribe;
  }, [fetchCircuit]);

  return {
    circuit,
    loading,
    error,
    notFound,
    refetch: fetchCircuit,
  };
}
