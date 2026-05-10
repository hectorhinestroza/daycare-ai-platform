// Dynamic per-user PWA manifest.
//
// Why this exists:
//   On iOS, a standalone PWA (Add to Home Screen) has localStorage that's
//   effectively isolated from the Safari tab where the user first opened
//   the bootstrap URL. The token saved during onboarding doesn't reliably
//   appear inside the standalone PWA at launch.
//
//   Fix: bake the user's token into the home-screen icon itself. We swap
//   the page's <link rel="manifest"> to a Blob URL whose `start_url` is
//   `/app?token=<theirs>`. When iOS reads the manifest during "Add to
//   Home Screen", it captures that URL — every subsequent home-screen
//   tap opens with `?token=...` in the URL, and the dispatcher captures
//   it fresh into the PWA's own localStorage.
//
// Threat model: the token is now visible in the home-screen icon's
// start_url. Same surface as putting it in localStorage — anyone who
// can pick up the device can already read it. Acceptable for pilot.

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

let lastBlobUrl = null;

/**
 * Build a per-user manifest as a Blob URL and point the page's
 * <link rel="manifest"> at it. Idempotent — calling repeatedly with the
 * same token rewrites the link with a fresh Blob (the previous one is
 * revoked to avoid leaks).
 *
 * Calling with a falsy token is a no-op so callers don't have to guard.
 */
export function installDynamicManifest(token) {
  if (!token) return;

  // Some environments (SSR, tests without jsdom URL polyfill) don't expose
  // URL.createObjectURL; bail gracefully.
  if (typeof Blob !== 'function' || typeof URL === 'undefined' || !URL.createObjectURL) {
    return;
  }

  const manifest = {
    ...BASE_MANIFEST,
    start_url: `/app?token=${encodeURIComponent(token)}`,
  };

  const blob = new Blob([JSON.stringify(manifest)], {
    type: 'application/manifest+json',
  });
  const url = URL.createObjectURL(blob);

  if (lastBlobUrl) {
    try {
      URL.revokeObjectURL(lastBlobUrl);
    } catch {
      /* ignore */
    }
  }
  lastBlobUrl = url;

  let link = document.querySelector('link[rel="manifest"]');
  if (!link) {
    link = document.createElement('link');
    link.rel = 'manifest';
    document.head.appendChild(link);
  }
  link.href = url;
}
