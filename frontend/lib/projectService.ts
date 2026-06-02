import { api } from './api';

export interface Project {
  id: string;
  firebase_uid: string;
  name: string;
  description: string | null;
  created_at: string;
}

export interface CreateProjectData {
  name: string;
  description?: string;
}

export interface UpdateProjectData {
  name?: string;
  description?: string;
}

export const projectService = {
  getProjects(): Promise<Project[]> {
    return api.get<Project[]>('/projects');
  },

  getProject(id: string): Promise<Project> {
    return api.get<Project>(`/projects/${id}`);
  },

  createProject(data: CreateProjectData): Promise<Project> {
    return api.post<Project>('/projects', data);
  },

  updateProject(id: string, data: UpdateProjectData): Promise<Project> {
    return api.put<Project>(`/projects/${id}`, data);
  },

  deleteProject(id: string): Promise<void> {
    return api.delete(`/projects/${id}`);
  },
};
