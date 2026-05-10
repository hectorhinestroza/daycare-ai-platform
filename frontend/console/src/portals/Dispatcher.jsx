import { useEffect, useState } from 'react';
import {
  apiFetch,
  clearAuth,
  getStoredToken,
  setCachedRole,
  setStoredToken,
} from '../api/client.js';
import { installDynamicManifest } from '../utils/dynamicManifest.js';

// /app — first thing users hit when they tap the home-screen icon or open
// a fresh bootstrap URL. Captures ?token= from the URL on first visit,
// verifies it via /api/auth/whoami, then redirects to the right portal.
//
// Token lifecycle:
//   1. Director hands out bootstrap URL: APP_BASE_URL/app?token=<signed>
//   2. User opens it once on iOS Safari → we read ?token, store it,
//      strip the query string, and continue.
//   3. User Adds to Home Screen.
//   4. Tapping the icon hits /app?source=pwa → no ?token param, but
//      the stored one survives. We re-verify on every cold start.
//   5. On any 401 (revoked, expired, tampered) we clear and show the
//      "access expired" message.

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

async function verifyToken() {
  // Staff (teacher/director) and parent use different whoami paths because
  // the staff guard would 403 a parent token. Try staff first; if 403,
  // fall back to the parent path. 401 → token is invalid.
  let res = await apiFetch('/api/auth/whoami');
  if (res.status === 403) {
    res = await apiFetch('/api/auth/whoami/parent');
  }
  if (!res.ok) return null;
  return res.json();
}

export default function Dispatcher() {
  const [state, setState] = useState({ status: 'loading', message: '' });

  useEffect(() => {
    (async () => {
      // 1. Capture ?token= if present (first open of bootstrap URL).
      const url = new URL(window.location.href);
      const tokenInUrl = url.searchParams.get('token');
      if (tokenInUrl) {
        setStoredToken(tokenInUrl);
        url.searchParams.delete('token');
        window.history.replaceState(null, '', url.pathname + url.search);
      }

      // 2. Install per-user manifest (any token, fresh or stored). When the
      //    user does Add to Home Screen, iOS reads this manifest and bakes
      //    `start_url=/app?token=<theirs>` into the home-screen icon. Solves
      //    the iOS standalone-PWA / Safari localStorage isolation issue.
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
      const payload = await verifyToken();
      if (!payload) {
        clearAuth();
        setState({
          status: 'expired',
          message:
            'Your access link is no longer valid. Please contact your daycare director for a fresh link.',
        });
        return;
      }

      // 5. Cache role for next cold start, then redirect.
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
