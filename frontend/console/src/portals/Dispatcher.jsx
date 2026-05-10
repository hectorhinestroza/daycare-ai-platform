import { useEffect, useState } from 'react';
import {
  apiFetch,
  API_BASE,
  clearAuth,
  getStoredToken,
  setCachedRole,
  setStoredToken,
} from '../api/client.js';
import { installDynamicManifest } from '../utils/dynamicManifest.js';

// /app — first thing users hit when they tap the home-screen icon or open
// a fresh bootstrap URL. Captures ?token= from the URL on first visit,
// verifies it via /api/auth/whoami, then redirects to the right portal.

const ROUTE_FOR_ROLE = {
  parent: (centerId, payload) => `/parent/${centerId}/${payload.child_ids[0]}`,
  teacher: (centerId, payload) => `/teacher/${centerId}/${payload.sub}`,
  director: (centerId) => `/director/${centerId}`,
};

function decideTargetRoute(payload) {
  const builder = ROUTE_FOR_ROLE[payload.role];
  if (!builder) return null;
  return builder(payload.center_id, payload);
}

// Returns one of:
//   { kind: 'ok', payload }
//   { kind: 'expired' }              — token verified bad, user should re-bootstrap
//   { kind: 'network', detail }      — fetch threw or returned 5xx
async function verifyToken() {
  let res;
  try {
    res = await apiFetch('/api/auth/whoami');
    if (res.status === 403) {
      res = await apiFetch('/api/auth/whoami/parent');
    }
  } catch (err) {
    return { kind: 'network', detail: err?.message || String(err) };
  }
  if (res.status === 401 || res.status === 403) return { kind: 'expired' };
  if (!res.ok) {
    return { kind: 'network', detail: `whoami returned HTTP ${res.status}` };
  }
  try {
    const payload = await res.json();
    return { kind: 'ok', payload };
  } catch (err) {
    return { kind: 'network', detail: `whoami response parse failed: ${err?.message || err}` };
  }
}

function ResetButton({ label = 'Try again' }) {
  return (
    <button
      onClick={async () => {
        clearAuth();
        if ('serviceWorker' in navigator) {
          try {
            const regs = await navigator.serviceWorker.getRegistrations();
            await Promise.all(regs.map((r) => r.unregister()));
          } catch {
            /* ignore */
          }
        }
        window.location.href = '/app';
      }}
      className="mt-4 px-4 py-2 rounded-full bg-primary text-on-primary text-sm font-medium hover:opacity-90 transition-opacity"
    >
      {label}
    </button>
  );
}

export default function Dispatcher() {
  const [state, setState] = useState({ status: 'loading' });

  useEffect(() => {
    (async () => {
      try {
        // 1. Capture ?token= if present (first open of bootstrap URL).
        const url = new URL(window.location.href);
        const tokenInUrl = url.searchParams.get('token');
        if (tokenInUrl) {
          setStoredToken(tokenInUrl);
          url.searchParams.delete('token');
          window.history.replaceState(null, '', url.pathname + url.search);
        }

        // 2. Install per-user manifest (any token, fresh or stored).
        const activeToken = tokenInUrl || getStoredToken();
        if (activeToken) {
          installDynamicManifest(activeToken);
        }

        // 3. Bail early if we have no token at all.
        if (!getStoredToken()) {
          setState({
            status: 'expired',
            message:
              'No active access link. Open the bookmark URL provided by your daycare director, or contact them for a new one.',
          });
          return;
        }

        // 4. Verify with the backend.
        const result = await verifyToken();

        if (result.kind === 'expired') {
          clearAuth();
          setState({
            status: 'expired',
            message:
              'Your access link is no longer valid. Please contact your daycare director for a fresh link.',
          });
          return;
        }

        if (result.kind === 'network') {
          setState({
            status: 'error',
            message:
              "We couldn't reach the server to verify your access. Please check your connection and try again.",
            detail: result.detail,
          });
          return;
        }

        // 5. Cache role for next cold start, then redirect.
        const payload = result.payload;
        setCachedRole(payload.role);
        const target = decideTargetRoute(payload);
        if (!target) {
          setState({
            status: 'expired',
            message: 'Unrecognized role on this token. Please contact your director.',
          });
          return;
        }
        window.location.replace(target);
      } catch (err) {
        // Last-resort safety net so we never get stuck forever on "Loading…".
        setState({
          status: 'error',
          message: 'Something went wrong while loading your portal.',
          detail: err?.message || String(err),
        });
      }
    })();
  }, []);

  if (state.status === 'expired') {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center px-6">
        <div className="max-w-md text-center">
          <h1 className="font-headline text-2xl font-semibold text-primary mb-3">
            Access link expired
          </h1>
          <p className="text-on-surface-variant leading-relaxed">{state.message}</p>
          <ResetButton />
        </div>
      </div>
    );
  }

  if (state.status === 'error') {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center px-6">
        <div className="max-w-md text-center">
          <h1 className="font-headline text-2xl font-semibold text-primary mb-3">
            Something went wrong
          </h1>
          <p className="text-on-surface-variant leading-relaxed">{state.message}</p>
          {state.detail && (
            <p className="mt-3 text-xs font-mono text-on-surface-variant/70 break-all">
              {state.detail}
            </p>
          )}
          <p className="mt-3 text-xs text-on-surface-variant/60">
            API: <span className="font-mono">{API_BASE}</span>
          </p>
          <ResetButton />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center">
      <div className="text-on-surface-variant">Loading…</div>
    </div>
  );
}
