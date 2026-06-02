'use client';

import { useEffect, useState } from 'react';
import { ExternalLink, FolderPlus, SearchCode } from 'lucide-react';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useProjects } from '@/hooks/useProjects';
import { circuitSourceService } from '@/lib/circuitSourceService';
import type { SearchResult } from '@/lib/searchService';

interface Props {
  error: string | null;
  loading: boolean;
  query: string;
  results: SearchResult[];
  searched: boolean;
}

export function SearchResults({
  error,
  loading,
  query,
  results,
  searched,
}: Props) {
  const { projects, loading: projectsLoading } = useProjects();
  const [selectedResult, setSelectedResult] = useState<SearchResult | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!selectedResult) {
      setSelectedProjectId('');
    }
  }, [selectedResult]);

  const handleSave = async () => {
    if (!selectedResult || !selectedProjectId) return;

    setSaving(true);
    try {
      await circuitSourceService.createSource(selectedProjectId, {
        title: selectedResult.title,
        source_name: selectedResult.source_name ?? undefined,
        source_url: selectedResult.source_url ?? undefined,
        image_url: selectedResult.image_url ?? undefined,
      });
      toast.success('Saved to project');
      setSelectedResult(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save result');
    } finally {
      setSaving(false);
    }
  };

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
        {error}
      </div>
    );
  }

  if (loading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {[0, 1, 2, 3, 4, 5].map((item) => (
          <Skeleton key={item} className="h-64 rounded-xl" />
        ))}
      </div>
    );
  }

  if (!searched) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed py-20 text-center">
        <SearchCode className="mb-4 h-10 w-10 text-muted-foreground/40" />
        <p className="font-medium">Search electronics resources</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Find datasheets, application notes, tutorials, LTspice examples, and research papers.
        </p>
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed py-20 text-center">
        <SearchCode className="mb-4 h-10 w-10 text-muted-foreground/40" />
        <p className="font-medium">No results found</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Try a more specific electronics query for "{query}".
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {results.map((result, index) => (
          <Card key={`${result.source_url ?? result.title}-${index}`} className="flex h-full flex-col overflow-hidden">
            {result.image_url ? (
              <div className="flex h-28 items-center justify-center border-b bg-muted/30">
                <img
                  src={result.image_url}
                  alt={result.source_name ?? result.title}
                  className="h-14 w-14 rounded-lg object-contain"
                />
              </div>
            ) : null}
            <CardHeader className="pb-2">
              <CardTitle className="line-clamp-2 text-base leading-snug">
                {result.title}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 pb-2">
              <p className="text-sm text-muted-foreground">
                {result.source_name ?? 'Unknown Source'}
              </p>
              {result.source_url ? (
                <p className="truncate text-xs text-muted-foreground/70">
                  {result.source_url}
                </p>
              ) : null}
            </CardContent>
            <CardFooter className="mt-auto flex items-center justify-between gap-2">
              {result.source_url ? (
                <Button variant="outline" size="sm" asChild>
                  <a href={result.source_url} target="_blank" rel="noopener noreferrer">
                    <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
                    Open
                  </a>
                </Button>
              ) : (
                <span />
              )}
              <Button size="sm" onClick={() => setSelectedResult(result)}>
                <FolderPlus className="mr-1.5 h-3.5 w-3.5" />
                Save To Project
              </Button>
            </CardFooter>
          </Card>
        ))}
      </div>

      <Dialog
        open={selectedResult !== null}
        onOpenChange={(open) => {
          if (!open) setSelectedResult(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save Search Result</DialogTitle>
            <DialogDescription>
              Choose a project to store this result as a circuit source.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <div className="rounded-lg border bg-muted/20 p-3">
              <p className="font-medium">{selectedResult?.title}</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {selectedResult?.source_name ?? 'Unknown Source'}
              </p>
            </div>

            <Select
              value={selectedProjectId}
              onValueChange={setSelectedProjectId}
              disabled={projectsLoading || projects.length === 0}
            >
              <SelectTrigger className="w-full">
                <SelectValue
                  placeholder={
                    projects.length === 0 ? 'Create a project first' : 'Select a project'
                  }
                />
              </SelectTrigger>
              <SelectContent>
                {projects.map((project) => (
                  <SelectItem key={project.id} value={project.id}>
                    {project.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setSelectedResult(null)}>
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={!selectedProjectId || saving || projects.length === 0}
            >
              {saving ? 'Saving...' : 'Save To Project'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
