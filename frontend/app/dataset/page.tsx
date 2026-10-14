'use client';

import { useState } from 'react';
import { ExternalLink, Search, Database, Github, ChevronLeft, ChevronRight } from 'lucide-react';
import { DashboardShell } from '@/components/dashboard-shell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { useDatasetCircuits } from '@/hooks/useDatasetCircuits';

const REPOSITORIES = [
  { slug: '', label: 'All repositories' },
  { slug: 'ribster-ltspice', label: 'Ribster/LTSpice' },
  { slug: 'alok-ltspice-circuit-design', label: 'Alok018/LTSpice_Circuit_Design' },
  { slug: 'mr-jaymac-ltspice-circuits', label: 'Mr-Jaymac/LTSpice-Circuits' },
  { slug: 'bert-ltspice-examples', label: 'bert/LTSpice-examples' },
];

function repoLabel(slug: string) {
  return REPOSITORIES.find(r => r.slug === slug)?.label ?? slug;
}

export default function DatasetPage() {
  const [searchInput, setSearchInput] = useState('');

  const {
    circuits,
    total,
    page,
    pageSize,
    totalPages,
    loading,
    error,
    search,
    repository,
    setPage,
    setSearch,
    setRepository,
  } = useDatasetCircuits(50);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput.trim());
  };

  const startItem = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const endItem = Math.min(page * pageSize, total);

  return (
    <DashboardShell>
      <main className="space-y-6 p-6 md:p-8">

        {/* Header */}
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Database className="h-6 w-6 text-primary" />
            <h1 className="text-3xl font-semibold tracking-tight">Circuit Dataset</h1>
          </div>
          <p className="max-w-2xl text-sm text-muted-foreground">
            {total > 0
              ? `${total.toLocaleString()} LTspice .asc schematics collected from public GitHub repositories.`
              : 'LTspice .asc schematics collected from public GitHub repositories.'}
            {' '}Click any entry to open the original file on GitHub.
          </p>
        </div>

        {/* Filters */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <form onSubmit={handleSearchSubmit} className="flex flex-1 gap-2">
            <div className="relative flex-1 max-w-md">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by filename…"
                value={searchInput}
                onChange={e => setSearchInput(e.target.value)}
                className="pl-9"
                aria-label="Search circuits"
              />
            </div>
            <Button type="submit" variant="secondary">Search</Button>
            {(search || repository) && (
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setSearchInput('');
                  setSearch('');
                  setRepository('');
                }}
              >
                Clear
              </Button>
            )}
          </form>

          {/* Repository filter */}
          <div className="flex flex-wrap gap-1.5">
            {REPOSITORIES.map(r => (
              <button
                key={r.slug}
                onClick={() => setRepository(r.slug)}
                className={[
                  'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
                  repository === r.slug
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border bg-muted/40 text-muted-foreground hover:border-primary/40 hover:text-foreground',
                ].join(' ')}
                aria-pressed={repository === r.slug}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>

        {/* Status bar */}
        {!loading && !error && total > 0 && (
          <p className="text-xs text-muted-foreground">
            Showing {startItem}–{endItem} of {total.toLocaleString()} circuits
            {search ? ` matching "${search}"` : ''}
            {repository ? ` in ${repoLabel(repository)}` : ''}
          </p>
        )}

        {/* Error */}
        {error && (
          <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
            Failed to load dataset: {error}
          </div>
        )}

        {/* Loading skeleton */}
        {loading && (
          <div className="space-y-2">
            {Array.from({ length: 10 }, (_, i) => (
              <div key={i} className="h-14 animate-pulse rounded-lg border border-border bg-muted/30" />
            ))}
          </div>
        )}

        {/* Circuit table */}
        {!loading && !error && circuits.length > 0 && (
          <div className="overflow-hidden rounded-xl border border-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40">
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">Filename</th>
                  <th className="hidden px-4 py-3 text-left font-medium text-muted-foreground md:table-cell">Path</th>
                  <th className="hidden px-4 py-3 text-left font-medium text-muted-foreground lg:table-cell">Repository</th>
                  <th className="px-4 py-3 text-right font-medium text-muted-foreground">Open</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {circuits.map(circuit => (
                  <tr key={circuit.id} className="group transition-colors hover:bg-muted/30">
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs font-medium text-foreground">
                        {circuit.filename}
                      </span>
                    </td>
                    <td className="hidden px-4 py-3 md:table-cell">
                      <span className="font-mono text-xs text-muted-foreground line-clamp-1 max-w-xs" title={circuit.original_relative_path}>
                        {circuit.original_relative_path}
                      </span>
                    </td>
                    <td className="hidden px-4 py-3 lg:table-cell">
                      <Badge variant="secondary" className="gap-1 font-mono text-xs">
                        <Github className="h-3 w-3" />
                        {circuit.source_repository}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <a
                        href={circuit.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label={`Open ${circuit.filename} on GitHub`}
                        className="inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium text-primary opacity-70 transition-opacity hover:opacity-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                        GitHub
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && circuits.length === 0 && (
          <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-border py-16 text-center">
            <Database className="h-10 w-10 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground">No circuits found.</p>
            {(search || repository) && (
              <Button variant="ghost" size="sm" onClick={() => { setSearch(''); setSearchInput(''); setRepository(''); }}>
                Clear filters
              </Button>
            )}
          </div>
        )}

        {/* Pagination */}
        {!loading && !error && totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(page - 1)}
              disabled={page <= 1}
              aria-label="Previous page"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm text-muted-foreground">
              Page {page} of {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(page + 1)}
              disabled={page >= totalPages}
              aria-label="Next page"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        )}

      </main>
    </DashboardShell>
  );
}
