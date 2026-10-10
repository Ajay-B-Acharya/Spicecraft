'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
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

  const contextRevision = useRef(0);
  const requestRevision = useRef(0);

  const fetchProjects = useCallback(async () => {
    const revision = ++requestRevision.current;
    if (!auth.currentUser) return;
    try {
      setLoading(true);
      setError(null);
      const data = await projectService.getProjects();
      if (revision === requestRevision.current) setProjects(data);
    } catch (err) {
      if (revision === requestRevision.current) setError(err instanceof Error ? err.message : 'Failed to load projects');
    } finally {
      if (revision === requestRevision.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      contextRevision.current++;
      requestRevision.current++;
      setProjects([]);
      setError(null);
      setLoading(Boolean(user));
      if (user) void fetchProjects();
    });
    return () => {
      contextRevision.current++;
      requestRevision.current++;
      unsubscribe();
    };
  }, [fetchProjects]);

  const createProject = useCallback(
    async (data: CreateProjectData): Promise<Project> => {
      const revision = contextRevision.current;
      const project = await projectService.createProject(data);
      if (revision !== contextRevision.current) return project;
      requestRevision.current++;
      setLoading(false);
      setProjects((prev) => [project, ...prev.filter((item) => item.id !== project.id)]);
      return project;
    },
    [],
  );

  const updateProject = useCallback(
    async (id: string, data: UpdateProjectData): Promise<Project> => {
      const revision = contextRevision.current;
      const updated = await projectService.updateProject(id, data);
      if (revision !== contextRevision.current) return updated;
      requestRevision.current++;
      setLoading(false);
      setProjects((prev) => prev.map((p) => (p.id === id ? updated : p)));
      return updated;
    },
    [],
  );

  const deleteProject = useCallback(async (id: string): Promise<void> => {
    const revision = contextRevision.current;
    await projectService.deleteProject(id);
    if (revision !== contextRevision.current) return;
    requestRevision.current++;
    setLoading(false);
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
