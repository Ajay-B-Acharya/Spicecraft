import { auth } from './firebase';
import { apiRequest } from './apiError';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

async function authHeaders(): Promise<HeadersInit> {
  const user = auth.currentUser;
  if (!user) throw new Error('Not authenticated');
  const token = await user.getIdToken();
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  };
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  async get<T>(path: string): Promise<T> {
    return apiRequest(`${API_BASE}${path}`, {
      headers: await authHeaders(),
    }, handleResponse<T>);
  },

  async post<T>(path: string, body: unknown): Promise<T> {
    return apiRequest(`${API_BASE}${path}`, {
      method: 'POST',
      headers: await authHeaders(),
      body: JSON.stringify(body),
    }, handleResponse<T>);
  },

  async put<T>(path: string, body: unknown): Promise<T> {
    return apiRequest(`${API_BASE}${path}`, {
      method: 'PUT',
      headers: await authHeaders(),
      body: JSON.stringify(body),
    }, handleResponse<T>);
  },

  async delete(path: string): Promise<void> {
    return apiRequest(`${API_BASE}${path}`, {
      method: 'DELETE',
      headers: await authHeaders(),
    }, handleResponse<void>);
  },
};
