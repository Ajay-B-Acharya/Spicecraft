'use client';

import { useState } from 'react';
import { ExternalLink, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import type { CircuitSource } from '@/lib/circuitSourceService';

interface Props {
  source: CircuitSource;
  onDelete: (id: string) => Promise<void>;
}

export function SourceCard({ source, onDelete }: Props) {
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async () => {
    if (!window.confirm(`Delete "${source.title}"? This cannot be undone.`)) return;
    setDeleting(true);
    try {
      await onDelete(source.id);
      toast.success('Source deleted');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete source');
      setDeleting(false);
    }
  };

  return (
    <Card className="flex flex-col overflow-hidden transition-shadow hover:shadow-md">
      {source.image_url && (
        <div className="overflow-hidden rounded-t-xl">
          <img
            src={source.image_url}
            alt={source.title}
            className="h-40 w-full object-cover"
          />
        </div>
      )}

      <CardHeader className="pb-2">
        <CardTitle className="text-base leading-snug">{source.title}</CardTitle>
      </CardHeader>

      {(source.source_name || source.source_url) && (
        <CardContent className="pb-2 space-y-1">
          {source.source_name && (
            <p className="text-sm text-muted-foreground">{source.source_name}</p>
          )}
          {source.source_url && (
            <p className="truncate text-xs text-muted-foreground/70">
              {source.source_url}
            </p>
          )}
        </CardContent>
      )}

      <CardFooter className="mt-auto flex items-center justify-between pt-4">
        <div>
          {source.source_url && (
            <Button
              variant="outline"
              size="sm"
              asChild
            >
              <a
                href={source.source_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
                Open Link
              </a>
            </Button>
          )}
        </div>
        <Button
          size="sm"
          variant="ghost"
          className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive"
          onClick={handleDelete}
          disabled={deleting}
          aria-label="Delete source"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </CardFooter>
    </Card>
  );
}
