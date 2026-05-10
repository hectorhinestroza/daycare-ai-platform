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
//   - Held in a module-level variable (in-memory).
//   - Set via postMessage from the page on every load (idempotent).
//   - If the SW restarts (rare, but possible after long idle), the next
//     page load re-sends the token before any "Add to Home Screen" tap.

let cachedToken = null;

const STATIC_FALLBACK_START_URL = '/app?source=pwa';

const BASE_MANIFEST = {
  name: 'Daycare Portal',
  short_name: 'Daycare',
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
  } else if (data.type === 'CLEAR_TOKEN') {
    cachedToken = null;
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
  const token = cachedToken;
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
