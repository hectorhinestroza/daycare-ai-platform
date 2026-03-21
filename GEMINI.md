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
Week [X] of 10-week build plan. Current feature: [Feature Name].

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
