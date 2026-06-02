'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import { onAuthStateChanged } from 'firebase/auth';
import { auth } from '@/lib/firebase';
import { projectService, type Project } from '@/lib/projectService';
import { DashboardShell } from '@/components/dashboard-shell';
import { SourcesView } from '@/components/sources/SourcesView';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';

export default function ProjectPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [project, setProject] = useState<Project | null>(null);
  const [projectLoading, setProjectLoading] = useState(true);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;

    const unsubscribe = onAuthStateChanged(auth, (user) => {
      if (user) {
        projectService
          .getProject(id)
          .then(setProject)
          .catch(() => setProject(null))
          .finally(() => setProjectLoading(false));
      } else {
        setProjectLoading(false);
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
  }, [id, router]);

  return (
    <DashboardShell>
      <main className="p-6 md:p-8 space-y-6">
        <div>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/dashboard">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Projects
            </Link>
          </Button>
        </div>

        <div>
          {projectLoading ? (
            <Skeleton className="h-9 w-48 rounded-lg" />
          ) : (
            <>
              <h1 className="text-3xl font-semibold tracking-tight">
                {project?.name ?? 'Project'}
              </h1>
              {project?.description && (
                <p className="mt-1 text-muted-foreground">{project.description}</p>
              )}
            </>
          )}
        </div>

        <SourcesView projectId={id} />
      </main>
    </DashboardShell>
  );
}
