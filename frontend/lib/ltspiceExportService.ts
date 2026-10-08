import { auth } from './firebase';
import { apiRequest } from './apiError';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

async function authHeaders(): Promise<HeadersInit> {
  const user = auth.currentUser;
  if (!user) throw new Error('Not authenticated');
  const token = await user.getIdToken();
  return {
    Authorization: `Bearer ${token}`,
  };
}

/**
 * Triggers a browser download of the LTspice .asc file for the given circuit.
 *
 * @param circuitId - The circuit's unique identifier.
 * @param filename  - The suggested download filename (e.g. "RC_Low_Pass_Filter.asc").
 */
async function exportAsc(circuitId: string, filename: string): Promise<void> {
  const headers = await authHeaders();

  const blob = await apiRequest(`${API_BASE}/circuits/${encodeURIComponent(circuitId)}/export/asc`, {
    headers,
  }, response => response.blob());
  const url = URL.createObjectURL(blob);

  // Programmatic download via a temporary anchor element
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename.endsWith('.asc') ? filename : `${filename}.asc`;
  try {
    document.body.appendChild(anchor);
    anchor.click();
  } finally {
    anchor.remove();
    // Allow the browser to consume the download before releasing its URL.
    setTimeout(() => URL.revokeObjectURL(url), 10_000);
  }
}

export const ltspiceExportService = { exportAsc };
