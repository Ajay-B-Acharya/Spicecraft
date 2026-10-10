export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly detail: unknown = null,
    public readonly retryable = false,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function text(value: unknown): string {
  return typeof value === 'string' || typeof value === 'number' ? String(value) : '';
}

export function formatApiDetail(detail: unknown, depth = 0): string {
  let remaining = 256;
  const seen = new Set<object>();
  const render = (value: unknown, level: number): string => {
    if (level > 8 || --remaining < 0) return '';
    if (value !== null && typeof value === 'object') {
      if (seen.has(value)) return '';
      seen.add(value);
    }
    if (Array.isArray(value)) return value.slice(0, 100).map(item => render(item, level + 1)).filter(Boolean).join('\n\n');
    if (!isRecord(value)) return text(value).slice(0, 2048);
    const lines: string[] = [];
    const message = (text(value.message) || text(value.msg)).slice(0, 2048);
    if (message) lines.push(message);
    for (const field of ['stage', 'code', 'component', 'pin', 'net', 'circuit']) {
      const item = text(value[field]).slice(0, 256);
      if (item) lines.push(`${field[0].toUpperCase()}${field.slice(1)}: ${item}`);
    }
    const location = value.loc ?? value.location;
    if (Array.isArray(location)) lines.push(`Field: ${location.slice(0, 32).map(item => text(item).slice(0, 256)).filter(Boolean).join('.')}`);
    for (const field of ['diagnostics', 'errors', 'detail']) {
      if (value[field] !== undefined) {
        const nested = render(value[field], level + 1);
        if (nested) lines.push(nested);
      }
    }
    return lines.join('\n');
  };
  return render(detail, depth).slice(0, 16_384);
}

export async function responseError(response: Response): Promise<ApiError> {
  let detail: unknown = null;
  try {
    const body: unknown = await response.json();
    detail = isRecord(body) && 'detail' in body ? body.detail : body;
  } catch {
    // Non-JSON gateway pages are not suitable user-facing diagnostics.
  }
  const retryable = isRecord(detail) && typeof detail.retryable === 'boolean'
    ? detail.retryable : [408, 429, 502, 503, 504].includes(response.status);
  return new ApiError(formatApiDetail(detail) || `Request failed (HTTP ${response.status}).`, response.status, detail, retryable);
}

/** No automatic replay: a timed-out write may already have reached the server. */
export async function apiRequest<T>(
  url: string, init: RequestInit, consume: (response: Response) => Promise<T>, timeoutMs = 120_000,
): Promise<T> {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  if (init.signal?.aborted) cancel();
  else init.signal?.addEventListener('abort', cancel, { once: true });
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { ...init, signal: controller.signal });
    if (!response.ok) throw await responseError(response);
    return await consume(response);
  } catch (error) {
    if (init.signal?.aborted) throw new ApiError('Request cancelled. Your input is preserved.', 0);
    if (controller.signal.aborted) throw new ApiError('Request timed out. Your input is preserved; check the saved state before retrying.', 408, null, true);
    if (error instanceof ApiError) throw error;
    if (error instanceof TypeError) throw new ApiError('Unable to reach the API. Your input is preserved; check your connection and retry.', 0, null, true);
    if (error instanceof SyntaxError) throw new ApiError('The API returned malformed JSON. Your input is preserved; retry the request.', 502, null, true);
    throw error;
  } finally {
    clearTimeout(timer);
    init.signal?.removeEventListener('abort', cancel);
  }
}
