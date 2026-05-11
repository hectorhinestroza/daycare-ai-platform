# Pilot Handoff

Everything that was built during the pilot phases, what's still on you,
and how to operate the system on pilot day.

For day-to-day ops (rollback, env vars, runbook), see `PILOT_NOTES.md`.
For deferred bugs and v2 follow-ups, see
`~/.claude/projects/.../memory/pilot_deferred_bugs.md`.

---

## 1. What was built

### Phase 0 — foundation
- Sentry SDK wired on backend + frontend with empty-DSN no-op fallback
- `before_send` PII scrubber (Python) + `beforeSend` PII scrubber (React) redact
  `child_name`, `transcript`, `body`, `caption`, `parent_name`, `parent_email`,
  `phone` from any event leaving the process
- `backend/utils/safe_logging.py` — `safe_log()` helper that refuses PII fields
  (raises in dev, drops in prod). All new logs go through this.
- `PILOT_NOTES.md` operations runbook
- `.env.example` template

### Phase 1 — critical fixes
- **PII scrubbed from existing log sites** in `whatsapp.py`, `extraction.py`,
  `narrative.py`, `scheduler.py`, `transcription.py`. No more child names,
  transcripts, raw LLM responses, or phone numbers in stdout.
- **MessageSid dedup** — Twilio retries no longer cause duplicate events.
  New `processed_messages` table; nightly cleanup at 03:00 UTC.
- **Twilio webhook signature verification** — `/webhook/whatsapp` rejects
  requests without a valid `X-Twilio-Signature` in production. Dev/test bypass
  preserved for the test suite.
- **AsyncOpenAI migration** — concurrent voice memos no longer serialize.
  Two voice memos arriving simultaneously both process within Twilio's
  webhook timeout instead of one timing out.
- **Consent gate wired into the events path** — events for kids without active
  parental consent are queued in `pending_consent_queue` instead of persisted.
- **`parental_consent` unique-constraint fix** — withdrawal/re-grant cycles
  now work; previously failed after the second withdrawal.

### Phase 2 — auth + PWA
- **HMAC-signed bearer tokens** signed with `AUTH_TOKEN_SECRET`. One unified
  token format for all three roles (parent, teacher, director). 90-day expiry
  for parents, 365-day for teachers (set by UI).
- **`require_role()` FastAPI dependency** with four guards: `"staff"`,
  `"director"`, `"parent"`, `"any"`. Applied to every router except the
  Twilio webhook (sig is its own auth) and the consent magic-link flow.
- **`POST /api/admin/tokens/issue`** (director-only) — mints a bootstrap URL
  for any role.
- **`POST /api/admin/tokens/revoke`** (director-only) — revokes a token by
  `(sub, nonce)`.
- **`/app` dispatcher** — captures bootstrap token from URL, verifies via
  whoami, routes to portal. Token stored in **sessionStorage** (per-tab,
  prevents cross-tab token contamination).
- **PWA manifest + icons** (192, 512, 512-maskable) generated from
  `logo-organic-curator-1024.svg`.
- **Same-origin dynamic manifest via service worker** — solves iOS WebKit's
  rejection of cross-origin manifests and Blob URLs. Each user's PWA install
  has their own `start_url=/app?token=<theirs>` baked into the home-screen
  icon, with a unique `id` so iOS treats per-user PWAs as distinct apps.
- **Frontend API client** auto-injects `Authorization: Bearer` from
  sessionStorage and bounces to `/app` on 401.
- **First-director bootstrap script** — `scripts/mint_first_director_token.py`
  for the chicken-and-egg "you need a director token to issue one" problem.
- **`addToast` memoized** — fixed the 10-req/s 403 storm caused by re-renders
  on every error toast.

### Phase 3 — observability
- **`request_id` ContextVar** — every `safe_log()` call inside an HTTP request
  auto-includes the request ID, no callsite changes
- **Twilio media deletion with retry** — 3 attempts, exponential backoff,
  hashed URL for log correlation. Replaces the fire-and-forget pattern that
  could leave audio on Twilio's CDN.
- **Structured pipeline logs** at every stage boundary:
  `webhook.received`, `webhook.teacher_resolved`, `transcription.completed`,
  `extraction.started`, `extraction.completed`, `consent_gate.passed`,
  `consent_gate.blocked`, `event.approved`, `event.rejected`,
  `event.batch_approved`, `narrative_refresh.{triggered,completed,failed}`,
  `scheduler.eod_tick`, `twilio.media_deletion.{succeeded,failed}`. All
  metadata-only, no PII.

### Phase 4 — operational guardrails
- **`EXTRACTION_DISABLED` kill switch** — flip the env var on Railway to
  pause GPT-4o extraction. Voice memos still arrive, get acknowledged to
  teachers, and Twilio media still deletes; nothing flows to events table.
- **`/health` upgrade** — reports `git_sha`, `uptime_seconds`,
  `extraction_disabled`, legal DPA fields. Dockerfile `HEALTHCHECK` directive.
- **`/privacy` page** — draft policy at a stable URL, footer link from
  parent portal, COPPA §12 disclosures covered.

### Tangential fixes that came up
- iOS PWA standalone localStorage isolation (service-worker dynamic manifest)
- Two-click "mint + copy" pattern in parent contact rows (iOS clipboard rule)
- Per-contact bootstrap URLs visible inline (replaces the broken legacy
  parent-portal link)
- Teacher bootstrap URLs in TeachersPanel (PR #44)
- Duplicate teacher phone → 409 instead of 500 (PR #45)
- Real "Remove" button for teachers, soft-delete preserves audit trail (PR #45)
- Dispatcher error visibility — no more silent "stuck at Loading…" (PR #42)

**Total: 18 PRs merged across 4 pilot phases plus tangential fixes. 228 backend
tests, frontend build clean.**

---

## 2. Pre-pilot-day checklist

Do these before the first director / parent gets a bootstrap URL.

### Environment

- [ ] Confirm **Railway backend service** env vars are set:
  - [ ] `AUTH_TOKEN_SECRET` (generated once, do not rotate during pilot)
  - [ ] `APP_BASE_URL` (frontend domain, no trailing slash — e.g.
        `https://console.raina-pilot.com`)
  - [ ] `SENTRY_DSN` (FastAPI project DSN — see Sentry section below)
  - [ ] `ENVIRONMENT=production`
  - [ ] `EXTRACTION_DISABLED=false` (or unset — default is false)
- [ ] Confirm **Railway frontend service** env vars:
  - [ ] `VITE_API_URL` (backend Railway URL, no trailing slash)
  - [ ] `VITE_SENTRY_DSN` (React project DSN — see Sentry section)
- [ ] Run `alembic upgrade head` against prod DB after each deploy (see PILOT_NOTES)
- [ ] Single-replica constraint on backend service (`Replicas: 1`)
- [ ] Postgres backups verified — at least one backup from the last 24h

### Auth

- [ ] At least one row in `admins` table for the pilot center (director's record)
- [ ] First director bootstrap URL minted via
      `scripts/mint_first_director_token.py` and handed to the director
- [ ] Director, on their phone:
  - [ ] Opens bootstrap URL in Safari → lands in director portal
  - [ ] Adds to Home Screen → tap icon → opens director portal directly
- [ ] For each teacher: director uses **Center → Teachers** panel → copy each
      teacher's bootstrap URL → send to their phone → they install
- [ ] For each parent: director uses **Center → Children → expand profile →
      per-parent-contact panel** → copy bootstrap URL → send to parent →
      they install

### Legal

- [ ] **`/privacy` page reviewed and approved by a lawyer.** The current
      content is a draft; replace `frontend/console/src/portals/PrivacyPolicy.jsx`
      with the approved text and remove the "draft pending legal review" tag.
- [ ] Privacy policy URL linked from the **printed consent form** as well
      (not just the parent portal footer)
- [ ] All Section 11 pre-launch items from `docs/legal_prd_v1.md` checked off
- [ ] Paper consent forms collected and corresponding `parental_consent` rows
      inserted in prod DB for every enrolled child

### Observability

- [ ] Sentry receiving events from both projects (see verification in Sentry section)
- [ ] `before_send` scrubber confirmed working — raise a test exception with a
      transcript containing a real name, confirm `[redacted]` shows in Sentry
- [ ] Alert rules configured in Sentry for:
  - [ ] Any unhandled exception
  - [ ] `consent_gate.blocked` log (would indicate consent missed in onboarding)
  - [ ] `twilio.media_deletion.failed` log (compliance — should be near zero)
  - [ ] Any HTTP 5xx

### Acceptance tests (manual, run against deployed env)

These are the smoke tests from `.private/pilot_checklist.md §5`. Run them all
on the deployed environment before flipping to "pilot live."

- [ ] `curl -X POST https://backend/webhook/whatsapp` (no signature) → 403
- [ ] Send a real WhatsApp voice memo via Twilio Sandbox → event appears in
      review queue, no PII (e.g. child name) in stdout logs
- [ ] Same MessageSid posted twice within 1 second → exactly one event created
- [ ] Voice memo for a child without consent (with `ENVIRONMENT=production`) →
      goes to `pending_consent_queue`, NOT events table
- [ ] Parent A's bootstrap URL accessing parent B's child via URL manipulation → 403
- [ ] Revoke a parent's token via API → next request returns 401, PWA shows
      "Access link expired" screen
- [ ] iOS: bootstrap URL → Add to Home Screen → tap icon → opens portal directly
- [ ] Upload a photo with EXIF, download from S3, verify EXIF stripped (`exiftool`)
- [ ] `EXTRACTION_DISABLED=true` → voice memo gets "pending review" reply, no
      event created. Flip back to false → next memo processes normally.

---

## 3. Sentry onboarding

You set up two Sentry projects earlier (React + Python/FastAPI) and have both
DSNs. Here's the operating model.

### Concepts in 60 seconds

- **Issue** = a deduplicated group of similar errors. Sentry stashes the first
  occurrence and the most recent, plus a count
- **Event** = one single error/log occurrence. Issues have many events
- **Release** = a deploy. Set this via the `release` option in init for
  release-tagged tracking (we don't do this yet — see "Next steps")
- **Performance** = APM/tracing. Disabled (we set `tracesSampleRate: 0`).
  Enable only if you want span-level performance data
- **before_send hook** = the only chance to mutate or drop events before they
  ship. Our `pii_scrubber` runs here

### First five minutes in the Sentry UI

1. Log in at https://sentry.io with your credentials
2. Top-left org switcher → confirm you're in the right org
3. Sidebar **Projects** → you should see two:
   - The React project (the iOS-blocked one was the first one created)
   - The FastAPI/Python project
4. Click each → **Settings** (gear icon) → **Client Keys (DSN)** → confirm
   the DSN matches what's in your Railway env vars
5. Sidebar **Issues** → empty until something errors. Click **All Unresolved**
   filter; when an error fires, it appears here

### Verifying the PII scrubber works (do this BEFORE pilot day)

This is the most important verification. The scrubber is the legal/ethical
backbone of having any observability tool at all.

**Backend test** (you do this on a deployed staging or prod with real DSN):

1. SSH into Railway shell, or temporarily add a debug endpoint, or do this
   locally with a real DSN set
2. Send a WhatsApp voice memo that mentions a name, **and** inject a temporary
   exception inside `extract_events()` like:
   ```python
   if "Annie" in transcript:
       raise RuntimeError("test sentry scrubber")
   ```
3. Sentry UI → Issues → click the new "test sentry scrubber" issue
4. Look at the **Tags** tab and **Additional Data** tab and **Stack Trace** tab:
   - Anywhere the stack-frame `vars` would have shown `transcript`,
     `child_name`, etc. you should see `[redacted]`
   - **No occurrence of the literal name "Annie" anywhere in the event**
5. If you see "Annie" anywhere → the scrubber failed. Stop the pilot until fixed.
6. Remove the test exception, redeploy

**Frontend test** (do this on staging):

1. Open the parent portal in Chrome desktop
2. DevTools console:
   ```js
   Sentry.captureException(new Error("scrubber test"), {
     extra: { child_name: "Annie", transcript: "Annie ate lunch" }
   });
   ```
3. Sentry UI → Issues → new "scrubber test" event → check Additional Data →
   `child_name` and `transcript` should both be `[redacted]`

### Setting up the four pilot alerts

Sidebar → **Alerts** → **Create Alert Rule**

For each:

1. **Any unhandled 5xx**
   - When: An issue is first seen
   - Filter: `level:error` (or use Issue Alert defaults)
   - Action: Email yourself (and director if applicable)

2. **`consent_gate.blocked` events**
   - When: An event matches conditions
   - Filter: `message contains "consent_gate.blocked"` (Sentry will index our
     structured log lines as messages)
   - Threshold: more than 0 in 1 hour
   - Action: Email — this should be near-zero in practice; if it fires, the
     director needs to chase down a missing consent

3. **`twilio.media_deletion.failed`**
   - Same shape as above with `message contains "twilio.media_deletion.failed"`
   - Threshold: more than 1 in 24 hours (occasional blip is OK; a pattern is not)

4. **Frontend uncaught error**
   - Project: React project
   - When: An issue is first seen
   - Action: Email

### Daily routine during the first 72 hours

- **Morning:** open Sentry → Issues → All Unresolved → triage anything new
- **Spot-check** the request-id correlation: pick a random event from the
  backend, find the `request_id`, search Issues for that ID to see the full
  request trail
- **Watch for compliance signals:** any `twilio.media_deletion.failed` or
  consent-gate block patterns

### Things NOT to do

- Don't enable `sendDefaultPii: true`. We explicitly override it to `false`
  in both SDKs — flipping it on would have Sentry auto-collect IP addresses,
  cookies, request bodies, and headers, bypassing our scrubber on some paths
- Don't change `before_send` / `beforeSend` without re-running the verification
  test above. The scrubber is the single point of failure for PII protection
- Don't bump `tracesSampleRate` above 0 until you've thought through whether
  performance traces could capture PII in span attributes (they can —
  request bodies and SQL queries can land in trace spans)

### Next steps (not blocking pilot day)

- **Release tagging.** Set `release: GIT_COMMIT_SHA` in both SDK inits. Then
  Sentry can correlate errors to specific deploys and run regressions
- **Source maps for the frontend.** Otherwise stack traces show minified JS
- **Slack integration.** Pages director on critical issues without email lag

---

## 4. Where to find things

| You want to | File |
|---|---|
| Run an emergency rollback | `PILOT_NOTES.md` → Rollback section |
| Flip the AI kill switch | `PILOT_NOTES.md` → Kill Switches |
| Issue a token to a new user | Director portal → Center → Teachers/Children panels (per-contact button) |
| Mint the *first* director token | `scripts/mint_first_director_token.py` |
| Revoke a token | `POST /api/admin/tokens/revoke` (curl example in PILOT_NOTES) |
| Regenerate PWA icons after logo change | `PILOT_NOTES.md` → Regenerating PWA icons |
| See deferred bugs to address before pilot | `pilot_deferred_bugs.md` memory file |
| Read the pilot checklist (source of truth) | `.private/pilot_checklist.md` |
| Read the legal PRD | `.private/legal_prd_v1.md` |
