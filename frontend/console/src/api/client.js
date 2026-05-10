// Authenticated fetch wrapper.
//
// Reads the bearer token from localStorage and injects it into every API
// call. On 401, wipes the token and redirects the user to /app so the
// dispatcher can show the "access expired" message.
//
// Usage:
//   apiFetch('/api/events/pending/teacher/abc')
//     → GET with Authorization header
//   apiFetch('/api/events/abc/xyz/approve', { method: 'POST' })
//
// All API call sites in api/index.js go through this wrapper.

export const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const TOKEN_KEY = 'dc_token';
const ROLE_KEY = 'dc_role';

export function getStoredToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setStoredToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* localStorage unavailable — silent */
  }
}

export function getCachedRole() {
  try {
    return localStorage.getItem(ROLE_KEY);
  } catch {
    return null;
  }
}

export function setCachedRole(role) {
  try {
    if (role) localStorage.setItem(ROLE_KEY, role);
    else localStorage.removeItem(ROLE_KEY);
  } catch {
    /* silent */
  }
}

export function clearAuth() {
  setStoredToken(null);
  setCachedRole(null);
}

function buildUrl(path) {
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  return `${API_BASE}${path}`;
}

/**
 * fetch() variant that injects Authorization: Bearer <stored token>
 * and bounces the user to /app on 401.
 */
export async function apiFetch(path, options = {}) {
  const token = getStoredToken();
  const headers = { ...(options.headers || {}) };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(buildUrl(path), { ...options, headers });

  if (res.status === 401) {
    // Token is bad — drop it and bounce to dispatcher. The dispatcher
    // will render the "access expired" message.
    clearAuth();
    if (typeof window !== 'undefined' && window.location.pathname !== '/app') {
      window.location.href = '/app';
    }
  }

  return res;
}

/**
 * Convenience helpers — same shape as a typical fetch JSON wrapper.
 */
export async function apiGet(path) {
  const res = await apiFetch(path);
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json();
}

export async function apiPost(path, body) {
  const res = await apiFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}`);
  return res.json();
}

export async function apiPatch(path, body) {
  const res = await apiFetch(path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`PATCH ${path} → ${res.status}`);
  return res.json();
}

export async function apiDelete(path) {
  const res = await apiFetch(path, { method: 'DELETE' });
  if (!res.ok && res.status !== 204) throw new Error(`DELETE ${path} → ${res.status}`);
  return res.status === 204 ? null : res.json();
}
