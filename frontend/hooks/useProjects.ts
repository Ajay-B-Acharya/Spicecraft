'use client';

import { useCallback, useEffect, useState } from 'react';
import { onAuthStateChanged } from 'firebase/auth';
import { auth } from '@/lib/firebase';
import {
  projectService,
  type CreateProjectData,
  type Project,
  type UpdateProjectData,
} from '@/lib/projectService';

export function useProjects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProjects = useCallback(async () => {
    if (!auth.currentUser) return;
    try {
      setLoading(true);
      setError(null);
      const data = await projectService.getProjects();
      setProjects(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load projects');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      if (user) {
        void fetchProjects();
      } else {
        setProjects([]);
        setLoading(false);
      }
    });
    return unsubscribe;
  }, [fetchProjects]);

  const createProject = useCallback(
    async (data: CreateProjectData): Promise<Project> => {
      const project = await projectService.createProject(data);
      setProjects((prev) => [project, ...prev]);
      return project;
    },
    [],
  );

  const updateProject = useCallback(
    async (id: string, data: UpdateProjectData): Promise<Project> => {
      const updated = await projectService.updateProject(id, data);
      setProjects((prev) => prev.map((p) => (p.id === id ? updated : p)));
      return updated;
    },
    [],
  );

  const deleteProject = useCallback(async (id: string): Promise<void> => {
    await projectService.deleteProject(id);
    setProjects((prev) => prev.filter((p) => p.id !== id));
  }, []);

  return {
    projects,
    loading,
    error,
    fetchProjects,
    createProject,
    updateProject,
    deleteProject,
  };
}
