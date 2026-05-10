// Dynamic per-user PWA manifest.
//
// Why this exists:
//   On iOS WebKit (Safari, iOS Chrome, iOS Firefox — all forced to use
//   WebKit), a standalone PWA's localStorage is effectively isolated
//   from the Safari tab where the bootstrap URL was opened. The token
//   saved during onboarding doesn't reach the standalone PWA at launch.
//
//   Fix: bake the user's token into the home-screen icon's start_url.
//   When the user taps "Add to Home Screen", iOS reads the manifest at
//   that moment and stores its start_url as the home-screen launcher.
//   Each subsequent home-screen tap opens with `?token=...` already in
//   the URL — the dispatcher captures it fresh into the standalone
//   PWA's own localStorage.
//
// Why we hit a backend endpoint instead of a Blob URL:
//   iOS WebKit silently ignores Blob URLs as <link rel=manifest> sources.
//   A stable backend URL is the only reliable approach. The endpoint
//   returns a real manifest JSON with absolute URLs and the token-bearing
//   start_url. Cross-origin manifests work on iOS 16.4+ when CORS is
//   correctly configured (we set allow_origins=* with no credentials).
//
// Threat model: the token is now visible in the home-screen icon's
// start_url. Same surface as putting it in localStorage — anyone who
// can pick up the device can already read it. Acceptable for pilot.

import { API_BASE } from '../api/client.js';

/**
 * Point the page's <link rel="manifest"> at the per-user backend manifest
 * endpoint. Idempotent — calling repeatedly with the same token rewrites
 * the link href.
 *
 * Falsy token is a no-op so callers don't have to guard.
 */
export function installDynamicManifest(token) {
  if (!token) return;

  const url = `${API_BASE}/api/auth/manifest?token=${encodeURIComponent(token)}`;

  let link = document.querySelector('link[rel="manifest"]');
  if (!link) {
    link = document.createElement('link');
    link.rel = 'manifest';
    document.head.appendChild(link);
  }
  // Cross-origin manifest needs explicit CORS opt-in. Backend sends
  // Access-Control-Allow-Origin: * with no credentials — anonymous mode.
  link.crossOrigin = 'anonymous';
  link.href = url;
}
