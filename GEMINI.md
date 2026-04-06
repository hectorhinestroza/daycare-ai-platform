# Daycare AI Platform — Agent Context

## Project Purpose
AI-native childcare operations platform. Voice memos from teachers
→ structured events → tiered review (teacher first-pass, director exceptions-only)
→ AI narrative parent reports. Standalone platform. No Brightwheel dependency.

## Tech Stack
- Backend: Python 3.11+, FastAPI, PostgreSQL (multi-tenant from day 1)
- STT: OpenAI Whisper API (V1), AssemblyAI Universal-2 (V1.5)
- LLM: GPT-4o, temperature=0, strict JSON Schema, Pydantic validation
- WhatsApp: Twilio WhatsApp Business API
- Frontend: React PWA (Review Console), Next.js/Vercel (Parent Portal)
- Payments: Stripe Connect
- Deploy: Railway or Fly.io

## Architecture Rules (NEVER VIOLATE)
- NEVER auto-send any event to parents without human approval (teacher OR director)
- ALL LLM outputs must be Pydantic schema validated before storage
- Multi-tenant isolation: every DB query must filter by center_id
- Temperature always 0 for extraction calls (deterministic)
- needs_review: true for any ambiguous event — never suppress
- Every event has a `review_tier` (teacher | director) and `confidence_score`
- COPPA compliance is a hard gate — see `docs/legal_PRD.md`

## Current Phase
Week 3 of 10-week build plan. Issues #1–#5 complete. Next: Issues #6–#7 (Admin Review Console).

## Three-Tier Review System

| Role | What They See | What They Do |
|------|--------------|--------------|
| Teacher | Their own submitted events | First-pass review — confirms AI got it right, one-tap approve |
| Director | Flagged events only (incidents, billing, low-confidence) | Exception-only review — handles the hard stuff |
| Parent | Approved events in real time | Read-only |

### How it works:
1. Teacher sends voice note via WhatsApp
2. AI structures into events, assigns `confidence_score` (0.0–1.0)
3. **High confidence** (e.g., "Lunch at 12pm — rice and beans") → teacher review → one-tap confirm → auto-publishes to parent
4. **Low confidence** (ambiguous child name, incident, billing) → director queue
5. Director only touches the hard stuff — keeps promise of "real-time updates" without admin burnout

### Event Schema Fields:
```python
review_tier: Literal["teacher", "director"]  # who must approve
confidence_score: float                       # 0.0–1.0
needs_director_review: bool                   # True for incidents, billing, low confidence
```

## Manage Kids Module (System of Record)

### Child Profile Management
- Basic info: name, DOB, room/classroom, allergies/medical notes, enrollment dates
- Emergency contacts with permission levels (who can pick up)
- Parent account links (emails/phones associated)
- Status: `ACTIVE` | `ENROLLED` | `WAITLIST` | `UNENROLLED`

### Room/Classroom Management
- Create rooms (Toddlers, Pre-K, etc.)
- Assign teachers to rooms
- Move kids between rooms (voice memos are scoped to teacher's room by default)

### Enrollment Flow
Director adds child → system generates magic link → parent completes consent → child goes `ACTIVE`

This is the entity graph the AI uses to resolve voice memos correctly
(e.g., "Jojo" in Room 2 = Josiah Washington, not Jonathan Smith).

## Parent Experience — Three Views

### 1. Live Day Feed (Real-Time)
As events are approved by teacher throughout the day, parents see them immediately.
Event cards with timestamps. Photos inline. Like a curated group chat for their child's day.

### 2. End-of-Day Recap (Push Notification)
Configurable time (default 5:30 PM). GPT-4o synthesizes all approved events into
AI narrative paragraph. Push notification or SMS magic link to parent.

### 3. History View (Past Days)
Calendar strip at top. Tap any past date → full timeline. Used for:
- Reviewing a week's data
- Checking incident timing ("When did that fall happen?")
- Pediatrician visits (feeding/nap patterns)
- Compliance audit trail (director can filter by event type + date range, export PDF)

## GitHub Issues — 10-Week Build Plan
Repo: https://github.com/hectorhinestroza/daycare-ai-platform

### Weeks 1–2: Voice Pipeline + WhatsApp Bot
| # | Title | Label | Status |
|---|-------|-------|--------|
| 1 | WhatsApp Business API Setup via Twilio | week-1 | ✅ Done |
| 2 | Whisper Transcription Endpoint | week-1 | ✅ Done |
| 3 | GPT-4o Structured Extraction with Pydantic Schemas | week-1 | ✅ Done |
| 4 | PostgreSQL Multi-Tenant Schema | week-2 | ✅ Done |
| 5 | Basic Logging and Error Handling | week-2 | ✅ Done |

### Weeks 3–4: Admin Review Console
| # | Title | Label | Status |
|---|-------|-------|--------|
| 6 | React PWA: Event Queue UI | week-3 | ✅ Done |
| 7 | Admin Approve / Edit / Reject Workflow | week-3 | ✅ Done |
| 8 | Activity Log and Audit Trail | week-4 | 🔲 Open |
| 9 | Center Onboarding: Classrooms, Children, Parent Contacts | week-4 | 🔲 Open |

### Weeks 3–4: Legal Engineering (parallel track)
| # | Title | Label | Status |
|---|-------|-------|--------|
| L-1 | Parental Consent Schema + API | legal, week-4 | 🔲 Open |
| L-2 | Consent Gate Middleware | legal, week-4 | 🔲 Open |
| L-3 | Photo EXIF Stripping + Secure Storage | legal, week-4 | 🔲 Open |
| L-4 | Audio Retention + Auto-Delete | legal, week-4 | 🔲 Open |
| L-5 | AI API Privacy Controls | legal, week-2 | 🔲 Open |
| L-6 | Data Retention Enforcement Jobs | legal, week-8 | 🔲 Open |
| L-7 | Parent Consent + Onboarding Flow | legal, week-4 | 🔲 Open |
| L-8 | Privacy Policy + Terms Pages | legal, week-9 | 🔲 Open |
| L-9 | Incident Response Plan | legal, week-9 | 🔲 Open |

### Weeks 5–6: Parent Portal + AI Narrative
| # | Title | Label | Status |
|---|-------|-------|--------|
| 10 | AI Narrative Daily Report Generation | week-5 | 🔲 Open |
| 11 | Parent Portal: Daily Report View + On demand view(every time teacher sends update it notifies the parent and parent can view the update in real time) + Photo Gallery +  | week-5 | 🔲 Open |
| 12 | WhatsApp Push Notification + Parent Heart Reaction | week-6 | 🔲 Open |

### Weeks 7–8: Billing Module + CSV Migration
| # | Title | Label | Status |
|---|-------|-------|--------|
| 13 | Billing Event Recognition + Auto-Calculate | week-7 | 🔲 Open |
| 14 | PDF Invoice Generation + Stripe Connect | week-7 | 🔲 Open |
| 15 | CSV Migration Tool: Child Roster + Parent Contacts | week-8 | 🔲 Open |

### Weeks 9–10: Pilot Launch + Iteration
| # | Title | Label | Status |
|---|-------|-------|--------|
| 16 | Production Deploy to 3 Design-Partner Centers | week-9 | 🔲 Open |
| 17 | Monitor Extraction Accuracy + Iterate AI Narrative | week-9 | 🔲 Open |
| 18 | Metrics Dashboard + Demo Video for GTM | week-10 | 🔲 Open |

## File Structure
/backend — FastAPI app
/frontend/console — React Review Console PWA
/frontend/parent — Next.js Parent Portal
/schemas — Pydantic models (source of truth)
/tests — pytest, write tests first
/docs — PRD, legal PRD, architecture docs

## Coding Standards
- Write tests before implementation (TDD)
- Pydantic models in /schemas are the contract — never bypass them
- All endpoints return typed responses matching Pydantic schemas
- Postgres multi-tenant: center_id on every table, every query

## What NOT to Build (V1 Scope Lock)
- No Chrome extension or any Brightwheel integration
- No native iOS/Android apps (PWA only)
- No attendance tracking, CACFP, staff scheduling
- No features outside the 10-week PRD until 25 paying centers
- No facial recognition or biometric identification (triggers IL BIPA)

## Auth
Magic links only. No passwords. Parent access = magic link per session or
30-day cookie. Admin access = magic link + email OTP for MFA.
No password hashing or storage anywhere in the system.

## UI Architecture

TEACHER APP (PWA mobile)
├── My Pending Events (AI-structured, awaiting my confirmation)
├── Quick Confirm / Edit (one-tap approve for high-confidence events)
└── Send New Voice Note / Photo

DIRECTOR CONSOLE (PWA mobile + desktop)
├── Dashboard (today's activity count, flagged events badge)
├── Flagged Queue (incidents, billing, low-confidence events ONLY)
├── Manage Kids
│   ├── Child List / Search
│   ├── Child Profile + Edit (name, DOB, room, allergies, emergency contacts)
│   ├── Rooms / Classroom Assignment (create rooms, assign teachers)
│   └── Enrollment → Parent Invite Flow (magic link → consent → ACTIVE)
├── Billing Tab (approved fees, pending invoices, Stripe status)
└── History / Reports (date range filter, event type filter, export PDF)

PARENT PORTAL (mobile web, magic link)
├── Today's Live Feed (real-time event cards + photos as approved)
├── End-of-Day Recap (AI narrative, configurable delivery time, default 5:30 PM)
└── History (calendar strip → past day timelines → compliance audit)