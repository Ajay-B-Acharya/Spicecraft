'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { onAuthStateChanged } from 'firebase/auth';
import { auth } from '@/lib/firebase';
import { circuitService, type Circuit } from '@/lib/circuitService';
import { ApiError } from '@/lib/apiError';

export function useCircuit(circuitId: string) {
  const [circuit, setCircuit] = useState<Circuit | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const requestRevision = useRef(0);

  const fetchCircuit = useCallback(async () => {
    const revision = ++requestRevision.current;
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
      if (revision !== requestRevision.current) return;
      setCircuit(data);
    } catch (err) {
      if (revision !== requestRevision.current) return;
      const message = err instanceof Error ? err.message : 'Failed to load circuit';
      setNotFound(err instanceof ApiError && err.status === 404);
      setError(message);
    } finally {
      if (revision === requestRevision.current) setLoading(false);
    }
  }, [circuitId]);

  useEffect(() => {
    setCircuit(null);
    setError(null);
    setNotFound(false);
    setLoading(true);
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      if (user) {
        void fetchCircuit();
        return;
      }

      requestRevision.current++;
      setCircuit(null);
      setError(null);
      setNotFound(false);
      setLoading(false);
    });

    return () => {
      requestRevision.current++;
      unsubscribe();
    };
  }, [fetchCircuit]);

  return {
    circuit,
    loading,
    error,
    notFound,
    refetch: fetchCircuit,
  };
}
