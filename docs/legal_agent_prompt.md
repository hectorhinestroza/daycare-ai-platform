# Legal Engineering Agent Prompt

> Give this prompt to a coding agent to implement the legal compliance layer
> from `docs/legal_PRD.md`. Issues are ordered by dependency and priority.

---

## System Prompt

You are a backend engineer implementing COPPA compliance and data privacy
engineering for the Daycare AI Platform. This platform collects children's
photos, voice memos, names, DOB, and daily activity data via an AI pipeline.

**Reference document:** `docs/legal_PRD.md` — this is your source of truth.
Every requirement there is a hard gate. Never weaken, skip, or defer a
requirement unless explicitly told to by the product owner.

**Architecture context:**
- Backend: Python 3.11+, FastAPI, PostgreSQL (multi-tenant, `center_id` on every table)
- Storage: AWS S3 for photos and temporary audio
- Auth: magic links only — no passwords
- Schemas: Pydantic models in `/schemas` are the contract
- Tests: pytest, write tests first (TDD)
- Agent context: read `GEMINI.md` at project root for full rules

**Critical rules:**
1. Every API endpoint that writes child data must validate `consent.daily_reports = True` and `consent.revoked_at = None` before accepting
2. Never store child PII in S3 keys, file names, or log messages
3. Audio files have a 72-hour TTL — use S3 Object Lifecycle rules, not cron
4. EXIF stripping happens at upload, before storage — not as a background job
5. Never log prompt content that contains child data

---

## Issues (in dependency order)

### Issue L-1: Parental Consent Schema + API
**Label:** `legal`, `week-4`
**Depends on:** Issue #4 (PostgreSQL schema)

**Description:**
Implement the `ParentalConsent` Pydantic model and PostgreSQL table.
Consent records are **immutable** — updates create new versioned records.

**Acceptance Criteria:**
- [ ] `ParentalConsent` schema in `/schemas/consent.py` matching legal_PRD §4.1
- [ ] PostgreSQL table `parental_consents` with fields: `consent_id`, `center_id`, `child_id`, `parent_id`, `consent_version`, `daily_reports`, `photo_sharing`, `voice_processing`, `ai_training` (default false), `consented_at`, `ip_address`, `revoked_at`, `revoked_reason`
- [ ] No UPDATE operations — only INSERT new versions
- [ ] API endpoints: `POST /consent` (create), `POST /consent/{id}/revoke` (revoke)
- [ ] `GET /consent/{child_id}/current` returns latest non-revoked consent
- [ ] All endpoints filtered by `center_id`
- [ ] Tests: create consent, revoke consent, verify immutability

**Definition of Done:** Consent record can be created and revoked via API. No UPDATE queries exist in the codebase for this table. Tests passing.

---

### Issue L-2: Consent Gate Middleware
**Label:** `legal`, `week-4`
**Depends on:** L-1

**Description:**
Create a reusable `require_consent(child_id, scope)` dependency that
can be injected into any FastAPI endpoint. This is the enforcement layer.

**Acceptance Criteria:**
- [ ] FastAPI dependency `require_consent(child_id: UUID, scope: str)` that checks: (a) consent exists for child, (b) specific scope is `True`, (c) `revoked_at is None`
- [ ] Scopes: `daily_reports`, `photo_sharing`, `voice_processing`, `ai_training`
- [ ] Returns 403 Forbidden with clear error message if consent missing/revoked
- [ ] Applied to: WhatsApp webhook (voice processing), photo upload, event creation, narrative generation
- [ ] Tests: accepted with valid consent, rejected without consent, rejected after revocation

**Definition of Done:** No child data can be written through the API without passing the consent gate. Tests prove all rejection scenarios.

---

### Issue L-3: Photo EXIF Stripping + Secure Storage
**Label:** `legal`, `week-4`
**Depends on:** L-1

**Description:**
Implement server-side EXIF metadata stripping and secure S3 storage for
photos per legal_PRD §4.2.

**Acceptance Criteria:**
- [ ] `Pillow` dependency added; EXIF stripping function in `backend/utils/photo.py`
- [ ] Strips ALL metadata: GPS, device ID, timestamp, camera make/model
- [ ] Re-encodes image without EXIF before writing to S3
- [ ] Validates file type server-side: JPEG, PNG, HEIC only
- [ ] Max file size: 10MB per photo
- [ ] S3 key pattern: `/{center_id}/{child_id}/{date}/{uuid}.jpg` — no PII in paths
- [ ] S3 bucket: private, AES-256 encryption at rest, versioning disabled
- [ ] Pre-signed URLs with 1-hour max expiry for all photo access
- [ ] Access check: requesting user belongs to `center_id`, consent exists, not revoked
- [ ] Tests: upload photo with GPS EXIF → verify metadata stripped; verify S3 key format; verify pre-signed URL expiry

**Definition of Done:** Upload a photo with GPS coordinates → download it → confirm zero EXIF metadata. S3 key contains no child names. Tests passing.

---

### Issue L-4: Audio Retention + Auto-Delete
**Label:** `legal`, `week-4`
**Depends on:** none (can start immediately)

**Description:**
Implement the 72-hour audio retention policy using S3 Object Lifecycle
rules per legal_PRD §4.3.

**Acceptance Criteria:**
- [ ] S3 bucket for temporary audio has lifecycle rule: delete objects after 3 days
- [ ] Audio uploaded to S3 with prefix `audio/{center_id}/{date}/{uuid}.ogg`
- [ ] No child PII in S3 key
- [ ] If transcription fails: audio retained max 7 days (separate lifecycle prefix/tag)
- [ ] Lifecycle rules configured via IaC (Terraform/CDK) or boto3 script in `/infra`
- [ ] Raw audio is NEVER stored in PostgreSQL
- [ ] Deletion logged to append-only audit table with: s3_key, deletion_timestamp, trigger_reason
- [ ] Tests: verify lifecycle policy exists on bucket; verify audio S3 key format

**Definition of Done:** S3 lifecycle rule verified. Audio files auto-deleted after 72 hours. No raw audio in the database.

---

### Issue L-5: AI API Privacy Controls
**Label:** `legal`, `week-2`
**Depends on:** none

**Description:**
Implement prompt sanitization and API call logging per legal_PRD §4.4.
This is partially retroactive — update existing extraction service.

**Acceptance Criteria:**
- [ ] Verify OpenAI account: zero data retention enabled (Settings → Data Controls)
- [ ] Prompt content sent to GPT-4o must NEVER include: child surname, parent contact info, or medical data beyond the specific event
- [ ] Add `sanitize_prompt(transcript, child_context)` function that strips PII before sending to LLM
- [ ] Log every AI API call to `ai_api_logs` table: `model`, `center_id`, `child_id`, `timestamp`, `token_count` — do NOT log prompt/response content
- [ ] Update extraction service to use sanitized prompts + structured logging
- [ ] Tests: verify prompt sanitization strips surnames; verify log record contains no PII

**Definition of Done:** AI API calls are logged without PII. Prompts are sanitized. OpenAI zero retention confirmed.

---

### Issue L-6: Data Retention Enforcement Jobs
**Label:** `legal`, `week-8`
**Depends on:** L-3, L-4

**Description:**
Implement the nightly retention job per legal_PRD §4.5 schedule.

**Acceptance Criteria:**
- [ ] Nightly job runs at 2AM UTC (use APScheduler or similar)
- [ ] Enforces retention schedule:
  - Photos: 12 months after capture OR upon unenrollment (whichever sooner)
  - Event records: 24 months after child unenrollment
  - Audit logs: 3 years
  - Session tokens: 30 days inactive
- [ ] Every deletion logged to append-only `retention_audit` table
- [ ] Retention periods configurable per center via admin settings
- [ ] Parent data deletion request API: `POST /parent/{id}/delete-data` — completes within 5 business days (CCPA)
- [ ] Tests: create expired records → run job → verify deleted + audit log created

**Definition of Done:** Nightly job runs and deletes expired data per schedule. All deletions audited. Tests passing.

---

### Issue L-7: Parent Consent + Onboarding Flow
**Label:** `legal`, `week-4`
**Depends on:** L-1, L-2, Issue #9

**Description:**
Implement the 10-step onboarding flow per legal_PRD §5. No child data
may be stored until all consent steps complete.

**Acceptance Criteria:**
- [ ] Director adds child → system generates unique parent invitation (magic link)
- [ ] Parent clicks link → creates account → reviews Privacy Policy
- [ ] Consent form with 4 separate checkboxes: daily reports, photo sharing, voice processing, AI training
- [ ] AI training checkbox: default unchecked, no incentive offered
- [ ] `ParentalConsent` record created on submission with all required fields
- [ ] Child status transitions: `ENROLLED` → `PENDING_CONSENT` → `ACTIVE`
- [ ] Child cannot receive events until status = `ACTIVE` (API-level enforcement)
- [ ] Parent can revoke consent via portal → immediate effect
- [ ] Tests: full flow from invitation to active; verify blocked before consent

**Definition of Done:** Complete consent-gated onboarding flow. Child data blocked at API level until parent completes consent. Tests passing.

---

### Issue L-8: Privacy Policy + Terms Pages
**Label:** `legal`, `week-9`
**Depends on:** none

**Description:**
Create `/privacy` and `/terms` routes serving COPPA-compliant legal
documents per legal_PRD §4.9.

**Acceptance Criteria:**
- [ ] Privacy Policy page at `/privacy` with all required sections from legal_PRD §4.9
- [ ] Terms of Service page at `/terms`
- [ ] Both pages include: effective date, version number, contact email
- [ ] Privacy Policy includes: complete data list, legal basis, third-party vendors, retention schedule, parent rights
- [ ] Recommend Termly.io or Iubenda for initial generation ($10–20/month)
- [ ] Pages are publicly accessible (no auth required)

**Definition of Done:** Both pages live and accessible. Content reviewed against legal_PRD §4.9 checklist.

---

### Issue L-9: Incident Response Plan
**Label:** `legal`, `week-9`
**Depends on:** none

**Description:**
Document the incident response plan per legal_PRD §6 and implement
emergency security controls.

**Acceptance Criteria:**
- [ ] Incident response document in `docs/incident_response.md`
- [ ] Contains: escalation contacts, S3 bucket isolation procedure, JWT invalidation procedure, parent notification template, FTC breach report URL
- [ ] API endpoint: `POST /admin/emergency/invalidate-tokens` — revokes all active sessions
- [ ] API endpoint: `POST /admin/emergency/lock-s3` — applies deny-all policy to S3 bucket
- [ ] Timeframe compliance: 72-hour FTC notification, 30-day parent notification
- [ ] Tests: verify token invalidation; verify S3 lock

**Definition of Done:** Incident response doc complete. Emergency endpoints functional and tested.

---

## Suggested Sprint Order

```
Sprint 1 (can start now):     L-4 (audio retention), L-5 (AI privacy)
Sprint 2 (after Issue #4):    L-1 (consent schema), L-2 (consent gate), L-3 (photo handling)
Sprint 3 (after Issue #9):    L-7 (onboarding flow)
Sprint 4 (pre-launch):        L-6 (retention jobs), L-8 (legal pages), L-9 (incident response)
```
