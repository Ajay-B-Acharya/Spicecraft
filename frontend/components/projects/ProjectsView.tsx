'use client';

import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { FolderKanban } from 'lucide-react';
import { auth } from '@/lib/firebase';
import { useProjects } from '@/hooks/useProjects';
import { Skeleton } from '@/components/ui/skeleton';
import { CreateProjectDialog } from './CreateProjectDialog';
import { ProjectCard } from './ProjectCard';

export function ProjectsView() {
  const router = useRouter();
  const { projects, loading, error, createProject, updateProject, deleteProject } =
    useProjects();

  useEffect(() => {
    const timer = setTimeout(() => {
      if (!auth.currentUser) {
        router.push('/login');
      }
    }, 500);
    return () => clearTimeout(timer);
  }, [router]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">My Projects</h2>
          {!loading && (
            <p className="mt-1 text-sm text-muted-foreground">
              {projects.length} project{projects.length !== 1 ? 's' : ''}
            </p>
          )}
        </div>
        <CreateProjectDialog onCreate={createProject} />
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-36 rounded-xl" />
          ))}
        </div>
      ) : projects.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed py-20 text-center">
          <FolderKanban className="mb-4 h-10 w-10 text-muted-foreground/40" />
          <p className="font-medium">No projects yet</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Create your first project to get started
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onDelete={deleteProject}
              onUpdate={updateProject}
            />
          ))}
        </div>
      )}
    </div>
  );
}
