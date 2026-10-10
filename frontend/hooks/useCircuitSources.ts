'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { onAuthStateChanged } from 'firebase/auth';
import { auth } from '@/lib/firebase';
import {
  circuitSourceService,
  type CircuitSource,
  type CreateSourceData,
  type UpdateSourceData,
} from '@/lib/circuitSourceService';

export function useCircuitSources(projectId: string) {
  const [sources, setSources] = useState<CircuitSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const contextRevision = useRef(0);
  const requestRevision = useRef(0);

  const fetchSources = useCallback(async () => {
    const revision = ++requestRevision.current;
    if (!projectId || !auth.currentUser) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const data = await circuitSourceService.getSources(projectId);
      if (revision === requestRevision.current) setSources(data);
    } catch (err) {
      if (revision === requestRevision.current) setError(err instanceof Error ? err.message : 'Failed to load sources');
    } finally {
      if (revision === requestRevision.current) setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    setSources([]);
    setError(null);
    setLoading(true);
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      contextRevision.current++;
      requestRevision.current++;
      setSources([]);
      setError(null);
      setLoading(Boolean(user && projectId));
      if (user) void fetchSources();
    });

    return () => {
      contextRevision.current++;
      requestRevision.current++;
      unsubscribe();
    };
  }, [fetchSources, projectId]);

  const createSource = useCallback(
    async (data: CreateSourceData): Promise<CircuitSource> => {
      const revision = contextRevision.current;
      setError(null);
      try {
        const source = await circuitSourceService.createSource(projectId, data);
        if (revision !== contextRevision.current) return source;
        requestRevision.current++;
        setLoading(false);
        setSources((prev) => [source, ...prev.filter((item) => item.id !== source.id)]);
        return source;
      } catch (err) {
        if (revision === contextRevision.current) setError(err instanceof Error ? err.message : 'Failed to create source');
        throw err;
      }
    },
    [projectId],
  );

  const updateSource = useCallback(
    async (id: string, data: UpdateSourceData): Promise<CircuitSource> => {
      const revision = contextRevision.current;
      setError(null);
      try {
        const updated = await circuitSourceService.updateSource(id, data);
        if (revision !== contextRevision.current) return updated;
        requestRevision.current++;
        setLoading(false);
        setSources((prev) => prev.map((source) => (source.id === id ? updated : source)));
        return updated;
      } catch (err) {
        if (revision === contextRevision.current) setError(err instanceof Error ? err.message : 'Failed to update source');
        throw err;
      }
    },
    [],
  );

  const deleteSource = useCallback(async (id: string): Promise<void> => {
    const revision = contextRevision.current;
    setError(null);
    try {
      await circuitSourceService.deleteSource(id);
      if (revision !== contextRevision.current) return;
      requestRevision.current++;
      setLoading(false);
      setSources((prev) => prev.filter((source) => source.id !== id));
    } catch (err) {
      if (revision === contextRevision.current) setError(err instanceof Error ? err.message : 'Failed to delete source');
      throw err;
    }
  }, []);

  return { sources, loading, error, fetchSources, createSource, updateSource, deleteSource };
}
