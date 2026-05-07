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

Phase 2 will add: `PARENT_LINK_SECRET` (for signed bookmark tokens).

Phase 4 will add: `EXTRACTION_DISABLED` (kill switch).

## Kill Switches

_Filled in by Phase 4. Placeholder._

## Acceptance Test Runbook

_Filled in by Phase 5. Placeholder._

## Known Limitations

- Single-replica only (above)
- `_command_context` is in-memory and lost on restart (teachers re-issue
  `/child` after a deploy; documented behavior)
- No real auth in v1 — Phase 2 adds signed bearer tokens; passkeys/JWTs
  deferred to v2
- Privacy policy page is a stub until Phase 4
