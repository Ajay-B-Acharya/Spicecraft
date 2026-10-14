import { useCallback, useEffect, useRef, useState } from 'react';
import {
  fetchDatasetCircuits,
  type DatasetCircuit,
  type DatasetCircuitsParams,
} from '@/lib/datasetService';

interface UseDatasetCircuitsState {
  circuits: DatasetCircuit[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  error: string | null;
}

interface UseDatasetCircuitsReturn extends UseDatasetCircuitsState {
  setPage: (page: number) => void;
  setSearch: (search: string) => void;
  setRepository: (repository: string) => void;
  search: string;
  repository: string;
  totalPages: number;
}

export function useDatasetCircuits(initialPageSize = 50): UseDatasetCircuitsReturn {
  const [state, setState] = useState<UseDatasetCircuitsState>({
    circuits: [],
    total: 0,
    page: 1,
    pageSize: initialPageSize,
    loading: true,
    error: null,
  });
  const [search, setSearchState] = useState('');
  const [repository, setRepositoryState] = useState('');
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(
    async (params: DatasetCircuitsParams) => {
      abortRef.current?.abort();
      abortRef.current = new AbortController();

      setState(prev => ({ ...prev, loading: true, error: null }));
      try {
        const data = await fetchDatasetCircuits(params);
        setState({
          circuits: data.circuits,
          total: data.total,
          page: data.page,
          pageSize: data.page_size,
          loading: false,
          error: null,
        });
      } catch (err: unknown) {
        if (err instanceof Error && err.name === 'AbortError') return;
        setState(prev => ({
          ...prev,
          loading: false,
          error: err instanceof Error ? err.message : 'Failed to load dataset',
        }));
      }
    },
    [],
  );

  useEffect(() => {
    load({ page: state.page, page_size: state.pageSize, search, repository });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.page, search, repository]);

  const setPage = useCallback((page: number) => {
    setState(prev => ({ ...prev, page }));
  }, []);

  const setSearch = useCallback((value: string) => {
    setSearchState(value);
    setState(prev => ({ ...prev, page: 1 }));
  }, []);

  const setRepository = useCallback((value: string) => {
    setRepositoryState(value);
    setState(prev => ({ ...prev, page: 1 }));
  }, []);

  const totalPages = Math.max(1, Math.ceil(state.total / state.pageSize));

  return {
    ...state,
    search,
    repository,
    setPage,
    setSearch,
    setRepository,
    totalPages,
  };
}
