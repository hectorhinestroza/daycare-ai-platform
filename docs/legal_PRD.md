# Legal Compliance PRD — Children's Data & Privacy
## Daycare AI Operations Platform
**Version:** 1.0  
**Date:** March 21, 2026  
**Status:** MANDATORY — implement before first paying customer  
**Companion to:** Main PRD v2.0 (Daycare AI Operations Platform)

---

## 1. Purpose & Scope

This document defines all legal engineering requirements for handling
children's personal data — including photos, voice audio, daily activity
records, and behavioral notes — for the Daycare AI Operations Platform.

This is not optional guidance. Every requirement in this document is a
hard gate. No feature that touches child data may ship without satisfying
the applicable requirements in this PRD.

---

## 2. Regulatory Framework

### 2.1 Primary Law: COPPA (Children's Online Privacy Protection Act)

- Applies to all online services that collect personal information from
  children under 13
- The platform is a covered operator: it collects photos, voice audio,
  names, ages, and behavioral data of children under 13
- **Amended Rule effective: April 22, 2026** — stricter consent,
  retention limits, and AI training prohibitions now in force
- Enforcement: FTC — civil penalties up to $53,088 per violation per
  child per day
- The school/FERPA exception does NOT apply: daycares are not covered
  educational institutions under FERPA. Individual verifiable parental
  consent is required for every child.

### 2.2 Secondary Laws (US)

| Law | Jurisdiction | Relevance |
|-----|-------------|-----------|
| FERPA | Federal | Does NOT apply — daycares are not schools |
| CCPA/CPRA | California | Applies if any CA centers onboard |
| NY SHIELD Act | New York | Applies (HQ state) — data breach notification |
| IL BIPA | Illinois | Applies if storing facial recognition or biometric data |
| TX SCOPE Act | Texas | Applies if TX centers onboard — student data protections |
| WA My Health MY Data Act | Washington | Applies to health/behavioral data |

### 2.3 International (Future)

- GDPR (EU): Do not onboard EU centers in V1. Architecture must support
  GDPR Article 8 (parental consent for children under 16) before any
  EU expansion.
- PIPEDA (Canada): Do not onboard Canadian centers in V1.

---

## 3. What Constitutes "Personal Information" Under COPPA

The following data types collected by this platform are explicitly
classified as COPPA-covered personal information. Treat each category
with the full set of requirements in Section 4.

| Data Type | COPPA Classification | Collected By Platform |
|-----------|---------------------|----------------------|
| Child's full name | Personal information | Yes — enrollment |
| Child's photo | Personal information | Yes — teacher uploads |
| Voice recording | Personal information | Yes — teacher voice memos |
| Age / date of birth | Personal information | Yes — enrollment |
| Daily activity events | Personal information | Yes — AI structured output |
| Behavioral/incident notes | Personal information | Yes — AI structured output |
| GPS/location metadata in photos | Geolocation = personal information | Yes — EXIF metadata in uploads |
| Parent name + contact | Personal information | Yes — enrollment |
| Health/allergy information | Personal information | Yes — child profile |

---

## 4. Engineering Requirements

### 4.1 Verifiable Parental Consent (VPC)

**Requirement:** Before any child's personal information is stored,
processed, or transmitted, the platform MUST obtain and record
verifiable parental consent.

**Implementation:**

- [ ] Consent flow is mandatory at center onboarding, per child
- [ ] Consent must be obtained by the parent/legal guardian, not the
  daycare director
- [ ] Consent form must clearly describe: what data is collected,
  how it is used, who it is shared with, and retention period
- [ ] Consent must be affirmative (opt-in checkbox, not pre-checked)
- [ ] Separate consent checkbox required for: (a) daily reports,
  (b) photo sharing, (c) voice processing, (d) AI model training
  (see Section 4.6)
- [ ] Consent records must be stored with: parent name, date/time of
  consent, IP address, consent version number, and child ID
- [ ] Consent records must be immutable — no updates, only versioned
  replacements with full audit trail
- [ ] Parent must be able to revoke consent at any time via the
  parent portal with immediate effect

**Consent Record Schema (Pydantic):**
```python
class ParentalConsent(BaseModel):
    consent_id: UUID
    center_id: UUID          # multi-tenant isolation
    child_id: UUID
    parent_id: UUID
    consent_version: str     # e.g. "2026-04-01-v1"
    daily_reports: bool
    photo_sharing: bool
    voice_processing: bool
    ai_training: bool        # default False, explicit opt-in only
    consented_at: datetime
    ip_address: str
    revoked_at: Optional[datetime] = None
    revoked_reason: Optional[str] = None
```

### 4.2 Photo Handling Requirements

**At upload (server-side, before storage):**

- [ ] Strip ALL EXIF metadata from every uploaded image — including GPS
  coordinates, device ID, timestamp, and camera make/model
- [ ] Use `Pillow` (Python) or `sharp` (Node) to re-encode image without
  EXIF before writing to S3
- [ ] Validate file type server-side (accept only JPEG, PNG, HEIC)
- [ ] Enforce max file size: 10MB per photo
- [ ] Log upload event: center_id, uploader_id, child_id(s) tagged,
  timestamp, original filename (do not store)

**Storage:**

- [ ] All photos stored in AWS S3 (or equivalent) with:
  - Bucket policy: private, no public access
  - Encryption at rest: AES-256
  - Versioning disabled (no accidental exposure of deleted files)
  - Server-side encryption enabled
- [ ] S3 keys must follow pattern: `/{center_id}/{child_id}/{date}/{uuid}.jpg`
  — never use child name or any PII in file paths
- [ ] Photos must NEVER be stored in the primary PostgreSQL database
  — store S3 key references only

**Access control:**

- [ ] Photo URLs must be pre-signed S3 URLs with max 1-hour expiry
- [ ] Pre-signed URLs generated only after verifying: requesting user
  belongs to center_id, consent exists for child_id, consent not revoked
- [ ] No permanent/public photo URLs at any time
- [ ] Parent portal photo access: scoped to own child only, enforced
  server-side by child_id + parent_id match

**Deletion:**

- [ ] Photo deletion must be hard delete from S3 (not soft delete)
- [ ] Deletion triggered by: parent consent revocation, child
  unenrollment, center contract termination, retention period expiry
- [ ] Deletion job must run within 24 hours of trigger event
- [ ] Deletion confirmation logged with: s3_key, deletion_timestamp,
  trigger_reason, operator_id

### 4.3 Voice Audio / Memo Handling Requirements

- [ ] Voice memos received via WhatsApp are transcribed using
  AssemblyAI/Whisper API with "do not train on my data" enabled
  in API account settings — verify this setting before launch
- [ ] Raw audio files must NOT be stored permanently
- [ ] Audio retention: 72 hours maximum after successful transcription,
  then hard delete
- [ ] If transcription fails: audio retained max 7 days for retry,
  then hard deleted regardless
- [ ] Transcription text (not audio) may be stored as part of the
  event record, subject to the retention schedule in Section 4.5
- [ ] Audio files stored temporarily in S3 with same encryption
  requirements as photos
- [ ] Audio file path must not contain child name or PII

### 4.4 AI Processing Requirements

- [ ] GPT-4o API calls: confirm "zero data retention" mode is enabled
  on your OpenAI API account (Settings → Data Controls)
- [ ] AssemblyAI API calls: confirm data deletion policy in account
  settings — enable auto-delete after processing
- [ ] Child data must NEVER be sent to any AI model as part of a
  training dataset without explicit AI training consent (Section 4.1)
- [ ] Prompt content sent to GPT-4o must never include: child's surname,
  parent contact information, or health/medical data beyond what is
  needed for the specific event being structured
- [ ] Log every AI API call with: model, center_id, child_id(s),
  timestamp, token count — do NOT log prompt/response content
  (contains PII)
- [ ] If AI confidence score < threshold: set `needs_review: true`,
  never auto-publish to parent portal

### 4.5 Data Retention Schedule

| Data Type | Retention Period | Trigger for Deletion |
|-----------|-----------------|---------------------|
| Voice audio (raw) | 72 hours after transcription | Automatic job |
| Photos | 12 months after capture OR upon unenrollment | Whichever is sooner |
| Daily event records | 24 months after child unenrollment | Automatic job |
| Consent records | 6 years (legal hold) | Manual, with legal review |
| Audit logs | 3 years | Automatic job |
| Stripe billing records | 7 years (tax law) | Manual, with legal review |
| Parent portal session tokens | 30 days inactive | Automatic expiry |

**Implementation requirements:**

- [ ] Automated retention enforcement job runs nightly at 2AM UTC
- [ ] Job logs every deletion action to append-only audit table
- [ ] Retention periods configurable per center via admin settings
  (centers may require shorter periods by policy)
- [ ] Parent can request immediate deletion of all their child's data
  via portal — must complete within 5 business days (CCPA requirement
  for CA centers)

### 4.6 AI Training Consent (COPPA 2026 Amendment)

The April 2026 amended COPPA Rule explicitly prohibits using children's
personal information to train AI models without separate verifiable
parental consent.

- [ ] AI training consent checkbox is separate from all other consents
- [ ] Default value: unchecked (opt-out by default)
- [ ] No incentive may be offered for AI training consent
- [ ] If AI training consent = false: that child's data is excluded
  from any fine-tuning, RAG, or model improvement pipeline
- [ ] Label training data with consent flag: `ai_training_consent: bool`
  so exclusion is enforced at data pipeline level, not just at UI level

### 4.7 Data Processing Agreements (DPAs)

Before handling any child data in production, execute DPAs with:

| Vendor | DPA Required | Notes |
|--------|-------------|-------|
| OpenAI | Yes | Request via OpenAI enterprise; enable zero retention |
| AssemblyAI | Yes | HIPAA BAA available; request DPA at signup |
| AWS (S3) | Yes | AWS DPA available via AWS console — accept it |
| Twilio (WhatsApp) | Yes | Request via Twilio compliance portal |
| Stripe | Yes | Stripe DPA auto-accepted via ToS for standard accounts |
| Vercel | Yes | Vercel DPA available in settings |
| Railway/Fly.io | Yes | Request from vendor before production launch |

### 4.8 Security Requirements

- [ ] All data in transit: TLS 1.2+ enforced, no HTTP
- [ ] All data at rest: AES-256 encryption
- [ ] PostgreSQL: encrypted at rest, SSL required for all connections
- [ ] S3: SSE-S3 or SSE-KMS on all buckets, no public bucket policies
- [ ] API authentication: JWT with 1-hour expiry + refresh token rotation
- [ ] Admin console: require MFA for all director/admin accounts
- [ ] Penetration test required before launch (can use free tier tools
  like OWASP ZAP for V1)
- [ ] Incident response plan: documented before first customer (see
  Section 6)

### 4.9 Privacy Policy & Terms of Service

Both documents must be live at a public URL before the first paying
customer. The Privacy Policy must include:

- [ ] Complete list of data collected (per Section 3)
- [ ] Legal basis for processing (parental consent)
- [ ] Third-party vendors receiving child data (Section 4.7 list)
- [ ] Retention schedule (Section 4.5)
- [ ] Parent rights: access, correction, deletion, portability
- [ ] COPPA-specific section stating: "We do not collect personal
  information from children under 13 without verifiable parental consent"
- [ ] Contact information for privacy inquiries
- [ ] Effective date and version number

Recommended: Use Termly.io or Iubenda for COPPA-compliant policy
generation ($10–20/month) rather than writing from scratch.

---

## 5. Onboarding Flow Requirements

The center onboarding flow must enforce the following sequence. No
child data may be stored until all steps are complete.

Step 1: Center director creates account
Step 2: Director accepts Platform Terms of Service + DPA
Step 3: Director adds children (name, DOB, room — no photos yet)
Step 4: System generates unique parent invitation link per child
Step 5: Director sends invitation to parent (email or SMS)
Step 6: Parent clicks link → creates parent account
Step 7: Parent reviews Privacy Policy + Data Use explanation
Step 8: Parent completes consent form (4 separate checkboxes)
Step 9: System stores ParentalConsent record (see schema, Section 4.1)
Step 10: Child record becomes ACTIVE — teachers may now upload photos,
send voice memos, and generate daily reports for this child


**Hard rule:** Steps 1–9 must complete before any teacher can submit
data for a child. The system must enforce this at the API level, not
just the UI level. Every API endpoint that writes child data must
validate `consent.daily_reports = True` and `consent.revoked_at = None`
before accepting the request.

---

## 6. Incident Response Requirements

A data breach involving children's personal information triggers:

| Timeframe | Required Action |
|-----------|----------------|
| 0–1 hours | Isolate affected systems, preserve logs |
| 24 hours | Internal incident report complete |
| 72 hours | FTC notification (if >1,000 children affected) |
| 72 hours | NY SHIELD: notify NY Attorney General if NY residents affected |
| 30 days | Affected parents notified individually |
| 30 days | CCPA breach notification if CA residents affected |

**Minimum incident response document (create before launch):**
- Who to call (you + legal counsel contact)
- How to isolate S3 bucket access
- How to invalidate all active JWT tokens
- Template parent notification email
- FTC breach report URL: ftc.gov/enforce/rules/rulemaking-regulatory-reform/childrens-online-privacy-protection-rule

---

## 7. Compliance Gate Checklist

This checklist must be 100% complete before onboarding the first
paying customer. It is a hard gate — not aspirational.

### Legal Setup
- [ ] Privacy Policy published at `/privacy` — COPPA-compliant
- [ ] Terms of Service published at `/terms`
- [ ] DPAs signed with all vendors in Section 4.7
- [ ] Legal counsel reviewed Privacy Policy (recommend: 1 hour with
  a COPPA-specialized attorney, ~$300–500)

### Engineering
- [ ] EXIF stripping implemented and tested (upload a photo with GPS,
  confirm metadata removed on server side)
- [ ] Consent gate enforced at API level (not just UI)
- [ ] Audio auto-deletion job running and logged
- [ ] Photo retention job running and logged
- [ ] Pre-signed S3 URLs with 1-hour expiry implemented
- [ ] OpenAI zero data retention confirmed in account settings
- [ ] AssemblyAI auto-delete confirmed in account settings
- [ ] TLS enforced on all endpoints
- [ ] MFA available for admin accounts

### Onboarding Flow
- [ ] Parent invitation flow complete (Step 1–10 in Section 5)
- [ ] Consent form with 4 separate checkboxes implemented
- [ ] Consent record stored with all required fields
- [ ] Parent revocation flow implemented (portal → immediate effect)
- [ ] Parent data deletion request flow implemented (5-day SLA)

---

## 8. Out of Scope (V1)

- Facial recognition or biometric identification (triggers IL BIPA —
  do not implement under any circumstances in V1)
- Health records integration (HIPAA territory — separate compliance
  layer required)
- EU/Canada center onboarding (GDPR/PIPEDA — separate legal review
  required)
- Selling or sharing child data with third parties for any purpose
  other than platform operations
- Behavioral advertising or profiling using child data

---

## 9. Agent Instructions

**If you are a coding agent reading this document:**

1. Every API endpoint that reads or writes child data must validate
   consent before executing. Add a `require_consent(child_id, scope)`
   middleware check to all such endpoints.
2. The `ai_training_consent` flag must be checked at the data pipeline
   level. Do not rely on UI-level filtering.
3. EXIF stripping is not optional. Implement it in the photo upload
   handler before writing to S3, not as a background job.
4. Audio files have a 72-hour TTL. Implement using S3 Object Lifecycle
   rules, not a cron job — S3 lifecycle rules are atomic and cannot
   be accidentally skipped.
5. Never log prompt content that contains child data. Log only:
   model name, center_id, child_id, timestamp, token count.
6. When in doubt about whether something involves child data: assume
   it does and apply full protections.