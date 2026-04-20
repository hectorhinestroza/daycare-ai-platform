# Affirmi — Legal Engineering Reference

> This document is required reading before deploying to production.
> Every section has a specific engineer action item.

---

## 1. OpenAI DPA + Zero-Retention Verification

**Required env var:** `OPENAI_ZERO_RETENTION_CONFIRMED=confirmed`
**Required env var:** `DPA_OPENAI_CONFIRMED=confirmed`

### How to verify

1. Log into [platform.openai.com](https://platform.openai.com) with the Affirmi account
2. Go to **Settings → Data Controls → API data usage policies**
3. Confirm "API data is not used to train OpenAI models" is active for your account tier
4. Navigate to [platform.openai.com/account/data-processing-agreement](https://platform.openai.com/account/data-processing-agreement)
5. Execute the OpenAI Data Processing Addendum (DPA) and save a copy to `/legal/dpa/openai_dpa_<date>.pdf`
6. Set both env vars to `confirmed` in your production `.env`

### Quarterly re-verification reminder

> ⚠️ **Every quarter:** Revisit step 3 above and confirm the policy has not changed.
> OpenAI has updated its data use policies multiple times. The Affirmi legal commitment
> to parents (consent form §7) depends on this remaining active.
> Log your verification in `/legal/compliance_log.md`.

---

## 2. Twilio DPA Verification

**Required env var:** `DPA_TWILIO_CONFIRMED=confirmed`

### How to verify

1. Log into [console.twilio.com](https://console.twilio.com) with the Affirmi account
2. Navigate to [twilio.com/legal/data-protection-addendum](https://www.twilio.com/legal/data-protection-addendum)
3. Execute the Twilio Data Protection Addendum for the Affirmi account
4. Save a copy to `/legal/dpa/twilio_dpa_<date>.pdf`
5. Set `DPA_TWILIO_CONFIRMED=confirmed` in your production `.env`

---

## 3. WhatsApp Business Mode

**Env var:** `WHATSAPP_MODE=sandbox` (pilot) or `WHATSAPP_MODE=production` (live)

### Sandbox (V1 Pilot)

For the first two pilot centers, Affirmi uses the **Twilio WhatsApp Sandbox**.
- Sandbox number: `+14155238886`
- Teachers join by sending the join code once every 3 days
- All compliance requirements apply in sandbox mode identically to production
- No Meta Business Account registration required for sandbox

### Production (> 2 centers)

Before onboarding a third center:
1. Register a WhatsApp Business Account with Meta via [business.whatsapp.com](https://business.whatsapp.com)
2. Register the production number through Twilio's WhatsApp sender profile
3. Set `WHATSAPP_MODE=production` in production environment
4. Update the sender number in `backend/routers/whatsapp.py`

---

## 4. Pre-Launch Checklist (from legal_prd_v1.md §11)

| # | Requirement | Owner | Status |
|---|---|---|---|
| 1 | `parental_consent` table created | Engineering | ⬜ L-1 |
| 2 | `children_with_active_consent` view + all pipeline queries use it | Engineering | ⬜ L-2 |
| 3 | EXIF stripping function implemented and tested | Engineering | ⬜ L-4 |
| 4 | Audio deletion after 24h max | Engineering | ⬜ L-3 |
| 5 | Photo 90-day retention job scheduled | Engineering | ⬜ L-7 |
| 6 | S3 bucket lifecycle rule 90 days, private ACL | Infrastructure | ⬜ |
| 7 | Pre-signed URL (1-hour expiry) for photo delivery | Engineering | ⬜ L-4 |
| 8 | OpenAI DPA executed and filed | Founder | ⬜ (this doc §1) |
| 9 | Twilio DPA executed and filed | Founder | ⬜ (this doc §2) |
| 10 | OpenAI "no training" API mode confirmed | Engineering | ⬜ (this doc §1) |
| 11 | WhatsApp Business Account registered | Founder | ⬜ (this doc §3) |
| 12 | V1 Consent Form reviewed by attorney | Founder | ⬜ |
| 13 | Privacy Policy published at affirmi.com/privacy | Founder | ⬜ |
| 14 | Consent withdrawal flow (72-hour deletion) | Engineering | ⬜ L-6 |
| 15 | Incident response contacts documented | Founder | ⬜ L-10 |

---

## 5. Startup Guard Behavior

The application uses `backend/startup/legal_checks.py` to enforce DPA confirmation
on every startup.

| Environment | Missing DPA vars | Behavior |
|---|---|---|
| `production` | Any | App refuses to start with `RuntimeError` |
| `development` | Any | App starts, logs `WARNING` for each missing var |
| `sandbox` | Any | App starts, logs `WARNING` for each missing var |

The `/health` endpoint returns `legal_checks: "passing" | "warning" | "blocking"`.

---

*Last updated: April 2026. See `.private/legal_prd_v1.md` for the full legal requirements document.*
