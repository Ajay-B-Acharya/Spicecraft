'use client';

import { BookOpen } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { useCircuitSources } from '@/hooks/useCircuitSources';
import { CreateSourceDialog } from './CreateSourceDialog';
import { SourceCard } from './SourceCard';

interface Props {
  projectId: string;
}

export function SourcesView({ projectId }: Props) {
  const { sources, loading, error, createSource, deleteSource } =
    useCircuitSources(projectId);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Circuit Sources</h2>
          {!loading && (
            <p className="mt-1 text-sm text-muted-foreground">
              {sources.length} source{sources.length !== 1 ? 's' : ''}
            </p>
          )}
        </div>
        <CreateSourceDialog onCreate={createSource} />
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-48 rounded-xl" />
          ))}
        </div>
      ) : sources.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed py-20 text-center">
          <BookOpen className="mb-4 h-10 w-10 text-muted-foreground/40" />
          <p className="font-medium">No sources yet</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Add your first circuit source to get started
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {sources.map((source) => (
            <SourceCard
              key={source.id}
              source={source}
              onDelete={deleteSource}
            />
          ))}
        </div>
      )}
    </div>
  );
}
