// Sentry initialization for the React PWA.
//
// Mirrors the backend's safe_logging.pii_scrubber: any field whose key is
// in PII_FIELD_NAMES has its value replaced with "[redacted]" before the
// event is sent. We override Sentry's default sendDefaultPii to FALSE —
// our pilot privacy posture is "no PII in observability, ever."
//
// DSN is read from VITE_SENTRY_DSN at build time. Empty DSN → init is a
// no-op and the rest of the app behaves identically.

import * as Sentry from '@sentry/react';

const PII_FIELD_NAMES = new Set([
  'child_name',
  'name',
  'transcript',
  'raw_transcript',
  'body',
  'caption',
  'parent_name',
  'parent_email',
  'phone',
]);

const REDACTED = '[redacted]';

function scrubMapping(obj) {
  if (!obj || typeof obj !== 'object') return;
  for (const key of Object.keys(obj)) {
    if (PII_FIELD_NAMES.has(key)) {
      obj[key] = REDACTED;
    }
  }
}

function scrubFrameVars(frames) {
  if (!Array.isArray(frames)) return;
  for (const frame of frames) {
    if (frame && frame.vars) {
      scrubMapping(frame.vars);
    }
  }
}

function piiScrubber(event) {
  if (event && typeof event === 'object') {
    scrubMapping(event.extra);

    if (event.request) {
      scrubMapping(event.request.data);
      scrubMapping(event.request.query_string);
      scrubMapping(event.request.headers);
      scrubMapping(event.request.cookies);
    }

    if (event.exception && Array.isArray(event.exception.values)) {
      for (const value of event.exception.values) {
        if (value && value.stacktrace) {
          scrubFrameVars(value.stacktrace.frames);
        }
      }
    }
  }
  return event;
}

export function initSentry() {
  const dsn = import.meta.env.VITE_SENTRY_DSN;

  // Diagnostics: ALWAYS log init status so we can verify in production
  // whether the SDK loaded, without depending on internal SDK globals
  // like __SENTRY__ that may change between SDK versions. The DSN value
  // itself is never logged — only its length, so the user can confirm
  // the env var made it through the build.
  // eslint-disable-next-line no-console
  console.info(
    '[sentry] init called, dsn length=',
    (dsn || '').length,
    'mode=',
    import.meta.env.MODE,
  );

  if (!dsn) {
    // eslint-disable-next-line no-console
    console.warn('[sentry] VITE_SENTRY_DSN not set — Sentry disabled');
    return;
  }

  try {
    Sentry.init({
      dsn,
      environment: import.meta.env.MODE,
      sendDefaultPii: false,
      beforeSend: piiScrubber,
      // Tracing disabled until we have a need; tune this when activating perf data.
      tracesSampleRate: 0,
    });
    // Expose for ad-hoc testing from the browser console. Removed in v2.
    if (typeof window !== 'undefined') {
      window.Sentry = Sentry;
    }
    // eslint-disable-next-line no-console
    console.info('[sentry] initialized — window.Sentry available for tests');
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error('[sentry] init threw — continuing without Sentry:', err);
  }
}

// Exported for unit tests
export { piiScrubber, PII_FIELD_NAMES };
