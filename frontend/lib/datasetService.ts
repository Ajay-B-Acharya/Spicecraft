const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export interface DatasetCircuit {
  id: string;
  filename: string;
  original_relative_path: string;
  source_repository: string;
  source_repository_url: string;
  source_url: string;
  license_status: string;
  download_status: string;
}

export interface DatasetCircuitsResponse {
  total: number;
  page: number;
  page_size: number;
  circuits: DatasetCircuit[];
}

export interface DatasetCircuitsParams {
  page?: number;
  page_size?: number;
  search?: string;
  repository?: string;
}

export async function fetchDatasetCircuits(
  params: DatasetCircuitsParams = {}
): Promise<DatasetCircuitsResponse> {
  const url = new URL(`${API_BASE}/dataset/circuits`);
  if (params.page)       url.searchParams.set('page',       String(params.page));
  if (params.page_size)  url.searchParams.set('page_size',  String(params.page_size));
  if (params.search)     url.searchParams.set('search',     params.search);
  if (params.repository) url.searchParams.set('repository', params.repository);

  const res = await fetch(url.toString());
  if (!res.ok) {
    throw new Error(`Dataset API error: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<DatasetCircuitsResponse>;
}
