# Daycare AI Platform

An AI-native childcare operations platform that replaces manual admin work with a voice-first pipeline. Teachers send voice memos via WhatsApp, the system structures them into logged events, admins perform the final review, and parents receive daily narrative reports. 

## How It Works

1. **Voice Intake**: Teachers send audio clips and photos via a WhatsApp Business bot (e.g., "Jason just ate all of his mac and cheese and had some water").
2. **AI Extraction**: The backend processes the audio using Whisper and uses GPT-4o to extract strictly-typed JSON matching our database schemas (e.g., `MEAL`, `ACTIVITY`, `NAP`).
3. **Three-Tier Review**: 
   - *High-confidence* events are surfaced for a single-tap teacher approval.
   - *Low-confidence*, billing, or incident events automatically flag for Director review. 
   - No data reaches parents without a human in the loop.
4. **Parent Narratives**: Real-time event updates are published to a live feed, and at the end of the day, parents receive a cohesive AI-generated summary of their child's day via a magic-link web portal.

## Tech Stack

- **Backend**: Python 3.11, FastAPI, PostgreSQL, SQLAlchemy + Alembic
- **Frontend**: React PWA (Admin/Teacher Console), Next.js (Parent Portal)
- **AI/ML Pipelines**: OpenAI Whisper (speed), AssemblyAI (proper noun & child name accuracy), GPT-4o (structured data extraction)
- **Integrations**: Twilio (WhatsApp API), Stripe Connect (Billing module)
- **Infrastructure**: Designed for Railway / Fly.io deployments

## Core Architectural Guardrails

- **Strict Validation**: All LLM extraction calls run at `temperature=0` and are validated against rigorous Pydantic models before database insertion. Parsing failures automatically default to `needs_review: true`.
- **Multi-tenant Isolation**: Every table and transactional query is strictly scoped by `center_id` at the database level.
- **Privacy First**: COPPA compliant by design. Media is stripped of EXIF data before secure bucket storage, and parent report access is scoped strictly via short-lived magic links (no passwords). 

## Local Development Setup

1. **Backend Environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r backend/requirements.txt
   ```

2. **Database Migrations**:
   ```bash
   alembic upgrade head
   ```

3. **Run FastAPI Server**:
   ```bash
   cd backend
   uvicorn main:app --reload
   ```

4. **Run Frontend Clients**:
   ```bash
   # Admin & Teacher Console
   cd frontend/console
   npm install && npm run dev
   
   # Parent Portal
   cd frontend/parent
   npm install && npm run dev
   ```

## Documentation

Full product requirements and structural overviews are detailed in `docs/PRD.md` and `docs/legal_PRD.md`.
