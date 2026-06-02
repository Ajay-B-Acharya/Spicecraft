'use client';

import { useCallback, useEffect, useState } from 'react';
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

  const fetchSources = useCallback(async () => {
    if (!projectId) return;
    try {
      setLoading(true);
      setError(null);
      const data = await circuitSourceService.getSources(projectId);
      setSources(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load sources');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      if (!user) {
        setSources([]);
        setLoading(false);
        return;
      }

      void fetchSources();
    });

    return unsubscribe;
  }, [fetchSources]);

  const createSource = useCallback(
    async (data: CreateSourceData): Promise<CircuitSource> => {
      const optimisticSource: CircuitSource = {
        id: `temp-${crypto.randomUUID()}`,
        project_id: projectId,
        title: data.title,
        source_name: data.source_name ?? null,
        source_url: data.source_url ?? null,
        image_url: data.image_url ?? null,
        created_at: new Date().toISOString(),
      };

      setError(null);
      setSources((prev) => [optimisticSource, ...prev]);

      try {
        const source = await circuitSourceService.createSource(projectId, data);
        setSources((prev) =>
          prev.map((item) => (item.id === optimisticSource.id ? source : item)),
        );
        return source;
      } catch (err) {
        setSources((prev) =>
          prev.filter((item) => item.id !== optimisticSource.id),
        );
        setError(err instanceof Error ? err.message : 'Failed to create source');
        throw err;
      }
    },
    [projectId],
  );

  const updateSource = useCallback(
    async (id: string, data: UpdateSourceData): Promise<CircuitSource> => {
      let previous: CircuitSource | undefined;

      setError(null);
      setSources((prev) =>
        prev.map((source) => {
          if (source.id !== id) return source;
          previous = source;
          return {
            ...source,
            ...data,
          };
        }),
      );

      try {
        const updated = await circuitSourceService.updateSource(id, data);
        setSources((prev) => prev.map((source) => (source.id === id ? updated : source)));
        return updated;
      } catch (err) {
        if (previous) {
          const rollbackSource = previous;
          setSources((prev) =>
            prev.map((source) => (source.id === id ? rollbackSource : source)),
          );
        }
        setError(err instanceof Error ? err.message : 'Failed to update source');
        throw err;
      }
    },
    [],
  );

  const deleteSource = useCallback(async (id: string): Promise<void> => {
    let removed: CircuitSource | undefined;

    setError(null);
    setSources((prev) => {
      removed = prev.find((source) => source.id === id);
      return prev.filter((source) => source.id !== id);
    });

    try {
      await circuitSourceService.deleteSource(id);
    } catch (err) {
      if (removed) {
        const rollbackSource = removed;
        setSources((prev) => [rollbackSource, ...prev]);
      }
      setError(err instanceof Error ? err.message : 'Failed to delete source');
      throw err;
    }
  }, []);

  return { sources, loading, error, fetchSources, createSource, updateSource, deleteSource };
}
