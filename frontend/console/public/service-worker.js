// Service worker — same-origin dynamic manifest for the PWA.
//
// Why this exists:
//   iOS WebKit silently rejects cross-origin <link rel="manifest"> sources
//   for standalone PWAs and falls back to the static /manifest.json. We
//   need the manifest's start_url to carry the user's token so the
//   home-screen icon can launch with auth context (iOS standalone PWAs
//   have a localStorage that's effectively isolated from Safari).
//
//   This SW lives at the frontend origin and intercepts fetches for
//   /manifest.json. When the page sends us a token via postMessage, we
//   synthesize a manifest with start_url=/app?token=<theirs>. iOS reads
//   this same-origin response just fine.
//
// Token lifecycle inside the SW:
//   - Held in a module-level variable (in-memory) for the fast path.
//   - Set via postMessage from the page on every load (idempotent).
//   - ALSO persisted to the Cache API so it survives SW termination.
//     iOS WebKit kills idle service workers within seconds. The page posts
//     the token on load, but iOS reads /manifest.json at the moment the
//     user taps Share → Add to Home Screen — which is NOT a page load and
//     can happen long after. If the SW was evicted in between, the in-memory
//     token is gone and we'd bake a token-less start_url into the icon,
//     producing the "Access link expired" screen on every launch. Reading
//     the token back from durable storage closes that gap. (SWs have no
//     access to localStorage/sessionStorage, so the Cache API is the store.)

let cachedToken = null;

const STATIC_FALLBACK_START_URL = '/app?source=pwa';

// Durable token store. The Cache API is the only persistent key/value store
// available inside a service worker. We stash the token as the body of a
// Response under a synthetic same-origin request key.
const TOKEN_CACHE = 'raina-auth-v1';
const TOKEN_CACHE_KEY = '/__token__';

async function persistToken(token) {
  try {
    const cache = await caches.open(TOKEN_CACHE);
    if (token) {
      await cache.put(TOKEN_CACHE_KEY, new Response(token));
    } else {
      await cache.delete(TOKEN_CACHE_KEY);
    }
  } catch {
    /* storage unavailable (private mode, quota) — fall back to in-memory */
  }
}

async function loadPersistedToken() {
  try {
    const cache = await caches.open(TOKEN_CACHE);
    const res = await cache.match(TOKEN_CACHE_KEY);
    if (!res) return null;
    const token = await res.text();
    return token || null;
  } catch {
    return null;
  }
}

const BASE_MANIFEST = {
  name: 'Raina',
  short_name: 'Raina',
  description: 'Real-time updates from your daycare',
  scope: '/',
  display: 'standalone',
  orientation: 'portrait',
  background_color: '#fef8f5',
  theme_color: '#8a4f36',
  icons: [
    { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
    { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
    {
      src: '/icons/icon-maskable-512.png',
      sizes: '512x512',
      type: 'image/png',
      purpose: 'maskable',
    },
  ],
};

self.addEventListener('install', () => {
  // Activate immediately on first install — don't wait for old pages to
  // close. Without this, the very first install requires a page reload
  // before the SW intercepts anything.
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  // Claim all open clients so we control them right away (otherwise SW
  // only controls navigations that happen AFTER activation).
  event.waitUntil(self.clients.claim());
});

self.addEventListener('message', (event) => {
  const data = event.data;
  if (!data || typeof data !== 'object') return;
  if (data.type === 'SET_TOKEN' && typeof data.token === 'string') {
    cachedToken = data.token || null;
    // waitUntil keeps the SW alive until the durable write finishes, so a
    // race between the postMessage and an eviction can't lose the token.
    event.waitUntil(persistToken(cachedToken));
  } else if (data.type === 'CLEAR_TOKEN') {
    cachedToken = null;
    event.waitUntil(persistToken(null));
  }
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname !== '/manifest.json') return;

  event.respondWith(buildManifestResponse());
});

// 16 hex chars (64 bits of entropy) is plenty for a per-token identifier
// and keeps the manifest body small.
async function hashToken(token) {
  if (!self.crypto?.subtle) return null;
  try {
    const data = new TextEncoder().encode(token);
    const digest = await self.crypto.subtle.digest('SHA-256', data);
    return Array.from(new Uint8Array(digest))
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('')
      .slice(0, 16);
  } catch {
    return null;
  }
}

async function buildManifestResponse() {
  // Prefer the in-memory token; fall back to the durable copy when the SW
  // was restarted since the page last posted it (the iOS eviction case).
  const token = cachedToken || (await loadPersistedToken());
  let id = '/';                              // default for the no-token fallback
  let startUrl = STATIC_FALLBACK_START_URL;

  if (token) {
    const hash = await hashToken(token);
    // `id` makes iOS treat each user's PWA as a distinct app, so installing
    // a parent PWA on the same device that already has the director PWA
    // doesn't just add a duplicate shortcut to the existing app. Without
    // this, iOS uses scope-based identity and merges PWAs that share scope.
    id = hash ? `/u/${hash}` : `/u`;
    startUrl = `/app?token=${encodeURIComponent(token)}`;
  }

  const manifest = { ...BASE_MANIFEST, id, start_url: startUrl };

  return new Response(JSON.stringify(manifest), {
    headers: {
      'Content-Type': 'application/manifest+json',
      // Prevent iOS from caching a stale (no-token) version
      'Cache-Control': 'no-store',
    },
  });
}
