import { api } from './api';

export interface SearchResult {
  title: string;
  source_name: string | null;
  source_url: string | null;
  image_url: string | null;
}

type SearchResultApiShape = Partial<SearchResult> & {
  sourceName?: string;
  sourceUrl?: string;
  imageUrl?: string;
};

function normalizeResult(result: SearchResultApiShape): SearchResult {
  return {
    title: String(result.title ?? ''),
    source_name: result.source_name ?? result.sourceName ?? null,
    source_url: result.source_url ?? result.sourceUrl ?? null,
    image_url: result.image_url ?? result.imageUrl ?? null,
  };
}

export const searchService = {
  async search(query: string): Promise<SearchResult[]> {
    const data = await api.get<SearchResultApiShape[]>(
      `/search?q=${encodeURIComponent(query)}`,
    );
    return data.map(normalizeResult);
  },
};
