// Authenticated fetch wrapper.
//
// Token storage: sessionStorage, not localStorage.
// Why: localStorage is shared across every browser tab on the same origin.
// Opening a parent bootstrap URL in a new tab would overwrite the
// director's token in localStorage and immediately break the director
// tab — every subsequent API call hit a 403 because the (now parent)
// token didn't match the director's role guard. sessionStorage is
// per-tab, so director and parent tabs each keep their own auth context
// without clobbering each other.
//
// Persistence in PWA mode: each home-screen launch is its own session
// and starts with empty sessionStorage, but the dynamic manifest's
// start_url is /app?token=<theirs> — the dispatcher captures the token
// from the URL on every cold start, so PWA users never notice.
//
// Persistence in plain-browser mode: sessionStorage survives refresh
// (F5) within the same tab. Closing the tab clears it — to come back,
// the user re-opens their bootstrap URL.

export const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const TOKEN_KEY = 'dc_token';
const ROLE_KEY = 'dc_role';

// One-time migration: if a previous version stored the token in
// localStorage, hoist it to sessionStorage on first read and clear the
// old copy. After every active tab has gone through this once, no more
// localStorage state remains.
function migrateLegacyKey(key) {
  try {
    if (sessionStorage.getItem(key)) return;
    const legacy = localStorage.getItem(key);
    if (legacy) {
      sessionStorage.setItem(key, legacy);
      localStorage.removeItem(key);
    }
  } catch {
    /* private mode, etc — silent */
  }
}

export function getStoredToken() {
  try {
    migrateLegacyKey(TOKEN_KEY);
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setStoredToken(token) {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
    // Defensive: also clear any stale localStorage copy from older builds.
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* sessionStorage unavailable — silent */
  }
}

export function getCachedRole() {
  try {
    migrateLegacyKey(ROLE_KEY);
    return sessionStorage.getItem(ROLE_KEY);
  } catch {
    return null;
  }
}

export function setCachedRole(role) {
  try {
    if (role) sessionStorage.setItem(ROLE_KEY, role);
    else sessionStorage.removeItem(ROLE_KEY);
    localStorage.removeItem(ROLE_KEY);
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
