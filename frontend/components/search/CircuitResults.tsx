import { AlertCircle, SearchCode } from 'lucide-react';
import { CircuitCard } from '@/components/search/CircuitCard';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import type { Circuit } from '@/lib/circuitService';

interface Props {
  circuits: Circuit[];
  error: string | null;
  loading: boolean;
  onRetry: () => Promise<void> | void;
}

export function CircuitResults({ circuits, error, loading, onRetry }: Props) {
  if (error) {
    return (
      <div className="rounded-xl border border-destructive/50 bg-destructive/10 p-6">
        <div className="flex items-start gap-3">
          <AlertCircle className="mt-0.5 h-5 w-5 text-destructive" />
          <div className="space-y-3">
            <div>
              <p className="font-medium text-destructive">Unable to load circuits</p>
              <p className="text-sm text-destructive/90">{error}</p>
            </div>
            <Button variant="outline" onClick={onRetry}>
              Try Again
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {[0, 1, 2, 3, 4, 5].map((item) => (
          <Skeleton key={item} className="h-64 rounded-xl" />
        ))}
      </div>
    );
  }

  if (circuits.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed py-20 text-center">
        <SearchCode className="mb-4 h-10 w-10 text-muted-foreground/40" />
        <p className="font-medium">No circuits available</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Circuits will appear here once the backend has data to return.
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {circuits.map((circuit) => (
        <CircuitCard key={circuit.id} circuit={circuit} />
      ))}
    </div>
  );
}
