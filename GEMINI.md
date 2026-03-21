# Daycare AI Platform — Agent Context

## Project Purpose
AI-native childcare operations platform. Voice memos from teachers 
→ structured events → admin review → AI narrative parent reports.
Standalone platform. No Brightwheel dependency.

## Tech Stack
- Backend: Python 3.11+, FastAPI, PostgreSQL (multi-tenant from day 1)
- STT: OpenAI Whisper API (V1), AssemblyAI Universal-2 (V1.5)
- LLM: GPT-4o, temperature=0, strict JSON Schema, Pydantic validation
- WhatsApp: Twilio WhatsApp Business API
- Frontend: React PWA (Review Console), Next.js/Vercel (Parent Portal)
- Payments: Stripe Connect
- Deploy: Railway or Fly.io

## Architecture Rules (NEVER VIOLATE)
- NEVER auto-send any event to parents without admin approval
- ALL LLM outputs must be Pydantic schema validated before storage
- Multi-tenant isolation: every DB query must filter by center_id
- Temperature always 0 for extraction calls (deterministic)
- needs_review: true for any ambiguous event — never suppress

## Current Phase
Week 1 of 10-week build plan. Current feature: Voice Pipeline + WhatsApp Bot.

## GitHub Issues — 10-Week Build Plan
Repo: https://github.com/hectorhinestroza/daycare-ai-platform

### Weeks 1–2: Voice Pipeline + WhatsApp Bot
| # | Title | Label | Status |
|---|-------|-------|--------|
| 1 | WhatsApp Business API Setup via Twilio | week-1 | 🔲 Open |
| 2 | Whisper Transcription Endpoint | week-1 | 🔲 Open |
| 3 | GPT-4o Structured Extraction with Pydantic Schemas | week-1 | 🔲 Open |
| 4 | PostgreSQL Multi-Tenant Schema | week-2 | 🔲 Open |
| 5 | Basic Logging and Error Handling | week-2 | 🔲 Open |

### Weeks 3–4: Admin Review Console
| # | Title | Label | Status |
|---|-------|-------|--------|
| 6 | React PWA: Event Queue UI | week-3 | 🔲 Open |
| 7 | Admin Approve / Edit / Reject Workflow | week-3 | 🔲 Open |
| 8 | Activity Log and Audit Trail | week-4 | 🔲 Open |
| 9 | Center Onboarding: Classrooms, Children, Parent Contacts | week-4 | 🔲 Open |

### Weeks 5–6: Parent Portal + AI Narrative
| # | Title | Label | Status |
|---|-------|-------|--------|
| 10 | AI Narrative Daily Report Generation | week-5 | 🔲 Open |
| 11 | Parent Portal: Daily Report View + Photo Gallery | week-5 | 🔲 Open |
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
