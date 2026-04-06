# Daycare AI Platform — Architecture Deep Dive

> Written for a C++ engineer new to Python and frontend. Every concept is
> explained from first principles with C++ analogies where they help.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Project Layout & Module System](#2-project-layout--module-system)
3. [Python Fundamentals (for C++ Engineers)](#3-python-fundamentals-for-c-engineers)
4. [FastAPI — The HTTP Server](#4-fastapi--the-http-server)
5. [Pydantic — The Type System](#5-pydantic--the-type-system)
6. [The Voice Pipeline (End‑to‑End)](#6-the-voice-pipeline-end-to-end)
7. [Database Layer — SQLAlchemy + PostgreSQL](#7-database-layer--sqlalchemy--postgresql)
8. [Three‑Tier Review System](#8-three-tier-review-system)
9. [React PWA Review Console](#9-react-pwa-review-console)
10. [Middleware & Observability](#10-middleware--observability)
11. [Configuration & Secrets](#11-configuration--secrets)
12. [Testing Strategy](#12-testing-strategy)
13. [Infrastructure (Twilio, ngrok, uvicorn)](#13-infrastructure-twilio-ngrok-uvicorn)

---

## 1. System Overview

The Daycare AI Platform turns teacher voice memos into structured, parent-readable events. The full data flow:

```
┌────────────┐   ┌─────────┐   ┌────────────┐   ┌───────────┐   ┌────────────┐   ┌────────┐
│  Teacher   │──▸│WhatsApp  │──▸│  Twilio    │──▸│  FastAPI  │──▸│ Review     │──▸│ Parent │
│  speaks    │   │  msg     │   │  webhook   │   │  backend  │   │ Console    │   │ Portal │
│  into phone│   │          │   │  POST      │   │           │   │ (React PWA)│   │(Week 5)│
└────────────┘   └─────────┘   └────────────┘   └───────────┘   └────────────┘   └────────┘
                                                      │
                                          ┌───────────┼───────────┐
                                          │           │           │
                                     ┌────▼──┐  ┌────▼──┐  ┌────▼──┐
                                     │Whisper│  │GPT-4o │  │Postgres│
                                     │(STT)  │  │(NLP)  │  │(DB)   │
                                     └───────┘  └───────┘  └───────┘
```

### Architecture rules (NEVER violate)

| Rule | Enforcement |
|------|-------------|
| No event reaches parents without human approval | `status=PENDING` default, approve endpoint required |
| All LLM outputs are Pydantic-validated before storage | `BaseEvent` schema validation in `extraction.py` |
| Multi-tenant isolation on every query | `center_id` column on every table, filtered in every handler |
| `temperature=0` for extraction | Hardcoded in `extraction.py` |
| `needs_review=True` for any ambiguity | Default in extraction, never suppressed |

---

## 2. Project Layout & Module System

```
day_care/
├── .env                          # secrets (git-ignored)
├── GEMINI.md                     # agent context file
├── backend/
│   ├── __init__.py
│   ├── main.py                   # entry point — FastAPI app creation, lifespan, middleware
│   ├── config.py                 # loads .env into typed settings (Pydantic)
│   ├── middleware.py             # request ID, timing, global error handler
│   ├── routers/
│   │   ├── whatsapp.py           # POST /webhook/whatsapp — voice pipeline
│   │   └── events.py             # 8 REST endpoints for review console
│   ├── services/
│   │   ├── transcription.py      # Whisper API wrapper (STT)
│   │   └── extraction.py         # GPT-4o structured extraction (NLP)
│   ├── storage/
│   │   ├── database.py           # SQLAlchemy engine, session, Base
│   │   ├── models.py             # ORM models (7 tables)
│   │   └── events_handlers.py    # CRUD operations (10 functions)
│   └── utils/
│       └── media.py              # Twilio media downloader
├── schemas/
│   ├── events.py                 # Pydantic event models (source of truth)
│   ├── narrative.py              # daily report model (Week 5)
│   └── billing.py                # billing event model (Week 7)
├── tests/
│   ├── test_events_api.py        # 19 tests — review API + batch/history
│   ├── test_events_handlers.py   # 36 tests — CRUD operations
│   └── test_whatsapp_webhook.py  # 5 tests — voice pipeline
├── frontend/
│   └── console/                  # React PWA — Vite + React
│       ├── src/
│       │   ├── App.jsx           # main app — role toggle, view toggle, batch approve
│       │   ├── api.js            # API service layer (8 fetch functions)
│       │   ├── index.css         # design system — dark mode, tokens, animations
│       │   └── components/
│       │       ├── EventCard.jsx # approve/reject/edit card + read-only history
│       │       ├── EmptyState.jsx
│       │       └── Toast.jsx     # auto-dismiss notifications
│       ├── public/manifest.json  # PWA manifest
│       └── index.html
├── alembic/                      # database migrations
│   ├── alembic.ini
│   └── env.py
└── docs/
    ├── PRD.md
    └── legal_PRD.md
```

### C++ analogy: `__init__.py`

In C++ you `#include` headers. In Python, a directory becomes an importable
**package** only if it contains `__init__.py` (can be empty). Think of it like
declaring a namespace. Every `__init__.py` in our tree is empty — they just tell
Python "this directory is a module."

```python
# Python equivalent of: #include "backend/services/transcription.h"
from backend.services.transcription import transcribe_audio
```

Python resolves imports from `PYTHONPATH`. We run with `PYTHONPATH=.` so the project
root is the import base.

---

## 3. Python Fundamentals (for C++ Engineers)

### Types are optional but we use them everywhere

```python
async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.ogg") -> str:
```

| C++ Concept | Python Equivalent |
|-------------|-------------------|
| `std::string` | `str` |
| `std::vector<T>` | `List[T]` |
| `std::optional<T>` | `Optional[T]` |
| `enum class` | `class MyEnum(str, Enum)` |
| `struct` | `class MyModel(BaseModel)` (Pydantic) |
| `const` | No equivalent (immutable by convention) |
| `nullptr` | `None` |
| header/source split | Everything in one `.py` file |

### `async` / `await` — like C++20 coroutines

```python
async def transcribe_audio(audio_bytes: bytes) -> str:
    result = await some_api_call()   # yields control while waiting
    return result
```

FastAPI manages the event loop (like `boost::asio::io_context`).

### Decorators — like C++ attributes

```python
@app.get("/health")          # registers health() as GET /health handler
async def health():
    return {"status": "healthy"}
```

---

## 4. FastAPI — The HTTP Server

### Entry point: `main.py`

```python
app = FastAPI(title="Daycare AI Platform API", lifespan=lifespan)

# Middleware stack (order matters — outermost first)
app.add_middleware(GlobalExceptionMiddleware)    # catches unhandled errors
app.add_middleware(RequestTimingMiddleware)       # logs request duration
app.add_middleware(RequestIDMiddleware)           # X-Request-ID header
app.add_middleware(CORSMiddleware, ...)           # allows React dev server

# Routers
app.include_router(events_router)    # /api/events/* (8 endpoints)
app.include_router(whatsapp_router)  # /webhook/whatsapp
```

### How a request flows

```
Client sends POST /webhook/whatsapp
    │
    ▼
uvicorn (ASGI server)
    │
    ▼
RequestIDMiddleware → assigns X-Request-ID
    │
    ▼
RequestTimingMiddleware → starts timer
    │
    ▼
GlobalExceptionMiddleware → try/catch wrapper
    │
    ▼
FastAPI router dispatch → whatsapp_webhook()
    │
    ├─ Look up teacher by phone → center_id
    ├─ Text? → extract_events() → persist to DB → TwiML reply
    ├─ Voice? → download → transcribe → extract → persist → TwiML reply
    └─ Photo? → log → TwiML reply
```

---

## 5. Pydantic — The Type System

Pydantic is our runtime type enforcement. In C++ the compiler enforces types;
in Python, Pydantic does this at runtime.

### Core schema: `schemas/events.py`

```python
class EventType(str, Enum):
    FOOD = "food"
    NAP = "nap"
    POTTY = "potty"
    ACTIVITY = "activity"
    INCIDENT = "incident"
    # ... 12+ types

class BaseEvent(BaseModel):
    id: UUID
    center_id: str               # multi-tenant key
    child_name: str
    event_type: EventType        # enforced enum
    confidence_score: float      # 0.0–1.0
    review_tier: str             # "teacher" | "director"
    needs_director_review: bool
    status: EventStatus          # PENDING | APPROVED | REJECTED
    raw_transcript: str          # audit trail
```

**Validation failure** = rejected event:
```python
event = BaseEvent(event_type="INVALID")  # → ValidationError — never stored
```

This is our moat against LLM hallucination. GPT-4o outputs are **untrusted** — Pydantic
validates before storage. Non-negotiable.

---

## 6. The Voice Pipeline (End‑to‑End)

```
Teacher voice memo → WhatsApp → Twilio POST → Our Server
    │
    ├── Step 1: Teacher lookup by phone → get center_id
    ├── Step 2: Download audio from Twilio (authenticated GET)
    ├── Step 3: Whisper API → transcript text
    ├── Step 4: GPT-4o extraction → structured JSON → Pydantic validation
    ├── Step 5: Persist to PostgreSQL (center_id scoped)
    └── Step 6: TwiML reply → "Got it! Parsed 2 events for Jason"
```

### GPT-4o extraction — the critical path

```python
response = client.chat.completions.create(
    model="gpt-4o",
    temperature=0,                              # deterministic
    response_format={"type": "json_object"},    # forces JSON
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Transcript: {transcript}"},
    ],
)
```

| Decision | Why |
|----------|-----|
| `temperature=0` | Deterministic — same input, same output |
| `needs_review=True` default | Ambiguous events flagged for humans |
| Pydantic validation gate | LLM outputs are untrusted |
| `status=PENDING` | No event auto-approved |

---

## 7. Database Layer — SQLAlchemy + PostgreSQL

### Entity Relationship Diagram

```mermaid
erDiagram
    CENTER ||--o{ ADMIN : employs
    CENTER ||--o{ TEACHER : employs
    CENTER ||--o{ ROOM : contains
    CENTER ||--o{ CHILD : enrolls
    CENTER ||--o{ EVENT : produces
    ROOM ||--o{ TEACHER : assigned_to
    ROOM ||--o{ CHILD : placed_in
    TEACHER ||--o{ EVENT : submits
    CHILD ||--o{ EVENT : about
    EVENT ||--o{ PHOTO : attached
```

### 7 ORM models in `models.py`

| Model | Key Fields | Multi-tenant |
|-------|-----------|-------------|
| `Center` | id, name, timezone | Root entity |
| `Admin` | email, role (director/admin) | `center_id` FK |
| `Teacher` | phone (E.164), room_id | `center_id` FK |
| `Room` | name (Toddlers, Pre-K...) | `center_id` FK |
| `Child` | name, DOB, allergies, status | `center_id` FK |
| `Event` | event_type, review_tier, confidence_score, status | `center_id` FK |
| `Photo` | s3_key, caption | `center_id` FK |

### Session management — C++ RAII pattern

```python
def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a DB session, auto-closes after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Usage in endpoints:
@router.get("/events/{center_id}")
def get_events(center_id: UUID, db: Session = Depends(get_db)):
    ...
```

`Depends(get_db)` is FastAPI's dependency injection — like constructor injection in C++.
The session auto-closes when the request completes (RAII pattern).

### Connection pooling

```python
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,   # verify connections alive before use
    pool_size=5,          # persistent connections
    max_overflow=10,      # overflow under load
)
```

In C++ terms: this is like a connection pool (`boost::asio::thread_pool` for DB connections).

---

## 8. Three‑Tier Review System

The core workflow that ensures no event reaches parents without human approval.

```
Voice memo → AI extraction → Event created (PENDING)
    │
    ├── confidence ≥ 0.7, not incident/billing
    │       → review_tier = "teacher"
    │       → Teacher sees in their queue → one-tap approve → APPROVED
    │
    └── confidence < 0.7, OR incident/billing
            → review_tier = "director", needs_director_review = True
            → Director sees in flagged queue → review → APPROVED/REJECTED
```

### Event lifecycle

```
PENDING ──approve──▸ APPROVED ──▸ visible to parents
    │
    └──reject───▸ REJECTED ──▸ not shown to parents
```

### Backend handlers (`events_handlers.py`)

| Function | What It Does |
|----------|-------------|
| `create_event()` | Insert new event (from voice pipeline) |
| `create_event_from_base()` | Insert from Pydantic BaseEvent (post-extraction) |
| `get_event()` | Single event by ID + center_id |
| `get_events_pending_teacher()` | Teacher queue: PENDING + review_tier=teacher |
| `get_events_pending_director()` | Director queue: PENDING + needs_director_review |
| `approve_event()` | Set status=APPROVED, set reviewed_at timestamp |
| `reject_event()` | Set status=REJECTED, set reviewed_at timestamp |
| `update_event()` | Inline edit (child_name, details, event_type, event_time) |
| `batch_approve_events()` | Approve ALL pending events for a child in one call |
| `get_events_history()` | Paginated list of APPROVED/REJECTED events |

### API endpoints (`events.py` router)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/events/pending/teacher/{center_id}` | Teacher review queue |
| `GET` | `/api/events/pending/director/{center_id}` | Director flagged queue |
| `GET` | `/api/events/history/{center_id}` | Approved/rejected history |
| `POST` | `/api/events/{center_id}/batch-approve` | Batch approve by child |
| `GET` | `/api/events/{center_id}/{event_id}` | Single event detail |
| `POST` | `/api/events/{center_id}/{event_id}/approve` | Approve event |
| `POST` | `/api/events/{center_id}/{event_id}/reject` | Reject event |
| `PATCH` | `/api/events/{center_id}/{event_id}` | Inline edit |

> **Route ordering** matters in FastAPI — specific paths (`history/{center_id}`)
> must be defined before catch-all paths (`{center_id}/{event_id}`), otherwise
> FastAPI tries to parse "history" as a UUID and returns 422.

---

## 9. React PWA Review Console

### Architecture

```
frontend/console/ (Vite + React)
├── App.jsx            ← state management, data fetching, layout
├── api.js             ← fetch wrappers for all 8 backend endpoints
├── index.css          ← design system (CSS custom properties)
└── components/
    ├── EventCard.jsx  ← approve/reject/edit card + read-only history mode
    ├── EmptyState.jsx ← "All caught up!" messages
    └── Toast.jsx      ← auto-dismiss notifications (3s, slide-in/out)
```

### State flow

```
URL ?center=UUID
    │
    ▼
App.jsx reads center_id from query params
    │
    ├── role state: "teacher" | "director" (toggle)
    ├── view state: "pending" | "history" (toggle)
    │
    ├── pending + teacher → fetchTeacherQueue(centerId)
    ├── pending + director → fetchDirectorQueue(centerId)
    └── history → fetchHistory(centerId)
    │
    ▼
Events grouped by child_name → rendered as EventCard list
    │
    ├── Approve → POST /approve → remove card + toast ✅
    ├── Reject → POST /reject → remove card + toast ℹ️
    ├── Edit → inline form → PATCH → refresh + toast ✅
    └── Batch Approve → POST /batch-approve → remove group + toast ✅
```

### Key features

| Feature | Implementation |
|---------|---------------|
| Auto-refresh | `setInterval(loadEvents, 15000)` — disabled in history view |
| Batch approve | "Approve All" button in child group header |
| Toast notifications | `Toast.jsx` with `toastIn`/`toastOut` CSS animations |
| Read-only history | `readOnly` prop on EventCard hides actions, shows status badge |
| Dark mode | CSS custom properties: `--bg-primary: #0f1117` |
| Mobile responsive | `@media (max-width: 640px)` flex-wrap, full-width buttons |
| PWA installable | `manifest.json` with `display: standalone` |

### Design system tokens (CSS)

```css
--bg-primary: #0f1117      /* app background */
--bg-card: #21242f          /* card background */
--accent: #6c5ce7           /* purple — active toggles */
--approve: #00c853          /* green — approve buttons */
--reject: #ff5252           /* red — reject buttons */
--edit: #ffc107             /* yellow — edit buttons */
--teacher-badge: #40c4ff    /* blue — teacher review tier */
--director-badge: #e040fb   /* magenta — director review tier */
```

---

## 10. Middleware & Observability

Three middleware layers in `middleware.py` (order matters — outermost first):

```python
app.add_middleware(GlobalExceptionMiddleware)   # 1. catches all errors
app.add_middleware(RequestTimingMiddleware)      # 2. logs duration
app.add_middleware(RequestIDMiddleware)          # 3. assigns X-Request-ID
```

| Middleware | What It Does | C++ Analogy |
|-----------|-------------|-------------|
| `RequestIDMiddleware` | UUID per request, stored in `request.state` | Thread-local request context |
| `RequestTimingMiddleware` | Logs `POST /webhook/whatsapp → 200 (863ms)` | Timer RAII wrapper |
| `GlobalExceptionMiddleware` | Catches unhandled exceptions, returns JSON errors | Top-level try/catch in main loop |

Log format:
```
2026-04-03 09:57:20,177 | WARNING | backend.routers.whatsapp | === INCOMING WHATSAPP ===
2026-04-03 09:57:21,035 | INFO | backend.middleware | POST /webhook/whatsapp → 200 (863ms)
```

---

## 11. Configuration & Secrets

### `config.py` — Pydantic Settings

```python
class Settings(BaseSettings):
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    openai_api_key: str = ""
    database_url: str = "sqlite:///./daycare.db"
    environment: str = "development"

    model_config = {"env_file": ".env"}

@lru_cache    # singleton pattern — constructed once
def get_settings() -> Settings:
    return Settings()
```

C++ equivalent: `static Settings& get_settings() { static Settings s; return s; }`

### `.env` file (git-ignored!)
```
TWILIO_ACCOUNT_SID=ACfbca...
TWILIO_AUTH_TOKEN=a9e05a...
OPENAI_API_KEY=sk-proj-...
DATABASE_URL=postgresql://user:pass@host:5432/daycare
ENVIRONMENT=development
```

---

## 12. Testing Strategy

**54 tests total**, all using SQLite in-memory databases for speed and isolation.

### Test architecture

```python
@pytest.fixture()
def db_session():
    """Create isolated in-memory DB + session per test."""
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Override FastAPI dependency to use test session
    app.dependency_overrides[get_db] = lambda: (yield db)

    yield db
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)
```

Each test gets a **fresh database** — no cross-test contamination. The `StaticPool`
ensures SQLite `:memory:` reuses the same connection.

### Test coverage

| File | Tests | What It Validates |
|------|-------|-------------------|
| `test_events_api.py` | 19 | All 8 endpoints, multi-tenant isolation, batch approve, history filter |
| `test_events_handlers.py` | 36 | CRUD operations, child resolution, status transitions |
| `test_whatsapp_webhook.py` | 5 | Voice pipeline (mocked), text extraction, unregistered phone |

### Running tests

```bash
source venv/bin/activate
pytest -q                      # 54 passed in ~1s
python -m ruff check --fix .   # linting
python -m ruff format .        # formatting
```

---

## 13. Infrastructure (Twilio, ngrok, uvicorn)

### How the pieces connect

```
Your Phone                Internet               Your Mac
┌─────────┐    ┌────────────────────────┐    ┌──────────────────────────┐
│WhatsApp  │──▸│ Twilio Cloud           │──▸│ ngrok tunnel             │
│  app     │   │ (receives msg,         │   │ (forwards HTTPS to local)│
│          │   │  POSTs to webhook URL) │   │         │                │
│          │◂──│ (sends TwiML reply)    │◂──│         ▼                │
└─────────┘    └────────────────────────┘   │   localhost:8000         │
                                            │   uvicorn + FastAPI      │
                                            │         │                │
                                            │    ┌────▼────┐           │
                                            │    │PostgreSQL│           │
                                            │    └─────────┘           │
                                            │    ┌────▼────┐           │
                                            │    │React PWA│ :5173     │
                                            │    └─────────┘           │
                                            └──────────────────────────┘
```

### Development commands

```bash
# Terminal 1: Backend
source venv/bin/activate
uvicorn backend.main:app --reload

# Terminal 2: Frontend
cd frontend/console && npm run dev

# Terminal 3: Tunnel (for WhatsApp testing)
ngrok http 8000

# Open console:
# http://localhost:5173/?center=YOUR_CENTER_UUID
```

### Production (Week 9)

ngrok goes away. Deploy backend to Railway/Fly.io with a real domain.
Frontend builds to static files (`npm run build`) served from CDN.

---

## What's Built vs. What's Next

| Week | Issues | Status |
|------|--------|--------|
| 1–2 | Voice Pipeline + WhatsApp + DB + Logging (#1–#5) | ✅ Done |
| 3 | Admin Review Console + Approve/Edit/Reject (#6–#7) | ✅ Done |
| 4 | Activity Log + Center Onboarding + Legal (#8–#9, L-1..L-5) | 🔲 Next |
| 5–6 | Parent Portal + AI Narrative (#10–#12) | 🔲 Planned |
| 7–8 | Billing + CSV Migration (#13–#15) | 🔲 Planned |
| 9–10 | Pilot Launch + Iteration (#16–#18) | 🔲 Planned |
