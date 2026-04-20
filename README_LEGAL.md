# Affirmi — Legal Engineering Reference

> **Pre-production reading.** Work through the checklist in §4 before your first real customer.
> No environment variables, no deploy steps — just founder actions and file saves.

---

## 1. OpenAI DPA + Zero-Retention Verification

**Who does this:** Founder (one time, before first paying customer)

### Steps

1. Log into [platform.openai.com](https://platform.openai.com) with the Affirmi account
2. Go to **Settings → Data Controls → API data usage policies**
3. Confirm **"API data is not used to train OpenAI models"** is active for your account tier
4. Navigate to the [OpenAI Data Processing Addendum](https://platform.openai.com/account/data-processing-agreement)
5. Execute the DPA and **save a copy to `/legal/dpa/openai_dpa_<YYYY-MM>.pdf`**

### Quarterly re-check

> ⚠️ Every quarter: revisit step 3 above and confirm the policy hasn't changed.
> OpenAI has updated its data-use policies multiple times.
> Log each verification in `/legal/compliance_log.md`:
> ```
> 2026-04-19 — OpenAI zero-retention confirmed. Platform shows "API data not used for training."
> ```

### Env var (optional, for /health observability only)

Set in your Railway/Fly environment after executing the DPA:
```
DPA_OPENAI_CONFIRMED=confirmed
OPENAI_ZERO_RETENTION_CONFIRMED=confirmed
```
If absent, `/health` reports `false` — a reminder, never a deploy blocker.

---

## 2. Twilio DPA Verification

**Who does this:** Founder (one time, before first paying customer)

### Steps

1. Log into [console.twilio.com](https://console.twilio.com) with the Affirmi account
2. Execute the [Twilio Data Protection Addendum](https://www.twilio.com/legal/data-protection-addendum)
3. **Save a copy to `/legal/dpa/twilio_dpa_<YYYY-MM>.pdf`**

### Env var (optional, for /health observability only)

```
DPA_TWILIO_CONFIRMED=confirmed
```

---

## 3. WhatsApp Business Mode

| Mode | When | How |
|---|---|---|
| `WHATSAPP_MODE=sandbox` | First 2 pilot centers | Twilio Sandbox (`+14155238886`). Teachers join with a one-time code. No Meta registration. |
| `WHATSAPP_MODE=production` | 3rd center onward | Register WhatsApp Business Account with Meta. Register number in Twilio. |

---

## 4. Pre-Production Legal Checklist

Work through this once before your first real customer. Check boxes, save PDFs, done.

### Founder actions

- [ ] OpenAI DPA downloaded and saved to `/legal/dpa/openai_dpa_<YYYY-MM>.pdf`
- [ ] OpenAI zero-retention confirmed active at platform.openai.com → Settings → Data Controls
- [ ] Twilio DPA downloaded and saved to `/legal/dpa/twilio_dpa_<YYYY-MM>.pdf`
- [ ] V1 Consent Form reviewed by attorney
- [ ] Privacy Policy published at `affirmi.com/privacy`
- [ ] WhatsApp Business Account registered (before 3rd center)

### Engineering actions

- [ ] `parental_consent` table live in production (L-1 ✅)
- [ ] `children_with_active_consent` view and consent gate enforcing (L-2 ✅)
- [ ] Photo EXIF stripping active before any S3 write (L-4 ✅)
- [ ] S3 bucket lifecycle rule: 90-day expiry, private ACL (L-7 — open)
- [ ] Photo delivery via pre-signed URLs with ≤1-hour expiry (L-7 — open)
- [ ] 90-day data retention nightly job scheduled (L-7 — open)
- [ ] Consent withdrawal flow (72-hour deletion) implemented (L-7 — open)
- [ ] WhatsApp audio in-memory only, Twilio deletion after transcription (L-3 — open)

---

## 5. /health Legal Fields Reference

The `/health` endpoint surfaces DPA status passively:

```json
{
  "status": "healthy",
  "legal": {
    "openai_dpa_confirmed": false,
    "twilio_dpa_confirmed": false,
    "openai_zero_retention_confirmed": false
  }
}
```

`false` = env var not set. A reminder. The deploy proceeds either way.
These flip to `true` once you set the env vars after executing the actual DPAs.

---

*Last updated: April 2026. Full legal requirements: `.private/legal_prd_v1.md`*
