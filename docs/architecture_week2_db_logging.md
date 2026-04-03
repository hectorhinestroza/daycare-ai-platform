# Daycare Platform — Week 2 Tech Spec
## PostgreSQL Multi-Tenant Design & Observability

This document provides a detailed breakdown of the Week 2 implementation, targeting senior engineers joining the project. The primary objectives were:
1. Transitioning from an in-memory data store to a persistent, production-ready PostgreSQL backend.
2. Building a strict multi-tenant architecture for Data Isolation.
3. Adding essential observability and robust error handling to the application edge.

---

## 1. Directory Structure & Modularization

The backend follows a standard, scalable FastAPI layout to separate concerns:
- `backend/database.py`: Core SQLAlchemy config, engine setup, and session lifecycle (`get_db` FastAPI dependency).
- `backend/models.py`: Declarative ORM entities mirroring the domain.
- `backend/crud.py`: Database access layer holding all raw SQL logic (queries + writes).
- `backend/middleware.py`: Request-level interceptors (timing, Request ID tracing, exception handling).
- `backend/routers/`: HTTP transport layer (e.g., `whatsapp.py`), orchestrating services + DB via dependencies.
- `schemas/`: Pure Pydantic domain models serving as validating DTOs (Data Transfer Objects).
- `alembic/`: Database migration environment.

## 2. Multi-Tenant Database Architecture

### The `center_id` Enforcement Rule
The platform is designed to house multiple daycare centers in a single database. To guarantee absolute data isolation, **every single operational table** in the system strictly requires a `center_id` Foreign Key.

This applies to: `admins`, `teachers`, `rooms`, `children`, `events`, and `photos`.
By enforcing this constraint at the schema level, we prevent cross-tenant data leaks. Any query touching operational data *must* filter by `center_id`. 

The `backend/crud.py` layer abstracts this implementation detail:
```python
def get_events_by_child(db: Session, center_id: uuid.UUID, child_name: str):
    return db.query(Event).filter(
        Event.center_id == center_id,    # <-- Enforced tenant filtering
        Event.child_name == child_name
    ).all()
```

### Table Relationships
1. **Centers**: Top-level entity.
2. **Rooms**: Belongs to Center.
3. **Children**: Belongs to Center and to Room. Represents the *System of Record* target for all extracted Voice Notes.
4. **Teachers**: Belongs to Center and to Room. Their configured `phone` number resolves incoming Webhooks to the correct Center context.
5. **Events**: Represents the AI-structured output (Food, Nap, Incident, etc.). Belongs to Center, resolved to the Teacher who sent the memo, and eventually bound to the Child.

## 3. Webhook Integration Refactor

The Twilio Webhook router (`backend/routers/whatsapp.py`) previously relied on a mock in-memory dict. It was refactored to securely integrate with the DB:

1. **Dependency Injection**: The router receives an active DB session via `Depends(get_db)`.
2. **Authentication/Context Resolution**: 
   - Upon receiving a WhatsApp message, the `From` parameter (phone number) is used to invoke `get_teacher_by_phone(db, phone)`.
   - If the number is unregistered, the webhook safely aborts and returns an XML response alerting the user.
   - If found, the Teacher entity provides the target `center_id` for the session.
3. **Data Persistence**:
   - The audio is downloaded, transcribed via Whisper, and structured via GPT-4o.
   - The pure Pydantic `BaseEvent` objects returned by the LLM are mapped to SQLAlchemy `Event` models via `create_event_from_base` and flushed to the DB in a `PENDING` state.

## 4. Middleware & Observability Edge

To ensure production-readiness, robust middleware was wrapped around the FastAPI edge:

### RequestIDMiddleware
Injects an `X-Request-ID` UUID Header into every request context. This guarantees that logs originating from a single request (webhook entry -> db query -> LLM call) can be confidently correlated during debugging.

### RequestTimingMiddleware
Measures end-to-end execution latency before the response physically goes out the door, logging the `process_time` (useful for monitoring Whisper/GPT-4o latency bottlenecks).

### GlobalExceptionMiddleware
Protects internal stack traces from leaking to the outside world.
- If an unhandled exception bridges up to the FastAPI edge, it dumps the full stack trace to the internal structured logger (tied to the Request ID).
- Returning a sterile `500 Server Error` JSON payload to the client.

## 5. Testing Strategy
The test suite was upgraded to support isolated, in-core database interactions.
Using a SQLite `in-memory` engine bound to a `StaticPool`, the `test_crud.py` and `test_whatsapp_webhook.py` files instantly boot up a clean schema, seed mock data, and execute tests with `check_same_thread=False` to securely test FastAPI Router logic handling concurrent DB sessions. All 39 tests currently clear.
