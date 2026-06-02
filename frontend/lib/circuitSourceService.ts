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

type CircuitSourceApiShape = Partial<CircuitSource> & {
  sourceName?: string;
  sourceUrl?: string;
  imageUrl?: string;
};

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

function normalizeSource(source: CircuitSourceApiShape): CircuitSource {
  return {
    id: String(source.id ?? ''),
    project_id: String(source.project_id ?? ''),
    title: String(source.title ?? ''),
    source_name:
      source.source_name ?? source.sourceName ?? null,
    source_url: source.source_url ?? source.sourceUrl ?? null,
    image_url: source.image_url ?? source.imageUrl ?? null,
    created_at: String(source.created_at ?? new Date().toISOString()),
  };
}

function logApiResponse(operation: string, payload: unknown): void {
  if (process.env.NODE_ENV !== 'production') {
    // Keep the payload visible while debugging the response contract.
    console.log(`[CircuitSources] ${operation}`, payload);
  }
}

export const circuitSourceService = {
  getSources(projectId: string): Promise<CircuitSource[]> {
    return api.get<CircuitSourceApiShape[]>(`/projects/${projectId}/sources`).then(
      (data) => {
        logApiResponse('GET /projects/:id/sources', data);
        return data.map(normalizeSource);
      },
    );
  },
  createSource(projectId: string, data: CreateSourceData): Promise<CircuitSource> {
    return api.post<CircuitSourceApiShape>(`/projects/${projectId}/sources`, data).then(
      (payload) => {
        logApiResponse('POST /projects/:id/sources', payload);
        return normalizeSource(payload);
      },
    );
  },
  updateSource(sourceId: string, data: UpdateSourceData): Promise<CircuitSource> {
    return api.put<CircuitSourceApiShape>(`/sources/${sourceId}`, data).then(
      (payload) => {
        logApiResponse('PUT /sources/:id', payload);
        return normalizeSource(payload);
      },
    );
  },
  deleteSource(sourceId: string): Promise<void> {
    return api.delete(`/sources/${sourceId}`);
  },
};
