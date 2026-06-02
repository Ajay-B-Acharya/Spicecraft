'use client';

import { useCallback, useState } from 'react';
import { searchService, type SearchResult } from '@/lib/searchService';

export function useSearch() {
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [searched, setSearched] = useState(false);

  const runSearch = useCallback(async (nextQuery: string) => {
    const trimmedQuery = nextQuery.trim();
    if (!trimmedQuery) {
      setResults([]);
      setQuery('');
      setSearched(false);
      setError(null);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setQuery(trimmedQuery);
      setSearched(true);
      const data = await searchService.search(trimmedQuery);
      setResults(data);
    } catch (err) {
      setResults([]);
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    error,
    loading,
    query,
    results,
    runSearch,
    searched,
  };
}
