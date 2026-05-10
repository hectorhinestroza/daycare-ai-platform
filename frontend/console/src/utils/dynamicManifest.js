// Dynamic per-user PWA manifest — service-worker version.
//
// Background:
//   iOS WebKit (Safari + iOS Chrome + iOS anything) won't honor cross-origin
//   <link rel="manifest"> sources or Blob URLs for standalone PWAs. The
//   only reliable way to ship a per-user manifest on iOS is a service
//   worker on the frontend origin that intercepts /manifest.json fetches.
//
// What this module does:
//   1. Registers the service worker on first call (idempotent)
//   2. Posts the user's token to the SW so it can bake it into the manifest
//      response when iOS asks for /manifest.json during "Add to Home Screen"
//
// Threat model:
//   The token ends up in the home-screen icon's start_url after install.
//   Same surface as putting it in localStorage — anyone holding the device
//   can already read it. Acceptable for pilot.

const SW_PATH = '/service-worker.js';

let registrationPromise = null;

function getRegistration() {
  if (!('serviceWorker' in navigator)) return Promise.resolve(null);
  if (registrationPromise) return registrationPromise;
  registrationPromise = navigator.serviceWorker
    .register(SW_PATH, { scope: '/' })
    .catch((err) => {
      // SW registration can fail (HTTP, dev quirks). Log once, keep going —
      // the static manifest is still served as a fallback.
      // eslint-disable-next-line no-console
      console.warn('[manifest] service worker registration failed', err);
      return null;
    });
  return registrationPromise;
}

function postToken(controller, token) {
  if (!controller) return;
  try {
    controller.postMessage({ type: 'SET_TOKEN', token });
  } catch {
    /* ignore */
  }
}

/**
 * Register the service worker (if not already) and tell it about the
 * current user's token. Idempotent and safe to call on every cold start
 * with the same token.
 *
 * Falsy token is a no-op so callers don't have to guard.
 */
export function installDynamicManifest(token) {
  if (!token) return;

  getRegistration().then(async (reg) => {
    if (!reg) return;

    // Active controller is the fastest path on subsequent loads.
    if (navigator.serviceWorker.controller) {
      postToken(navigator.serviceWorker.controller, token);
    }

    // First-load case: the SW exists in a `installing`/`waiting` state
    // and isn't controlling the page yet. Wait for it to become ready
    // and post then. Without this, the very first "Add to Home Screen"
    // could hit the static manifest before the SW intercepts.
    try {
      await navigator.serviceWorker.ready;
      postToken(navigator.serviceWorker.controller || reg.active, token);
    } catch {
      /* ignore */
    }
  });
}

/**
 * Tell the SW to forget the token. Called when the user logs out or the
 * stored token is cleared via 401 handling.
 */
export function clearDynamicManifest() {
  if (!('serviceWorker' in navigator)) return;
  if (navigator.serviceWorker.controller) {
    try {
      navigator.serviceWorker.controller.postMessage({ type: 'CLEAR_TOKEN' });
    } catch {
      /* ignore */
    }
  }
}
