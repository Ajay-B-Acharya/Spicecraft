'use client';

import { useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import type { Project, UpdateProjectData } from '@/lib/projectService';

interface Props {
  project: Project;
  onDelete: (id: string) => Promise<void>;
  onUpdate: (id: string, data: UpdateProjectData) => Promise<unknown>;
}

export function ProjectCard({ project, onDelete }: Props) {
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async () => {
    if (!window.confirm(`Delete "${project.name}"? This cannot be undone.`)) return;
    setDeleting(true);
    try {
      await onDelete(project.id);
      toast.success('Project deleted');
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : 'Failed to delete project',
      );
      setDeleting(false);
    }
  };

  return (
    <Card className="flex flex-col transition-shadow hover:shadow-md">
      <CardHeader className="pb-2">
        <CardTitle className="text-base leading-snug">{project.name}</CardTitle>
      </CardHeader>
      {project.description && (
        <CardContent className="pb-2">
          <p className="line-clamp-3 text-sm text-muted-foreground">
            {project.description}
          </p>
        </CardContent>
      )}
      <CardFooter className="mt-auto flex items-center justify-between pt-4">
        <span className="text-xs text-muted-foreground">
          {formatDistanceToNow(new Date(project.created_at), {
            addSuffix: true,
          })}
        </span>
        <Button
          size="sm"
          variant="ghost"
          className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive"
          onClick={handleDelete}
          disabled={deleting}
          aria-label="Delete project"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </CardFooter>
    </Card>
  );
}
