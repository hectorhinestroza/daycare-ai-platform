# Pilot Operations Runbook

This file is the operational source of truth for the pilot. It documents
constraints, rollback procedures, and emergency switches for the deployed
environment. Keep it short and accurate — anything that drifts from reality
becomes a hazard.

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

## Acceptance Test Runbook

_Filled in by Phase 5. Placeholder._

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
