import { api } from './api';

export interface CircuitSource {
  id: string;
  project_id: string;
  title: string;
  source_name: string | null;
  source_url: string | null;
  image_url: string | null;
  created_at: string;
}

export interface CreateSourceData {
  title: string;
  source_name?: string;
  source_url?: string;
  image_url?: string;
}

export interface UpdateSourceData {
  title?: string;
  source_name?: string;
  source_url?: string;
  image_url?: string;
}

export const circuitSourceService = {
  getSources(projectId: string): Promise<CircuitSource[]> {
    return api.get<CircuitSource[]>(`/projects/${projectId}/sources`);
  },
  createSource(projectId: string, data: CreateSourceData): Promise<CircuitSource> {
    return api.post<CircuitSource>(`/projects/${projectId}/sources`, data);
  },
  updateSource(sourceId: string, data: UpdateSourceData): Promise<CircuitSource> {
    return api.put<CircuitSource>(`/sources/${sourceId}`, data);
  },
  deleteSource(sourceId: string): Promise<void> {
    return api.delete(`/sources/${sourceId}`);
  },
};
