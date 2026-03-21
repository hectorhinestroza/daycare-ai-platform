# Daycare AI Platform — Product Requirements Document V1

**Version:** 1.0 — March 2026
**Author:** Hector Hinestroza
**Status:** Draft — For PM Agent Execution
**Target ICP:** Independent daycare centers, 30–75 children, US market

---

## 1. Executive Summary

This PRD defines the V1 build for the Daycare AI Platform — a standalone, AI-native childcare operations system. The product replaces the offshore VA + manual admin workflow with a voice-first AI pipeline: teachers speak, AI structures, admins review, parents receive beautiful narrative daily reports. No Chrome extension. No Brightwheel dependency. Full platform ownership with a defensible $20–200M exit path.

|                    | OLD APPROACH (Abandoned)                                    | NEW APPROACH (This PRD)                                      |
|--------------------|-------------------------------------------------------------|--------------------------------------------------------------|
| **Architecture**   | Chrome extension injecting into Brightwheel DOM             | Standalone AI platform + parent portal + billing             |
| **Risk**           | Violates Brightwheel ToS — killable overnight               | Full stack ownership, no third-party dependency              |
| **Exit**           | $5–10M ceiling                                              | $20–200M potential                                           |
| **Fundability**    | Not fundable at Seed                                        | Fundable                                                     |

---

## 2. Problem Statement

Independent daycare directors run $300K–$750K/year operations with consumer-grade tools.

| Problem                  | Current Workaround        | Cost                    | Key Issue                                    |
|--------------------------|---------------------------|-------------------------|----------------------------------------------|
| Manual daily logs        | Brightwheel tapping       | 10–20 min/classroom/day | Disrupts classroom; inconsistent quality     |
| Photo documentation      | Philippines VA            | $500–$1,500/month       | Slow, no context, language barrier           |
| Billing adjustments      | Admin manual entry        | 2–5 hrs/week            | Missed charges, revenue leakage              |
| Director doing it all    | Owner handles everything  | Burnout                 | Unscalable; owner can't grow                 |

**Core insight:** Replace the offshore VA + manual admin workflow at the operations layer. The AI structures data; a human reviews before anything reaches parents. Zero-hallucination by design.

---

## 3. Target Customer (ICP)

| Attribute            | Value                                                            |
|----------------------|------------------------------------------------------------------|
| Center type          | Independent single-location childcare center                     |
| Size                 | 30–75 enrolled children                                          |
| Annual revenue       | $300K–$750K                                                      |
| Current platform     | Brightwheel or evaluating alternatives                           |
| Pain signal          | Paying VA $500–$1,500/month OR director doing it all             |
| Decision maker       | Owner/director — single buyer, 30–60 day sales cycle             |
| Geography (V1)       | United States, English-speaking staff                            |
| Avoid                | Home-based daycares (price-sensitive); corporate chains (long cycles) |

---

## 4. Users & Roles

| Role              | Description                               | Primary Interaction                              |
|-------------------|-------------------------------------------|--------------------------------------------------|
| Teacher / Staff   | Frontline, non-technical, time-constrained | WhatsApp Bot: voice + photos                     |
| Admin / VA        | Office manager or director's assistant     | Review Console: approve/edit/reject events       |
| Director / Owner  | Decision maker; billing + parent satisfaction | Review Console + billing approval             |
| Parent            | Receives daily updates; read-only in V1    | Parent Portal (PWA): magic link, no login        |

**V2 additions:** multi-center owner dashboard; parent comment/reaction on reports.

---

## 5. System Architecture

```text
TEACHER INPUT
  │  WhatsApp Business API  (voice .ogg/.mp4 + photos + text)
  ▼
FASTAPI BACKEND  (Python 3.11+, multi-tenant PostgreSQL)
  ├── STT:   Whisper API (V1)  →  AssemblyAI Universal-2 (V1.5)
  ├── LLM:   GPT-4o  strict JSON Schema  →  Pydantic validation
  └── API:   /parse-memo  /pending-events  /events/:id  /billing
  ▼
REVIEW CONSOLE  (React PWA — admin / VA)
  ├── Event queue grouped by child + date
  ├── Approve / edit / reject  |  needs_review yellow flag
  └── Billing event queue with $ indicator
  ▼
PARENT PORTAL  ★ NEW — replaces Chrome extension
  ├── AI narrative daily report per child  (120–250 words, warm tone)
  ├── Photo gallery with AI-generated captions
  ├── WhatsApp push: "Jason's daily report is ready! 📚"
  └── Magic link auth — no app install required
  ▼
BILLING MODULE  ★ NEW
  ├── Late pickup / extra hours / drop-in capture from voice
  ├── Auto-calculate charge from center config
  ├── PDF invoice generation on approval
  └── Stripe Connect — director receives payment directly
  ▼
MIGRATION TOOL  (one-time, not ongoing)
  └── CSV import: child roster + parent contacts from any platform
```

| Layer         | Technology                     | Notes                                                   |
|---------------|--------------------------------|---------------------------------------------------------|
| Input         | WhatsApp Business API via Twilio | One bot per center; max 90s voice, 10 photos/memo      |
| Backend       | Python 3.11+, FastAPI          | Multi-tenant from day 1                                 |
| STT           | Whisper API → AssemblyAI V1.5  | AssemblyAI for child name accuracy (~40% better proper nouns) |
| LLM           | GPT-4o, strict JSON Schema     | Temperature 0; schema-validated; never auto-send        |
| Storage       | PostgreSQL                     | Multi-tenant; upgrade from SQLite                       |
| Review UI     | React (PWA)                    | Admin + director only                                   |
| Parent Portal | Next.js / Vercel               | Magic link; PWA; no native app in V1                    |
| Payments      | Stripe Connect                 | Director receives funds directly                        |
| Deploy        | Railway / Fly.io               | Low ops overhead for solo founder                       |

---

## 6. V1 Feature Scope

### Feature 1 — WhatsApp Voice + Photo Intake

- Bot accepts `.ogg`/`.mp4` voice up to 90 seconds
- Bot accepts photo batches (up to 10) with optional text caption
- Bot confirms: *"Got it! Parsed 3 events for Jason (1 meal, 1 nap, 1 activity)."*
- `/child [name]` or `/classroom [name]` sets context before sending
- Ambiguous names prompt: *"Did you mean Jason M. or Jason T.?"*
- Teacher onboarding < 5 minutes; 60-second demo video provided
- **OUT OF SCOPE (V1):** video messages, real-time feedback, teacher-facing editing

### Feature 2 — AI Event Extraction Pipeline

- Whisper transcription < 8 seconds for memos up to 60 seconds
- GPT-4o with strict JSON Schema matching Pydantic models
- System prompt: *"Extract only what is stated. Do not infer or add detail."*
- Temperature: 0 (deterministic on every call)
- Ambiguous events: `needs_review: true` — never auto-sent
- All outputs schema-validated before storage; malformed responses rejected
- Event types: `MEAL`, `NAP`, `DIAPER`, `ACTIVITY`, `NOTE`, `PICKUP`, `DROP_OFF`, `INCIDENT_MINOR`/`MAJOR`, `BILLING_LATE_PICKUP`, `BILLING_EXTRA_HOURS`, `BILLING_DROP_IN`

### Feature 3 — Admin Review Console

- Accessible at `app.[domain].com/center/[id]`
- Event queue grouped by child + date
- Each card: child name, event type (icon), timestamp, parsed details, photo thumbnails
- Yellow warning on `needs_review: true` events
- Admin actions: approve single, approve all for child, inline edit, delete/reject
- Approved events move to "ready for parent portal" queue
- Activity log: what was published, by whom, when

> [!CAUTION]
> **No event reaches parents without explicit admin approval — ever.**

### Feature 4 — AI Narrative Daily Report + Parent Portal ★ CORE DIFFERENTIATOR

| Brightwheel (Current)                          | Daycare AI Platform                                                                                                  |
|------------------------------------------------|----------------------------------------------------------------------------------------------------------------------|
| ☐ Meal: Lunch — ate "most of it"               | *"Jason had a great Thursday! He ate almost all of his mac and cheese at lunch and asked for more apple slices. He napped well from noon to 1:15..."* |
| ☐ Nap: 12:00–1:15 PM                           | 📷 3 photos with AI captions                                                                                         |
| Clinical. Transactional. No soul.              | Warm. Personal. Parents share with grandparents.                                                                     |

- System groups all approved events per child/day into one summary object
- LLM generates: headline (1 sentence), body (120–250 words), tone (upbeat/neutral/needs-attention)
- Each photo gets a 1-line AI caption; low-confidence falls back to generic ("Art time")
- Generation latency < 5 seconds p50 per report
- Admin can override narrative before publishing
- Parent accesses via magic link (SMS or email); no app install or login in V1
- Parent can "heart" the report (engagement tracking for churn prediction)
- WhatsApp push notification to parent on publish
- **OUT OF SCOPE (V1):** parent comments, two-way teacher-parent messaging

### Feature 5 — Billing Module

- Pipeline recognizes billing intent: *"Marcus was picked up 45 minutes late."*
- Extracts: `child_name`, `billing_type`, `duration`; auto-calculates amount from center config
- Center configures: late pickup ($/min), extra hours ($/hr), drop-in day rate
- Billing events appear in review queue with `$` indicator; admin approves before charge
- Approved billing events generate a PDF invoice
- Stripe Connect: parent pays online; director receives funds directly
- **OUT OF SCOPE (V1):** full tuition billing, recurring invoices, subsidy/CACFP tracking

### Feature 6 — Migration Tool (One-Time Onboarding)

- CSV import: child name, DOB, room, parent name, email, phone
- Template provided for Brightwheel and Procare CSV exports
- Import validates: deduplication, required fields, room assignment conflicts
- Parallel-run guide: use both platforms for 2 weeks, then switch
- **This is NOT an ongoing integration — it is a clean one-time migration**

---

## 7. Out of Scope — V1

- Chrome extension or any Brightwheel DOM interaction
- Native iOS or Android apps (PWA only)
- Attendance / check-in / check-out tracking
- Staff scheduling and time tracking
- Full tuition billing, recurring invoices, CACFP tracking
- Multi-platform support beyond generic CSV (Procare, HiMama: V2+)
- Parent-to-teacher messaging or two-way communication
- Curriculum, developmental milestones, lesson plans
- Multi-center consolidated dashboards
- Any AI auto-send to parents without explicit human approval — ever

---

## 8. Core Data Schemas (The Moat)

```python
class EventType(str, Enum):
    MEAL | NAP | DIAPER | ACTIVITY | NOTE_TO_PARENT | PICKUP | DROP_OFF
    INCIDENT_MINOR | INCIDENT_MAJOR
    BILLING_LATE_PICKUP | BILLING_EXTRA_HOURS | BILLING_DROP_IN

class BaseEvent(BaseModel):
    id: UUID
    center_id: str
    child_name: str
    event_type: EventType
    event_time: Optional[datetime]
    needs_review: bool = False
    status: EventStatus = PENDING
    raw_transcript: str
    photo_ids: List[str]

class DailyNarrative(BaseModel):  # ★ NEW
    child_name: str
    date: date
    center_id: str
    headline: str                   # 1 sentence
    body: str                       # 120–250 words, warm tone
    tone: Literal['upbeat', 'neutral', 'needs-attention']
    photo_captions: Dict[str, str]  # photo_id → caption
    published_at: Optional[datetime] = None
    admin_override: bool = False

class BillingEvent(BaseEvent):
    billing_type: Literal['LATE_PICKUP', 'EXTRA_HOURS', 'DROP_IN']
    minutes_over: Optional[int]
    hours_extra: Optional[float]
    amount_usd: Optional[float]     # auto-calculated from center config
    stripe_invoice_id: Optional[str]
```

---

## 9. Success Metrics & Kill Conditions

### Phase 1 — Design Partners (3–5 centers, Weeks 1–12)

| Metric                    | Target                      | Kill Condition                              |
|---------------------------|-----------------------------|---------------------------------------------|
| Teacher voice adoption    | ≥80% of classrooms, ≥3x/week | < 30% after 6 weeks of training            |
| Parent report open rate   | ≥70% open ≥3x/week          | < 40% open rate after 4 weeks live          |
| Event edit rate           | < 15% manual corrections    | ≥40% edits = extraction quality too low     |
| Billing capture rate      | ≥90% same-day               | < 60% = revenue recovery story fails        |
| Director NPS              | ≥8/10                       | < 6/10 = not sticky enough                  |
| Willingness to pay        | ≥2 centers at $150+/mo      | Zero pay = no commercial viability          |

### Phase 2 — Growth (10–25 centers, Months 4–9)

| Metric          | Target                                          |
|-----------------|--------------------------------------------------|
| Monthly churn   | < 4%                                             |
| Referral rate   | ≥50% of new centers via community channels       |
| MRR milestone   | ≥$4,000–6,000 MRR by month 9                    |
| VA displacement | ≥40% of centers reduce/eliminate VA after 60 days |

> [!WARNING]
> **WALK AWAY** if after 90 days:
> - Zero centers willing to pay $99+/month
> - Teachers refuse voice flow (<30% usage)
> - Parents prefer Brightwheel's reports to yours
> - Centers are happy with $200/month VA and won't switch

---

## 10. 10-Week Build Plan (Solo Founder, Nights + Weekends)

> [!IMPORTANT]
> Do not start the next phase until the gate check passes. No features outside this PRD until 25 paying centers.

### Weeks 1–2 — Voice Pipeline + WhatsApp Bot

- WhatsApp Business API via Twilio/MessageBird (one bot per center)
- Whisper transcription endpoint (`POST /transcribe`)
- GPT-4o structured extraction with Pydantic schemas (`POST /parse-memo`)
- PostgreSQL multi-tenant schema from day 1 (`centers`, `children`, `events`)
- Basic logging and error handling

✅ **Gate:** Send a voice memo → get back validated JSON events

### Weeks 3–4 — Admin Review Console

- React PWA: event queue grouped by child/date
- Approve / edit / reject workflow per event
- Inline editing; photo thumbnail preview; `needs_review` yellow flag
- Activity log for full audit trail
- Center onboarding: add classrooms, children, parent contacts

✅ **Gate:** Admin reviews, edits, and approves a batch of events end-to-end

### Weeks 5–6 — Parent Portal + AI Narrative ★ THE BIG CHANGE

- AI narrative generation: `events[]` → headline + body + tone (GPT-4o)
- Parent-facing web portal: daily report per child (Next.js/Vercel)
- Photo gallery with AI-generated captions
- Magic link auth via SMS/email — no app install
- WhatsApp push notification to parent on publish
- Parent "heart" reaction (engagement tracking)

✅ **Gate:** Parent receives a beautiful narrative report and says: *"I love this."*

### Weeks 7–8 — Billing Module + CSV Migration

- Billing event recognition from voice memos (existing Pydantic schemas)
- Center config: late pickup rate, extra hours rate, drop-in rate
- Auto-calculate charge; `$` indicator in review queue
- PDF invoice generation on approval
- Stripe Connect integration
- CSV importer: child roster + parent contacts from generic CSV

✅ **Gate:** Director captures a late pickup charge, generates invoice, parent pays via Stripe

### Weeks 9–10 — Pilot Launch + Iteration

- Deploy to 3 design-partner centers (production)
- Teacher onboarding per center (< 30 min on-site or Zoom)
- Monitor extraction accuracy; log error cases
- Iterate on AI narrative quality from parent feedback
- Record 60-second product demo video (for GTM)
- Track: teacher adoption %, parent open rate, billing capture rate

✅ **Gate:** All 3 pilots live, metrics tracked, ≥1 center ready to pay

---

## 11. Pricing Model

Anchored against the cost of a Philippines VA ($500–$1,500/month). No credit card required for free trial.

| Tier        | Price            | Includes                                                        | Target                                     |
|-------------|------------------|-----------------------------------------------------------------|--------------------------------------------|
| Pilot       | Free (4–8 wks)   | Full product; white-glove onboarding; case study exchange       | First 3–5 design partners                  |
| Starter     | $199/month       | Up to 3 classrooms; daily reports + billing events              | Centers with 1 VA or director doing it all |
| Growth      | $349/month       | Up to 8 classrooms; priority support; billing analytics         | Centers replacing VA entirely              |
| Multi-site  | Custom ACV       | 10+ locations; consolidated dashboard; dedicated onboarding     | Small chains or franchise operators         |

### Unit Economics — Growth Tier ($349/month)

| Item                                    | Amount         |
|-----------------------------------------|----------------|
| AI infra (Whisper + GPT-4o)             | ~$2–6/month    |
| Hosting / storage / bandwidth           | ~$5–15/month   |
| All-in infra cost                       | ~$7–21/month   |
| Gross margin                            | 94–98%         |
| LTV at 4% monthly churn (25 mo avg)     | ~$8,725        |
| Target CAC (referral-driven)            | < $300         |

---

## 12. Go-to-Market Strategy

### Phase 1 — First 5 Paying Centers (Months 1–3)

- Start with personal network: friend's daycare is customer zero → 3–5 peer referrals
- Target multi-site owners: 1 sales call = $600–$1,700 MRR (3–5 centers)
- Facebook groups: "Daycare Owners," "Childcare Director Network" — authentic posts, no overt selling
- Free 30-day trial; teacher onboarding < 5 minutes
- On-site visits: 2–4 hours at each pilot center in week 1. Fix friction the same week.

### Phase 2 — 5 → 25 Centers (Months 4–9)

- **Case study machine:** every center that kills their VA becomes a named case study on your site
- **State childcare associations:** preferred vendor at 2–3 state conferences in 2026
- **Content SEO:** "daycare daily report automation," "childcare VA replacement," "Brightwheel alternative"
- **Influencer network:** Kris Murray (Child Care Rockstar Radio), Child Care Genius Podcast
- **Killer GTM move:** offer free 30-day "AI Daily Report" add-on alongside existing platform → parents prefer your reports → centers stop needing the old platform → that's the migration trigger

---

## 13. Risks & Mitigations

| Risk                                 | Likelihood | Severity | Mitigation                                                       |
|--------------------------------------|------------|----------|------------------------------------------------------------------|
| Brightwheel builds native AI         | Medium     | High     | Be first to 500 centers; become the platform they'd acquire      |
| Teacher doesn't adopt WhatsApp       | Medium     | High     | < 5 min onboarding; 60-sec demo; on-site training week 1        |
| COPPA compliance (child photos)      | Low–Med    | High     | kidSAFE Seal; DPAs; no facial recognition; $15–50K legal Day 1   |
| High SMB churn                       | Medium     | High     | Anchor in billing ($ recovery); annual contracts                 |
| LLM hallucination on child names     | Medium     | High     | AssemblyAI in V1.5; needs_review flag; human approval always     |
| Solo founder bandwidth               | High       | Medium   | Strict V1 scope; no features outside PRD until 25 paying centers |
| WhatsApp Business API approval       | Low        | Medium   | Apply early; Telegram as fallback intake                         |

> [!WARNING]
> **COPPA — Day 1 Requirement (April 22, 2026 Deadline):** Photos of children are "personal information" under COPPA 2025 amendments. Use "school authorization" model. Never perform facial recognition. Encryption in transit and at rest. Execute DPAs with every center customer. Budget $15,000–$50,000 initial legal setup before onboarding real children's data.

---

## 14. Exit Potential

| ARR Milestone  | Centers | Exit Range               | Buyer Type                          |
|----------------|---------|--------------------------|-------------------------------------|
| < $1M ARR      | < 300   | $3–8M (acqui-hire)       | Brightwheel, Kangarootime           |
| $1–3M ARR      | 300–800 | $5–25M (tuck-in)         | Procare/Roper, Brightwheel, Lillio  |
| $3–10M ARR     | 800–2K  | $20–80M                  | PE add-on or strategic premium      |
| $10–25M ARR    | 2K–6K   | $70–200M                 | Roper, PE buyout                    |
| $25M+ ARR      | 6K+     | $150M–$500M+             | IPO or strategic acquirer           |

A standalone AI-native childcare platform is a $20–200M outcome. The 2025–2027 window is favorable: PE dry powder at record levels, AI-native products attracting a 25–30% valuation premium over horizontal SaaS.

---

*Daycare AI Platform — PRD V1 | Confidential | March 2026 | Author: Hector Hinestroza*
