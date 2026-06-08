'use client';

import { useCallback, useEffect, useState } from 'react';
import { onAuthStateChanged } from 'firebase/auth';
import { auth } from '@/lib/firebase';
import { circuitService, type Circuit } from '@/lib/circuitService';

export function useCircuits() {
  const [circuits, setCircuits] = useState<Circuit[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCircuits = useCallback(async () => {
    if (!auth.currentUser) return;

    try {
      setLoading(true);
      setError(null);
      const data = await circuitService.getCircuits();
      setCircuits(data);
    } catch (err) {
      setCircuits([]);
      setError(err instanceof Error ? err.message : 'Failed to load circuits');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      if (user) {
        void fetchCircuits();
        return;
      }

      setCircuits([]);
      setError(null);
      setLoading(false);
    });

    return unsubscribe;
  }, [fetchCircuits]);

  return {
    circuits,
    loading,
    error,
    refetch: fetchCircuits,
  };
}
