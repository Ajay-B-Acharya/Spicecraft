'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Download, ExternalLink, FileCode2, Github, AlertCircle } from 'lucide-react';
import { DashboardShell } from '@/components/dashboard-shell';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import type { DatasetCircuit } from '@/lib/datasetService';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

interface CircuitViewerState {
  circuit: DatasetCircuit | null;
  content: string | null;
  loading: boolean;
  error: string | null;
  contentError: string | null;
}

export default function DatasetCircuitPage() {
  const params = useParams<{ circuitId: string }>();
  const router = useRouter();
  const circuitId = typeof params.circuitId === 'string' ? params.circuitId : '';

  const [state, setState] = useState<CircuitViewerState>({
    circuit: null,
    content: null,
    loading: true,
    error: null,
    contentError: null,
  });

  useEffect(() => {
    if (!circuitId) {
      router.push('/dataset');
      return;
    }

    // Fetch circuit metadata
    const fetchCircuit = async () => {
      try {
        const res = await fetch(`${API_BASE}/dataset/circuits/${encodeURIComponent(circuitId)}`);
        if (!res.ok) {
          throw new Error(`Failed to load circuit: ${res.status} ${res.statusText}`);
        }
        const circuit = (await res.json()) as DatasetCircuit;
        setState(prev => ({ ...prev, circuit, loading: false }));

        // Fetch .asc content
        try {
          const contentRes = await fetch(`${API_BASE}/dataset/circuits/${encodeURIComponent(circuitId)}/content`);
          if (!contentRes.ok) {
            throw new Error(`Failed to load .asc content: ${contentRes.status} ${contentRes.statusText}`);
          }
          const content = await contentRes.text();
          setState(prev => ({ ...prev, content }));
        } catch (err) {
          setState(prev => ({
            ...prev,
            contentError: err instanceof Error ? err.message : 'Failed to load .asc content',
          }));
        }
      } catch (err) {
        setState(prev => ({
          ...prev,
          loading: false,
          error: err instanceof Error ? err.message : 'Failed to load circuit',
        }));
      }
    };

    fetchCircuit();
  }, [circuitId, router]);

  const handleDownload = () => {
    if (!state.content || !state.circuit) return;
    const blob = new Blob([state.content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = state.circuit.filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (state.loading) {
    return (
      <DashboardShell>
        <main className="space-y-6 p-6 md:p-8">
          <Skeleton className="h-10 w-64" />
          <Skeleton className="h-96 w-full" />
        </main>
      </DashboardShell>
    );
  }

  if (state.error || !state.circuit) {
    return (
      <DashboardShell>
        <main className="space-y-6 p-6 md:p-8">
          <Button variant="ghost" asChild>
            <Link href="/dataset">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Dataset
            </Link>
          </Button>
          <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-6 text-destructive">
            <AlertCircle className="mb-2 h-5 w-5" />
            <p className="font-medium">Failed to load circuit</p>
            <p className="mt-1 text-sm">{state.error ?? 'Unknown error'}</p>
          </div>
        </main>
      </DashboardShell>
    );
  }

  const { circuit, content, contentError } = state;

  return (
    <DashboardShell>
      <main className="space-y-6 p-6 md:p-8">
        {/* Header */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-2">
            <Button variant="ghost" asChild className="w-fit px-0">
              <Link href="/dataset">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Dataset
              </Link>
            </Button>
            <div className="flex items-center gap-3">
              <FileCode2 className="h-6 w-6 text-primary" />
              <h1 className="text-3xl font-semibold tracking-tight">{circuit.filename}</h1>
            </div>
          </div>

          {/* Actions */}
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" asChild>
              <a
                href={circuit.source_url}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="View source on GitHub"
              >
                <Github className="mr-2 h-4 w-4" />
                View Source
              </a>
            </Button>
            {content && (
              <Button onClick={handleDownload}>
                <Download className="mr-2 h-4 w-4" />
                Download .asc
              </Button>
            )}
          </div>
        </div>

        {/* Metadata */}
        <div className="rounded-xl border bg-card p-4 text-card-foreground shadow-sm">
          <dl className="grid grid-cols-1 gap-3 text-sm md:grid-cols-2">
            <div>
              <dt className="font-medium text-muted-foreground">Repository</dt>
              <dd className="mt-1">
                <Badge variant="secondary" className="gap-1 font-mono">
                  <Github className="h-3 w-3" />
                  {circuit.source_repository}
                </Badge>
              </dd>
            </div>
            <div>
              <dt className="font-medium text-muted-foreground">Path</dt>
              <dd className="mt-1 font-mono text-xs">{circuit.original_relative_path}</dd>
            </div>
            <div>
              <dt className="font-medium text-muted-foreground">License</dt>
              <dd className="mt-1">
                <Badge variant={circuit.license_status === 'UNKNOWN' ? 'secondary' : 'default'}>
                  {circuit.license_status}
                </Badge>
              </dd>
            </div>
            <div>
              <dt className="font-medium text-muted-foreground">Source URL</dt>
              <dd className="mt-1">
                <a
                  href={circuit.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                >
                  {circuit.source_repository_url}
                  <ExternalLink className="h-3 w-3" />
                </a>
              </dd>
            </div>
          </dl>
        </div>

        {/* .asc Content */}
        {contentError ? (
          <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
            <AlertCircle className="mb-2 h-4 w-4" />
            <p className="font-medium">Failed to load .asc content</p>
            <p className="mt-1">{contentError}</p>
          </div>
        ) : content ? (
          <div className="rounded-xl border bg-card text-card-foreground shadow-sm">
            <div className="border-b p-4">
              <h2 className="text-sm font-semibold">LTspice Schematic (.asc)</h2>
              <p className="mt-1 text-xs text-muted-foreground">
                Raw LTspice schematic file content. Import to editor or download for use in LTspice.
              </p>
            </div>
            <div className="p-4">
              <pre className="max-h-[600px] overflow-auto rounded-lg border bg-muted/30 p-4 font-mono text-xs leading-relaxed">
                {content}
              </pre>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center rounded-xl border border-dashed py-16">
            <div className="flex flex-col items-center gap-2 text-muted-foreground">
              <FileCode2 className="h-8 w-8" />
              <p className="text-sm">Loading .asc content…</p>
            </div>
          </div>
        )}

        {/* Attribution Notice */}
        <div className="rounded-lg border border-border/50 bg-muted/20 p-4 text-xs text-muted-foreground">
          <p>
            <strong>Attribution:</strong> This circuit is sourced from the public repository{' '}
            <a
              href={circuit.source_repository_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              {circuit.source_repository}
            </a>
            . The license status is currently <strong>{circuit.license_status}</strong>. Please verify
            licensing terms before redistribution or commercial use.
          </p>
        </div>
      </main>
    </DashboardShell>
  );
}
