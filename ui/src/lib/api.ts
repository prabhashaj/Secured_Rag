/**
 * Shared API fetch wrapper for Lexicon AI frontend.
 * Automatically injects Bearer token authentication and handles 401 expiration redirects.
 */
export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = localStorage.getItem('lexicon_auth_token');

  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(path, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    localStorage.removeItem('lexicon_auth_token');
    // Dispatch custom auth event or redirect to trigger re-authentication UI
    window.dispatchEvent(new CustomEvent('auth_session_expired'));
  }

  return res;
}
