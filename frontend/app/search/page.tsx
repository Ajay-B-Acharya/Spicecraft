'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { onAuthStateChanged } from 'firebase/auth';
import { DashboardShell } from '@/components/dashboard-shell';
import { SearchBar } from '@/components/search/SearchBar';
import { SearchResults } from '@/components/search/SearchResults';
import { auth } from '@/lib/firebase';
import { useSearch } from '@/hooks/useSearch';

export default function SearchPage() {
  const router = useRouter();
  const { error, loading, query, results, runSearch, searched } = useSearch();

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;

    const unsubscribe = onAuthStateChanged(auth, (user) => {
      if (!user) {
        timer = setTimeout(() => {
          if (!auth.currentUser) {
            router.push('/login');
          }
        }, 500);
      }
    });

    return () => {
      unsubscribe();
      if (timer) clearTimeout(timer);
    };
  }, [router]);

  return (
    <DashboardShell>
      <main className="space-y-6 p-6 md:p-8">
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight">Search Circuits</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Search electronics resources and save useful references directly into your projects.
          </p>
        </div>

        <SearchBar loading={loading} onSearch={runSearch} />

        <SearchResults
          error={error}
          loading={loading}
          query={query}
          results={results}
          searched={searched}
        />
      </main>
    </DashboardShell>
  );
}
