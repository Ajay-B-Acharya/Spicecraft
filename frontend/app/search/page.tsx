'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { onAuthStateChanged } from 'firebase/auth';
import { DashboardShell } from '@/components/dashboard-shell';
import { CircuitResults } from '@/components/search/CircuitResults';
import { auth } from '@/lib/firebase';
import { useCircuits } from '@/hooks/useCircuits';

export default function SearchPage() {
  const router = useRouter();
  const { circuits, error, loading, refetch } = useCircuits();

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
            Browse the circuit library from the FastAPI backend and open any design for a closer look.
          </p>
        </div>

        <CircuitResults circuits={circuits} error={error} loading={loading} onRetry={refetch} />
      </main>
    </DashboardShell>
  );
}
