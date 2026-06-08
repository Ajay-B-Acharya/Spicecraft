import Link from 'next/link';
import { AlertCircle, RotateCcw, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ErrorProps {
  message: string;
  onRetry: () => Promise<void> | void;
}

export function CircuitErrorState({ message, onRetry }: ErrorProps) {
  return (
    <div className="rounded-xl border border-destructive/50 bg-destructive/10 p-6">
      <div className="flex items-start gap-3">
        <AlertCircle className="mt-0.5 h-5 w-5 text-destructive" />
        <div className="space-y-4">
          <div>
            <p className="font-medium text-destructive">Unable to load circuit</p>
            <p className="mt-1 text-sm text-destructive/90">
              {message || 'The circuit could not be loaded. Please try again.'}
            </p>
          </div>
          <Button variant="outline" onClick={onRetry}>
            <RotateCcw className="mr-2 h-4 w-4" />
            Retry
          </Button>
        </div>
      </div>
    </div>
  );
}

export function CircuitNotFoundState() {
  return (
    <div className="rounded-xl border border-dashed p-10 text-center">
      <p className="text-xl font-semibold">Circuit Not Found</p>
      <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
        This circuit may have been removed or the link may be incorrect.
      </p>
      <Button asChild className="mt-6">
        <Link href="/search">
          <Search className="mr-2 h-4 w-4" />
          Search Circuits
        </Link>
      </Button>
    </div>
  );
}
