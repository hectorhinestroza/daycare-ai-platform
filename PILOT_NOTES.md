# Pilot Operations Runbook

This file is the operational source of truth for the pilot. It documents
constraints, rollback procedures, and emergency switches for the deployed
environment. Keep it short and accurate — anything that drifts from reality
becomes a hazard.

## Week 1 Status (as of 2026-05-15)

Live pilot site: **Tilly's Tots**, timezone `America/Los_Angeles`.
Mode: **Phase 1 still active** — `CONSENT_GATE_DISABLED=true`, no parents
onboarded yet. The 2-day teacher-only window stretched into a longer
shakedown — flip to Phase 2 only after the open items below are stable.

### Operational changes shipped during the first week

| Issue surfaced | Fix shipped (PR) | What it does |
|---|---|---|
| Pool exhaustion mid-day-1 — `QueuePool limit of size 5 overflow 10 reached`, all requests 500ing | **#65** — bumped `pool_size=20`, `max_overflow=40`, added `pool_recycle=1800`, `pool_timeout=10` in `backend/storage/database.py` | 15-connection pool was too small for ~5 teachers + parent portal polling at 10 s. Now sized for 60 concurrent with a 30 min recycle. |
| Voice transcription got names like **Clara / Loie / Emi** wrong; teachers' own names ended up as kid events | **#66** — Whisper roster prompt + Double-Metaphone fuzzy resolver + teacher-aware extraction prompt | See **Voice Extraction Pipeline** below for the full flow. |
| Director had to copy-paste teacher portal links to preview | **#66** — `Open` button next to each teacher's bootstrap link in Center > Teachers | Mirrors the parent-portal Open button from earlier. |
| Several smaller UI bugs (waitlist tab unused, enrolled vs active confusion, rooms add-form at bottom, +1 phone prefix clunky) | **#64** | Console polish before pilot day. |
| Brand rename "Daycare" → "Raina" in PWA install title and tab title | **#63** | Existing installed PWAs keep old label until re-installed. |
| Local-dev had no way to bypass auth | **#66** — `scripts/seed_local_dev.py` + relies on existing `pilot_auth.py` dev bypass | Run the seed once, start backend with `ENVIRONMENT=development`, `npm run dev` works cold. |

### Open items the director flagged that are NOT yet shipped

- **Teacher pronunciation recording at enrollment** — proposed by the
  director as a stronger fallback than Double-Metaphone. Tracked as a
  TODO in `get_child_by_name` (see Voice Extraction Pipeline §
  Resolver).
- **Teacher name on event cards / in narrative** (#1B in the day-1
  feedback round). Skipped because the new extraction prompt now bakes
  the teacher into the parent-visible `details` text. Revisit if the
  next pilot session shows it's still unclear.

### Known prod state at pilot start

- Single Postgres on Railway (volume was wiped 2026-05-11 after table
  corruption — see "DB recovery" note below); fresh schema bootstrapped
  by the updated `scripts/start.sh` (auto-detects empty DB, runs
  `create_all` + view + stamps Alembic at HEAD).
- One director admin (Hector), no teachers/kids yet at the time of
  writing — populated via the director console once Tilly's Tots is in
  the system.
- `CONSENT_GATE_DISABLED=true` set in Railway env.
- Twilio WhatsApp Sandbox (72-hour re-join, code documented in the
  director guide).

## Hard Constraints

### Single replica only — DO NOT scale

The backend keeps `_command_context` (in-memory dict in `whatsapp.py`) for
WhatsApp `/child` and `/classroom` commands. Scaling above one replica will
cause commands set on replica A to be invisible to replica B, leading to
silent context loss for teachers.

- Railway: ensure the backend service has `Replicas: 1`
- Do not enable autoscaling
- Lifting this limit requires moving `_command_context` to Postgres or Redis
  (deferred to v2)

### Manual migrations before deploy

Do **not** trust `start.sh` to run `alembic upgrade head` during pilot
deploys. Run it manually before each deploy:

```bash
DATABASE_URL=<prod-url> alembic upgrade head
```

Then deploy. This makes migration failures visible before they crash the
application boot.

### Daily Postgres backups

Railway Postgres has automated daily backups. Verify before pilot day:

1. Open Railway → Postgres service → Backups tab
2. Confirm a backup from the last 24 hours exists
3. Trigger a manual backup once so we have a known-good restore point

## Rollback (Railway)

If a deploy is bad:

1. Open Railway → backend service → Deployments tab
2. Find the last known-good deployment
3. Click the three-dot menu → **Redeploy**
4. Wait for health check to go green

For a database migration that needs to be reverted:

```bash
DATABASE_URL=<prod-url> alembic downgrade -1
```

Always verify the downgrade migration body before running it — some
migrations are non-reversible.

## Environment

Required environment variables (production):

- `ENVIRONMENT=production` — flips consent gate from "warn" to "block"
- `DATABASE_URL` — Railway Postgres URL
- `OPENAI_API_KEY`, `OPENAI_ZERO_RETENTION_CONFIRMED`
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_BUCKET`, `AWS_S3_REGION`
- `RESEND_API_KEY` — for consent magic-link email

### Sentry (two DSNs — one per platform)

Sentry uses one project per platform, so we have two DSNs. Both are stored
in Railway env vars (never in git). Empty values make the SDK init a no-op.

| Variable | Set on | Project type |
|---|---|---|
| `SENTRY_DSN` | backend Railway service | Python / FastAPI |
| `VITE_SENTRY_DSN` | frontend Railway service | React (Vite reads at build time) |

Both clients run `before_send` / `beforeSend` PII scrubbers
(`backend/utils/safe_logging.py::pii_scrubber` and
`frontend/console/src/sentry.js::piiScrubber`) that redact known PII
fields (`child_name`, `transcript`, `body`, `caption`, etc.) before any
event leaves the process. We override Sentry's `sendDefaultPii` to
`false` on both sides so IPs, headers, and request bodies aren't auto-
collected.

When rotating DSNs, update Railway only — no code change needed.

### Auth (Phase 2)

| Variable | Set on | Purpose |
|---|---|---|
| `AUTH_TOKEN_SECRET` | backend Railway service | HMAC signing secret for all bearer tokens |
| `APP_BASE_URL` | backend Railway service | Used to build bootstrap URLs |

Generate the secret once with:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Do not rotate** during the pilot — rotating invalidates every issued
token simultaneously and locks every user out.

Phase 4 will add: `EXTRACTION_DISABLED` (kill switch).

## Token Issuance (Phase 2 — Director's Day-One Workflow)

**Before users can access the system,** the director must issue bearer
tokens for every staff member and parent. This is a one-time setup per
user (each token is good for 90 days).

### How tokens flow

1. Director hits `POST /api/admin/tokens/issue` (authenticated as a
   director themselves).
2. Backend returns a `bootstrap_url` like
   `https://your-app/app?token=<long-signed-string>`.
3. Director hands the URL to the user (printed handout, SMS, email).
4. User opens it once on iOS Safari → token is captured to localStorage.
5. User taps Share → Add to Home Screen → done. From then on, tapping
   the icon opens the right portal directly with no re-auth.

### Bootstrapping the very first director

Before any director token exists, you can't call `/api/admin/tokens/issue`.
For the first center, mint a director token manually with a one-shot
script (run from your laptop pointed at the production DB):

```python
# scripts/mint_first_director_token.py — one-shot
from uuid import UUID
from backend.utils.auth_tokens import generate_token

DIRECTOR_ADMIN_ID = UUID("paste-from-prod-admins-table")
CENTER_ID = UUID("paste-from-prod-centers-table")

token, payload = generate_token(
    role="director",
    sub=DIRECTOR_ADMIN_ID,
    center_id=CENTER_ID,
)
print(f"https://your-app/app?token={token}")
print(f"Expires: {payload.expires_at}")
```

A ready-made script lives at `scripts/mint_first_director_token.py`.
Run it from the repo root with the prod env loaded:
```bash
DATABASE_URL='...' \
AUTH_TOKEN_SECRET='...' \
APP_BASE_URL='https://your-app.up.railway.app' \
PYTHONPATH=. \
python scripts/mint_first_director_token.py \
    --admin-id <uuid-from-admins-table> \
    --center-id <uuid-from-centers-table>
```

Hand the URL to the director. From then on, the director uses
`/api/admin/tokens/issue` for every other user.

### Issuing teacher tokens (director console UI)

Teacher bootstrap URLs are generated automatically in the director console.
No curl required for the common case:

1. Open the director console → **Manage → Teachers** tab
2. Each teacher row shows a "Teacher app link" panel with the URL already generated
3. Click **Copy** and send the URL to the teacher (WhatsApp, SMS, etc.)
4. Click **Refresh** (↺) to rotate the URL if a device is lost or the teacher changes phones

The URL is good for 365 days. After it expires (or after a revoke), regenerate
from the same panel.

### Enrolling a child with a parent contact (director console UI)

The **Enroll Child** modal now captures the primary parent in one step:

1. Open **Manage → Children** → **Enroll Child**
2. Fill in the child's details (name, DOB, classroom, allergies)
3. In the **Primary Contact** section enter the parent's name, phone
   (country code defaults to `+1`), and **email** (required — used to
   send the consent magic-link and privacy policy)
4. Submit — the child is created and the parent contact is attached in a
   single request

If you skip the contact section, the child is enrolled without a parent
link. You can add the contact later from the child's profile page.

### Revoking a token

When a teacher leaves, a parent loses their phone, etc.:

```bash
curl -X POST https://your-app/api/admin/tokens/revoke \
  -H "Authorization: Bearer <director-token>" \
  -H "Content-Type: application/json" \
  -d '{"sub": "<user-uuid>", "nonce": "<their-current-nonce>"}'
```

The nonce comes from the response of the original `issue` call (saved
when the token was minted). After revoke, the user's bookmark URL
returns 401 and they see "access expired" — re-issue and hand them a
new URL.

### Deploy ordering for Phase 2

The Phase 2 PR adds auth gates to all existing endpoints. The deploy
ritual matters:

1. Run migrations against the prod DB (adds `revoked_token_nonces` table)
2. Set `AUTH_TOKEN_SECRET` on the backend Railway service
3. Deploy the backend
4. **Before deploying the frontend**, mint the first director token
   (script above) so someone can actually log in
5. Deploy the frontend
6. Open the bootstrap URL on the director's phone, Add to Home Screen
7. Use the director's session to issue tokens for teachers + parents
   via `POST /api/admin/tokens/issue`

## Kill Switches

### `CONSENT_GATE_DISABLED` — Phase 1 (teachers-only) override

For the 2-day teacher-only pilot phase BEFORE parents are onboarded with
paper consent, set on the backend Railway service:

```
CONSENT_GATE_DISABLED=true
```

Effect:
- Voice memos for kids without recorded consent flow normally into the
  events table (instead of going to `pending_consent_queue`)
- Director can monitor activity through their console and the
  "Preview parent view" button on each child
- Every bypass logs `CONSENT_GATE_DISABLED is set — bypassing consent…`
  at WARNING level for compliance grep

**Flip back to `false` before any parent receives a bootstrap URL.**
By the time you onboard parents in Phase 2, the daycare director should
have collected paper consent forms and either inserted them into
`parental_consent` rows manually OR sent the parent through the
`/consent/<token>` magic-link flow.

### Phase 1 → Phase 2 data wipe

After the 2-day pilot, run this against the Railway Postgres to start
clean before parents arrive (preserves the structural records — center,
rooms, teachers, admins — and only wipes the pilot's event/photo/log data):

```sql
BEGIN;

-- Children stay (need their UUIDs for re-enrollment), but if you want a
-- clean slate including children:
--   DELETE FROM parental_consent;
--   DELETE FROM parent_contacts;
--   DELETE FROM children;

-- Pilot-generated activity
DELETE FROM activity_logs;
DELETE FROM daily_narratives;
DELETE FROM photos;
DELETE FROM pending_photos;
DELETE FROM events;
DELETE FROM pending_events;
DELETE FROM processed_messages;
DELETE FROM pending_consent_queue;
DELETE FROM consent_gate_audit;
DELETE FROM ai_api_logs;

COMMIT;
```

Run from the Railway Postgres Query tab, or via `psql "$RAILWAY_DB"`.
Then set `CONSENT_GATE_DISABLED=false`, restart the backend, and onboard
parents per the standard Phase 2 procedure.

### `EXTRACTION_DISABLED` — pause the AI pipeline

When something is wrong with GPT-4o extraction (bad model output, cost
spike, etc.) flip this on the backend Railway service:

```
EXTRACTION_DISABLED=true
```

Effect:
- Voice memos and text notes skip transcription + GPT-4o entirely
- Twilio media is still deleted (zero-retention is independent)
- Teacher gets a "Recording received — pending review" reply
- Each affected webhook logs `extraction.disabled` (warning) with the
  MessageSid for the director to follow up

Flip back to `false` (or remove the var) to resume normal extraction.
No restart needed beyond Railway's deploy.

## Voice Extraction Pipeline

Updated 2026-05-15 (PR #66). This section is the source of truth for how
a WhatsApp voice memo becomes one or more DB events. If you're debugging
"the AI missed the kid's name" or "the AI extracted the wrong event,"
start here.

### End-to-end flow

```
WhatsApp voice memo ──► /twilio webhook (whatsapp.py)
                                 │
                                 ├─► get_children_by_center (roster fetch)
                                 │
                                 ├─► transcribe_audio(audio, prompt=roster_hint)
                                 │       │
                                 │       └─► OpenAI Whisper
                                 │           prompt: "Children at this
                                 │                    daycare: Clara, Loie,
                                 │                    Emi, ..."
                                 │
                                 ├─► extract_events(transcript,
                                 │                  known_children=roster,
                                 │                  teacher_name=teacher.name)
                                 │       │
                                 │       └─► GPT-4o (chat completions)
                                 │           system: extraction rules
                                 │           user:   teacher context + roster
                                 │                   + transcript
                                 │
                                 ├─► For each extracted event:
                                 │     get_child_by_name(child_name)
                                 │       Pass 1: exact case-insensitive
                                 │       Pass 2: prefix match
                                 │       Pass 3: contains match
                                 │       Pass 4: Double-Metaphone phonetic
                                 │       → child_id (or None if ambiguous)
                                 │
                                 ├─► Consent gate (skipped if
                                 │                CONSENT_GATE_DISABLED)
                                 │
                                 └─► create_event_from_base
                                       teacher_id + child_id + details
```

### 1. Whisper transcription with roster hint

`backend/services/transcription.py::transcribe_audio` accepts an optional
`prompt` string and forwards it to OpenAI Whisper. Whisper biases its
output toward terms in the prompt — passing the kid roster materially
improves spelling of unusual names.

The prompt is built in `backend/routers/whatsapp.py` right before the
transcription call:

```python
center_children = get_children_by_center(db, teacher.center_id)
known_names = [c.name for c in center_children if c.name]
whisper_prompt = (
    f"Children at this daycare: {', '.join(known_names)}."
    if known_names else None
)
```

Limits to know:
- Whisper accepts up to ~244 tokens in `prompt` (~1000 chars). At pilot
  scale (one center, max ~30 kids) we're well under that.
- The roster includes ALL active children in the center, not just the
  teacher's room. Cross-room mentions ("Carlos was visiting from the
  older room") need this.

### 2. Extraction with teacher context

`backend/services/extraction.py::extract_events` accepts an optional
`teacher_name`. When set, the user prompt prepends explicit rules:

- Never extract the teacher's own name as a child event.
- The teacher's first-person references ("I", "me", "my") resolve to
  the teacher's name in event `details`.
- When the teacher appears as actor OR recipient in a child event,
  attribute them in `details`. Direction is preserved:

| Transcript | Resulting event |
|---|---|
| `"Emi helped Joii build a tower"` | `child=Joii, details="Built a tower with help from Emi"` |
| `"I read a book to Carlos"` | `child=Carlos, details="Read a book with Emi"` |
| `"Carlos helped me organize the toys"` | `child=Carlos, details="Helped Emi organize the toys"` |
| `"Joii asked me for a hug"` | `child=Joii, details="Asked Emi for a hug"` |

The system prompt (unchanged from earlier) still enforces:
- Always extract every event mentioned.
- Confidence < 0.7 forces director review.
- Incident / medication events ALWAYS go to director review regardless
  of confidence.
- Group phrases ("all kids", "everyone") set `applies_to_all=true`;
  the WhatsApp router then fans the event out to each ACTIVE child in
  the teacher's room.

### 3. Name resolution — `get_child_by_name`

Four sequential passes, defined in
`backend/storage/events_handlers.py::get_child_by_name`. Earlier passes
short-circuit; later passes only run if no unique earlier match.

| Pass | Strategy | Example |
|---|---|---|
| 1 | Exact case-insensitive (`ilike`) | `"Annie Johnson"` → `"Annie Johnson"` |
| 2 | First-name prefix (`Child.name ILIKE '<input> %'`) — only if uniquely matches | `"Annie"` → `"Annie Johnson"` |
| 3 | Contains (`Child.name ILIKE '% <input> %'`) — only if uniquely matches | `"Marie"` → `"Sofia Marie Lopez"` |
| 4 | **Double-Metaphone** phonetic — only if uniquely matches | `"Klara"` → `"Clara"`, `"Emmy"` → `"Emi"` |

Verified empirically against the pilot's tricky names:
- `Clara` ↔ `Klara`
- `Emi` ↔ `Emmy`, `Amy`, `Aimee`, `Ammy`
- `Loie` ↔ `Lowee`, `Lowey`
- `Joii` ↔ `Joey`

Returns `None` on ambiguity (two kids share the same phonetic code).
The caller treats `None` as "send to director review" rather than
silently mis-attributing.

The `metaphone` PyPI package is the only new runtime dep. Import is
wrapped in a `try/except ImportError` so the resolver falls back to the
first 3 passes if the package isn't installed (e.g. in a stripped-down
test env).

#### Future: pronunciation matching (Phase 3)

Director suggested recording how each kid's name is pronounced at
enrollment, and using that audio as the strongest resolution signal.
Tracked as a TODO comment in `get_child_by_name`. Would add a Pass 5
that compares audio embeddings — strongest fallback for names where
Double-Metaphone gives a false negative (e.g. `Emi` vs `Em-ee`, which
have different codes `AM` vs `AMM`).

### 4. Consent gate

After extraction and resolution, each event passes through
`get_child_for_processing` (`backend/utils/consent_gate.py`). During
Phase 1 the gate bypasses via `CONSENT_GATE_DISABLED=true` (see Kill
Switches). In Phase 2 it queries `children_with_active_consent` and
returns `None` for any child without active consent, sending the event
to `pending_consent_queue` instead of the live DB.

### 5. Persistence and downstream

If consent passes, `create_event_from_base` writes the row with:

- `teacher_id` — derived from `teacher.id` (the sender)
- `child_id` — resolved by `get_child_by_name`, may be `None` on
  ambiguity
- `child_name` — what the AI extracted (may differ slightly from the
  resolved Child.name)
- `review_tier` — `teacher` for low-stakes types, `director` for
  incident/medication or confidence < 0.7

The director's queue (`/api/events/pending/teacher`,
`/api/events/pending/director`) reads from this table and triggers the
EOD narrative generation after approval (see `events.py` →
`_refresh_narrative_if_exists`).

### Debugging checklist

When something goes wrong with extraction:

- [ ] Check Sentry for the WhatsApp request span — confirms the audio
  reached the backend.
- [ ] Look for `transcription.completed` log with `transcript_length` —
  confirms Whisper returned text.
- [ ] Look for `extraction.started` and `extraction.completed` logs —
  confirms GPT-4o was called and what it returned.
- [ ] If event saved with `child_id IS NULL`: name resolution failed.
  Query: which passes ran? Use SQL on `events` joined with `children`
  to see what `event.child_name` looks like vs `children.name`.
- [ ] If event was approved but doesn't appear in parent feed: same
  issue — `get_approved_events_for_child` matches on `child_id OR
  exact-name`. Backfill `child_id` manually:
  `UPDATE events SET child_id = '<uuid>' WHERE id = '<event-id>';`

### Kill switches relevant to this pipeline

- `EXTRACTION_DISABLED=true` — short-circuits the whole pipeline.
  Audio is still deleted from Twilio; the teacher gets a "pending
  review" reply. See Kill Switches section above.
- `CONSENT_GATE_DISABLED=true` — bypasses the consent check (Phase 1).

## Privacy Policy

A draft Privacy Policy is served at `/privacy`. The content was
generated from `docs/legal_prd_v1.md §12` and **has not been reviewed
by a lawyer**. Before the first parent receives a bootstrap URL:

1. Send the rendered page (or `frontend/console/src/portals/PrivacyPolicy.jsx`)
   to legal counsel
2. Have them edit the content in place — keep the route at `/privacy`
3. Update the "Last updated" date in the component
4. Remove the "draft pending legal review" tag near the top

The page is reachable from the parent portal footer. The route is
public (no bearer-token gate). It is also linked from `docs/legal_prd_v1.md
Section 11 item 13` (pre-launch checklist).

## Acceptance Test Runbook

_Filled in by Phase 5. Placeholder._

## TODO

- [ ] **Sentry** — DSNs are wired up and PII scrubbing is in place, but we haven't
  validated that errors actually reach the Sentry dashboard end-to-end. Before pilot day:
  1. Trigger a test error on the backend (raise an exception in a route, hit it with curl)
  2. Confirm the event appears in the Sentry project (not filtered by `before_send`)
  3. Set up an alert rule: "new issue → email / Slack within 1 min"
  4. Repeat the smoke test on the frontend (throw in a React component, confirm it lands)
  5. Review the scrubber allowlist in `backend/utils/safe_logging.py::pii_scrubber`
     and `frontend/console/src/sentry.js::piiScrubber` — add any new fields that
     contain child or parent data

## Known Limitations

- Single-replica only (above)
- `_command_context` is in-memory and lost on restart (teachers re-issue
  `/child` after a deploy; documented behavior)
- Auth is HMAC-signed bearer tokens stored in localStorage (Phase 2).
  Vulnerable to XSS in theory; acceptable for pilot scale.
  Passkeys/WebAuthn deferred to v2.

## Regenerating PWA icons

Source of truth: `logo-organic-curator-1024.svg` at the repo root.
Three PNG sizes ship in `frontend/console/public/icons/` (192, 512,
512-maskable). To regenerate after the SVG changes:

```bash
# 1. Render the SVG to a 1024×1024 master via macOS sips
sips -s format png --resampleWidth 1024 \
  logo-organic-curator-1024.svg --out /tmp/logo-master.png

# 2. Resize and emit the three PWA sizes (run from repo root)
source venv/bin/activate && python -c "
from PIL import Image
import os
src = Image.open('/tmp/logo-master.png').convert('RGBA')
out = 'frontend/console/public/icons'
src.resize((192, 192), Image.LANCZOS).save(os.path.join(out, 'icon-192.png'))
src.resize((512, 512), Image.LANCZOS).save(os.path.join(out, 'icon-512.png'))
# Maskable: Android safe-zone is inner 80%; shrink to 70% and pad with brand bg.
BG = (0xfe, 0xf8, 0xf5, 255)
maskable = Image.new('RGBA', (512, 512), BG)
inner = src.resize((360, 360), Image.LANCZOS)
maskable.paste(inner, ((512-360)//2, (512-360)//2), inner)
maskable.save(os.path.join(out, 'icon-maskable-512.png'))
"
```
- Privacy policy page is a stub until Phase 4
