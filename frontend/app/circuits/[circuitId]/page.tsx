'use client';

import Link from 'next/link';
import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { onAuthStateChanged } from 'firebase/auth';
import { ArrowLeft } from 'lucide-react';
import { CircuitEditorActions } from '@/components/circuits/CircuitEditorActions';
import { CircuitComponentsTable } from '@/components/circuits/CircuitComponentsTable';
import { CircuitConnectionsTable } from '@/components/circuits/CircuitConnectionsTable';
import { CircuitDetailSkeleton } from '@/components/circuits/CircuitDetailSkeleton';
import { CircuitSchematic } from '@/components/circuits/CircuitSchematic';
import {
  CircuitErrorState,
  CircuitNotFoundState,
} from '@/components/circuits/CircuitErrorState';
import { CircuitMetadata } from '@/components/circuits/CircuitMetadata';
import { CircuitOverview } from '@/components/circuits/CircuitOverview';
import { DashboardShell } from '@/components/dashboard-shell';
import { Button } from '@/components/ui/button';
import { useCircuitEditor } from '@/hooks/useCircuitEditor';
import { auth } from '@/lib/firebase';
import { useCircuit } from '@/hooks/useCircuit';

export default function CircuitDetailPage() {
  const params = useParams<{ circuitId: string }>();
  const router = useRouter();
  const circuitId = typeof params.circuitId === 'string' ? params.circuitId : '';
  const { circuit, error, loading, notFound, refetch } = useCircuit(circuitId);
  const {
    circuit: editableCircuit,
    hasUnsavedChanges,
    resetDraft,
    saveChanges,
    saving,
    updateComponentValue,
  } = useCircuitEditor(circuit);

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

  const handleSaveChanges = async () => {
    const updatedCircuit = await saveChanges();
    if (updatedCircuit) {
      resetDraft(updatedCircuit);
    }
  };

  return (
    <DashboardShell>
      <main className="space-y-6 p-6 md:p-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-2">
            <Button variant="ghost" asChild className="w-fit px-0 text-muted-foreground">
              <Link href="/search">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Search
              </Link>
            </Button>
            <h1 className="text-3xl font-semibold tracking-tight">
              {loading ? 'Circuit Details' : circuit?.name ?? 'Circuit Not Found'}
            </h1>
          </div>
          {!loading && !error && !notFound && editableCircuit ? (
            <CircuitEditorActions
              hasUnsavedChanges={hasUnsavedChanges}
              onSave={handleSaveChanges}
              saving={saving}
            />
          ) : null}
        </div>

        {loading ? <CircuitDetailSkeleton /> : null}

        {!loading && notFound ? <CircuitNotFoundState /> : null}

        {!loading && error && !notFound ? (
          <CircuitErrorState message={error} onRetry={refetch} />
        ) : null}

        {!loading && !error && !notFound && editableCircuit ? (
          <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]">
            <div className="space-y-4">
              <CircuitOverview circuit={editableCircuit} />
              
              <div className="rounded-xl border bg-card text-card-foreground shadow">
                <div className="p-6 space-y-1.5 flex flex-col">
                  <h3 className="font-semibold leading-none tracking-tight">Circuit Schematic</h3>
                  <p className="text-sm text-muted-foreground text-left mt-2">Visual representation. View-only for now.</p>
                </div>
                <div className="p-6 pt-0">
                  <CircuitSchematic circuit={editableCircuit} />
                </div>
              </div>

              <CircuitComponentsTable
                components={editableCircuit.components}
                onValueChange={updateComponentValue}
                saving={saving}
              />
              <CircuitConnectionsTable wires={editableCircuit.wires} />
            </div>
            <CircuitMetadata tags={editableCircuit.tags} />
          </div>
        ) : null}
      </main>
    </DashboardShell>
  );
}
