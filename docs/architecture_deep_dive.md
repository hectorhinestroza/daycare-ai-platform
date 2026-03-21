# Daycare AI Platform — Architecture Deep Dive

> Written for a C++ engineer new to Python and frontend. Every concept is
> explained from first principles with C++ analogies where they help.

---

## Table of Contents

1. [Project Layout & Module System](#1-project-layout--module-system)
2. [Python Fundamentals (for C++ Engineers)](#2-python-fundamentals-for-c-engineers)
3. [FastAPI — The HTTP Server](#3-fastapi--the-http-server)
4. [Pydantic — The Type System](#4-pydantic--the-type-system)
5. [The Voice Pipeline (End‑to‑End)](#5-the-voice-pipeline-end-to-end)
6. [Configuration & Secrets](#6-configuration--secrets)
7. [Testing](#7-testing)
8. [Infrastructure (Twilio, ngrok, uvicorn)](#8-infrastructure-twilio-ngrok-uvicorn)

---

## 1. Project Layout & Module System

### Directory structure

```
day_care/
├── .env                      # secrets (git-ignored)
├── .gitignore
├── GEMINI.md                 # agent context file
├── backend/
│   ├── __init__.py           # makes this a Python "package"
│   ├── main.py               # entry point — like main.cpp
│   ├── config.py             # loads .env into typed settings
│   ├── requirements.txt      # like a CMakeLists dependency list
│   ├── routers/
│   │   ├── __init__.py
│   │   └── whatsapp.py       # HTTP endpoint handler
│   ├── services/
│   │   ├── __init__.py
│   │   ├── transcription.py  # Whisper API wrapper
│   │   └── extraction.py     # GPT-4o wrapper
│   └── utils/
│       ├── __init__.py
│       └── media.py          # Twilio media downloader
├── schemas/
│   ├── __init__.py
│   ├── events.py             # core data models
│   ├── narrative.py          # daily report model
│   └── billing.py            # billing event model
├── tests/
│   ├── __init__.py
│   ├── test_whatsapp_webhook.py
│   ├── test_transcription.py
│   └── test_extraction.py
├── frontend/console/          # (empty — Week 3)
├── frontend/parent/           # (empty — Week 5)
└── docs/
    ├── PRD.md
    └── competitive_research.md
```

### C++ analogy: `__init__.py`

In C++ you have header files and `#include`. In Python, a directory becomes
an importable **package** only if it contains an `__init__.py` file (can be
empty). Think of it like declaring a namespace.

```cpp
// C++: you'd write
#include "backend/services/transcription.h"

// Python equivalent:
from backend.services.transcription import transcribe_audio
```

Every `__init__.py` in our tree is empty — they just tell Python "this
directory is a module, you can import from it."

### How imports work

Python resolves imports from the **root** of `PYTHONPATH`. That's why we
run the server with `PYTHONPATH=.` — it tells Python to treat the project
root (`day_care/`) as the import base, so `from backend.services.extraction
import extract_events` resolves correctly.

---

## 2. Python Fundamentals (for C++ Engineers)

### Types are optional but we use them everywhere

Python is dynamically typed, but we use **type hints** (like C++ concepts
but at the annotation level). They don't enforce at runtime by default —
**Pydantic** does the enforcement for us (more on that in §4).

```python
# Type-annotated function — similar to a C++ function signature
async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.ogg") -> str:
```

| C++ Concept         | Python Equivalent                        |
|---------------------|------------------------------------------|
| `std::string`       | `str`                                    |
| `std::vector<T>`    | `List[T]` or `list[T]`                  |
| `std::optional<T>`  | `Optional[T]`                            |
| `enum class`        | `class MyEnum(str, Enum)`                |
| `struct`            | `class MyModel(BaseModel)` (Pydantic)    |
| `const`             | No direct equivalent (immutable by convention) |
| `nullptr`           | `None`                                   |
| header/source split | No split — everything in one `.py` file  |

### `async` / `await` — like C++20 coroutines

Our pipeline is I/O-bound (waiting for OpenAI API, Twilio downloads). Python's
`async/await` works like C++20 coroutines:

```python
# Python
async def transcribe_audio(audio_bytes: bytes) -> str:
    result = await some_api_call()   # yields control while waiting
    return result

# C++20 equivalent concept:
# task<std::string> transcribe_audio(std::vector<uint8_t> audio_bytes) {
#     auto result = co_await some_api_call();
#     co_return result;
# }
```

The `async` keyword makes a function a coroutine. `await` suspends execution
until the I/O operation completes, letting other requests be handled in the
meantime. FastAPI manages the event loop for us (like `boost::asio::io_context`).

### Decorators — like C++ attributes

```python
@app.get("/health")          # ← this is a decorator
async def health():
    return {"status": "healthy"}
```

A decorator wraps a function with additional behavior. `@app.get("/health")`
registers `health()` as the handler for `GET /health`. Think of it like
a C++ attribute `[[route("/health", GET)]]` if such a thing existed.

### `Dict`, `List`, `Optional`

```python
from typing import Dict, List, Optional

# Dict[str, str] ≈ std::unordered_map<std::string, std::string>
# List[str]      ≈ std::vector<std::string>
# Optional[str]  ≈ std::optional<std::string>
```

---

## 3. FastAPI — The HTTP Server

FastAPI is our web framework. Think of it as a modern, async HTTP server
library — like combining Boost.Beast with automatic request parsing and
OpenAPI docs generation.

### Entry point: [main.py](file:///Users/hector/Documents/Projects/day_care/backend/main.py)

```python
import logging
from fastapi import FastAPI
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
load_dotenv()       # reads .env file into environment variables

from backend.routers.whatsapp import router as whatsapp_router

app = FastAPI(title="Daycare AI Platform API")
app.include_router(whatsapp_router)   # register webhook routes

@app.get("/")
async def root():
    return {"status": "ok", "message": "Daycare AI Platform API is running"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
```

**Key concepts:**

| FastAPI Concept      | What It Does                                        | C++ Analogy |
|----------------------|-----------------------------------------------------|-------------|
| `FastAPI()`          | Creates the application                             | `main()` creating a server |
| `@app.get("/path")`  | Registers a GET route handler                       | Route registration table |
| `include_router(r)` | Mounts a group of routes from another file          | Linking a sub-module |
| `Form("default")`   | Extracts a form field from POST body                | Parsing POST parameters |
| `Response`           | Raw HTTP response object                            | `http::response<string>` |

### How a request flows

```
Client sends POST /webhook/whatsapp
    │
    ▼
uvicorn (ASGI server, like nginx but for Python)
    │
    ▼
FastAPI app (main.py)
    │  app.include_router(whatsapp_router) registered this route
    ▼
whatsapp_webhook() function in routers/whatsapp.py
    │
    ├─ Text? → extract_events() → TwiML response
    ├─ Voice? → download → transcribe → extract → TwiML response
    ├─ Photo? → log metadata → TwiML response
    └─ Other? → fallback greeting
```

### Running the server

```bash
PYTHONPATH=. uvicorn backend.main:app --reload --port 8000
#            ^^^^^^^ ^^^^^^^^^^^^^^^ ^^^^^^^^
#            server   module:variable  hot-reload on file changes
```

`uvicorn` is the ASGI server (like running your compiled binary, but for
Python web apps). `backend.main:app` tells it: "import the `app` variable
from `backend/main.py`." The `--reload` flag watches files and restarts
automatically — similar to `inotifywait` + rebuild in C++.

---

## 4. Pydantic — The Type System

Pydantic is our runtime type enforcement layer. In C++, the compiler
enforces types. In Python, Pydantic does this at runtime — every field
is validated when you construct an object.

### Core schema: [events.py](file:///Users/hector/Documents/Projects/day_care/schemas/events.py)

```python
class EventType(str, Enum):      # ← like enum class EventType : std::string
    MEAL = "MEAL"
    NAP = "NAP"
    DIAPER = "DIAPER"
    ACTIVITY = "ACTIVITY"
    # ...12 total types

class EventStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class BaseEvent(BaseModel):      # ← like a struct with validation
    id: UUID                     # auto-generated unique ID
    center_id: str               # multi-tenant key (CRITICAL)
    child_name: str
    event_type: EventType        # enforced enum — can't be arbitrary string
    event_time: Optional[datetime] = None
    needs_review: bool = False   # flagged for admin review
    status: EventStatus = EventStatus.PENDING
    raw_transcript: str          # original text for audit
    photo_ids: List[str] = Field(default_factory=list)
```

**C++ analogy:**
```cpp
// If C++ had runtime validation like Pydantic:
struct BaseEvent {
    uuid id;
    string center_id;        // multi-tenant — EVERY event has this
    string child_name;
    EventType event_type;     // compiler-enforced enum
    optional<datetime> event_time = nullopt;
    bool needs_review = false;
    EventStatus status = EventStatus::PENDING;
    string raw_transcript;
    vector<string> photo_ids = {};

    // Pydantic auto-generates:
    // - constructor with validation
    // - JSON serialization/deserialization
    // - field type checking at construction time
};
```

### What happens when validation fails

```python
# This would THROW a ValidationError (like a C++ exception):
event = BaseEvent(
    id=uuid4(),
    center_id="c1",
    child_name="Jason",
    event_type="INVALID_TYPE",   # ← not in EventType enum — REJECTED
    raw_transcript="test",
)
# pydantic.ValidationError: 1 validation error for BaseEvent
#   event_type: value is not a valid enumeration member
```

This is our moat against LLM hallucination. GPT-4o can return whatever
it wants, but if it doesn't match our schema, the event is **rejected**.

### Architecture rule: schemas are the contract

```
schemas/events.py     ← source of truth
    │
    ├── backend/services/extraction.py validates against this
    ├── backend/routers/whatsapp.py returns these
    └── (Week 2) database tables will mirror this
```

All LLM outputs go through Pydantic before storage. This is non-negotiable.

---

## 5. The Voice Pipeline (End‑to‑End)

This is the core of the product. Here's the complete data flow:

```
┌──────────────┐    ┌────────────┐    ┌───────────────┐    ┌──────────────┐    ┌────────────┐
│  Teacher     │───▸│  WhatsApp  │───▸│  Twilio       │───▸│  Our Server  │───▸│  Teacher   │
│  sends voice │    │  app       │    │  webhook POST │    │  processes   │    │  gets reply│
│  memo        │    │            │    │  to /webhook/ │    │  & extracts  │    │  "Got it!" │
│              │    │            │    │  whatsapp     │    │  events      │    │            │
└──────────────┘    └────────────┘    └───────────────┘    └──────────────┘    └────────────┘
```

### Step 1: Twilio webhook receives the message

When someone sends a WhatsApp message to our Twilio number, Twilio makes
an HTTP POST to our webhook URL with form data:

```
POST /webhook/whatsapp
Content-Type: application/x-www-form-urlencoded

From=whatsapp:+18328667291
Body=                          ← empty for voice memos
NumMedia=1
MediaUrl0=https://api.twilio.com/2010-04-01/Accounts/.../Media/...
MediaContentType0=audio/ogg
ProfileName=Hector Hinestroza
MessageSid=SMd2e1b49662e8...
SmsStatus=received
```

### Step 2: Webhook handler routes the message

[whatsapp.py](file:///Users/hector/Documents/Projects/day_care/backend/routers/whatsapp.py) determines the message type:

```python
@router.post("/whatsapp")
async def whatsapp_webhook(
    From: str = Form(""),
    Body: str = Form(""),
    NumMedia: str = Form("0"),
    MediaUrl0: str = Form(None),
    MediaContentType0: str = Form(None),
    # ...
) -> Response:
    phone = From
    body = Body.strip()
    num_media = int(NumMedia)

    # Route based on message type:
    if body and not num_media:           # text message
        ...
    elif num_media >= 1 and "audio" in MediaContentType0:  # voice
        ...
    elif num_media >= 1 and "image" in MediaContentType0:  # photo
        ...
```

`Form("default")` is FastAPI's way of saying "extract this field from the
POST form data." In C++ terms, it's like parsing a URL-encoded body and
extracting named fields.

### Step 3: Download audio from Twilio

[media.py](file:///Users/hector/Documents/Projects/day_care/backend/utils/media.py) downloads the audio file:

```python
async def download_twilio_media(media_url: str) -> tuple[bytes, str]:
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        response = await client.get(
            media_url,
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            follow_redirects=True,
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "application/octet-stream")
        return response.content, content_type
```

**C++ analogy:** This is like making an authenticated HTTP GET request with
libcurl. `httpx` is Python's modern HTTP client (similar to `cpp-httplib`).
The `async with` pattern is like RAII — it ensures the client connection
is cleaned up when the block exits.

### Step 4: Whisper transcription

[transcription.py](file:///Users/hector/Documents/Projects/day_care/backend/services/transcription.py) sends audio to OpenAI's Whisper API:

```python
async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.ogg") -> str:
    if not audio_bytes:
        raise ValueError("Empty audio data received")

    client = OpenAI(api_key=settings.openai_api_key)

    audio_file = io.BytesIO(audio_bytes)    # wrap bytes as file-like object
    audio_file.name = filename              # Whisper needs the extension

    transcript = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        response_format="text",
    )
    return transcript.strip()
```

**What's happening:**
- `io.BytesIO(audio_bytes)` — wraps raw bytes into a file-like object. In
  C++ this would be like a `std::istringstream` wrapping a byte buffer.
- `whisper-1` is the model name — it's OpenAI's speech-to-text model.
- The API returns plain text (the transcript).

### Step 5: GPT-4o structured extraction

[extraction.py](file:///Users/hector/Documents/Projects/day_care/backend/services/extraction.py) — this is the most critical file:

```python
SYSTEM_PROMPT = """You are an event extraction system for a daycare center.
Extract only what is explicitly stated in the transcript. Do not infer or add detail.
...
You MUST return a JSON object with an "events" key containing an array.
..."""

async def extract_events(transcript, center_id, child_name=None) -> List[BaseEvent]:
    client = OpenAI(api_key=settings.openai_api_key)

    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0,                              # deterministic!
        response_format={"type": "json_object"},    # forces JSON output
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Transcript: {transcript}"},
        ],
    )

    raw_content = response.choices[0].message.content   # raw JSON string
    parsed = json.loads(raw_content)                     # parse to dict

    # Handle response formats
    if isinstance(parsed, dict) and "events" in parsed:
        raw_events = parsed["events"]
    elif isinstance(parsed, dict) and "event_type" in parsed:
        raw_events = [parsed]        # single event as bare dict
    # ...

    # Validate EVERY event through Pydantic
    validated_events = []
    for raw_event in raw_events:
        try:
            event = BaseEvent(
                id=uuid4(),
                center_id=center_id,          # multi-tenant isolation
                child_name=raw_event.get("child_name", "Unknown"),
                event_type=EventType(raw_event["event_type"]),  # enforced enum
                needs_review=raw_event.get("needs_review", True),
                status=EventStatus.PENDING,    # NEVER auto-approved
                raw_transcript=transcript,
                # ...
            )
            validated_events.append(event)
        except (ValidationError, KeyError, ValueError):
            continue   # malformed event skipped — never stored
    return validated_events
```

**Critical design decisions:**

| Decision | Why | Architecture Rule |
|----------|-----|-------------------|
| `temperature=0` | Deterministic extraction — same input, same output every time | NEVER change this |
| `needs_review=True` default | If GPT-4o is uncertain, flag for human review | Never suppress |
| Pydantic validation | LLM outputs are untrusted — validate before storage | ALL LLM outputs must be validated |
| `status=PENDING` | No event reaches parents without admin approval | NEVER auto-approve |
| `center_id` on every event | Multi-tenant isolation from day 1 | Every query must filter by center_id |

### Step 6: Confirmation reply

Back in the webhook, the validated events are formatted into a summary:

```python
def _format_event_summary(events: list) -> str:
    # Groups events by child, counts by type
    # Returns: "Got it! Parsed 2 events for Jason (1 nap, 1 meal)."
```

This is wrapped in TwiML (Twilio Markup Language) — the XML format Twilio
expects as an HTTP response to send a reply back to WhatsApp:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>Got it! Parsed 2 events for Jason (1 nap, 1 meal).
⚠️ 1 event flagged for review.</Message>
</Response>
```

---

## 6. Configuration & Secrets

### [config.py](file:///Users/hector/Documents/Projects/day_care/backend/config.py)

```python
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    openai_api_key: str = ""
    environment: str = "development"

    model_config = {"env_file": ".env"}

@lru_cache            # ← singleton pattern
def get_settings() -> Settings:
    return Settings()
```

**How this works:**
- `BaseSettings` automatically reads from environment variables
- `model_config = {"env_file": ".env"}` also reads from the `.env` file
- `@lru_cache` — this is a **memoization decorator**. It makes `get_settings()`
  return the same instance every time (singleton pattern). In C++:
  ```cpp
  Settings& get_settings() {
      static Settings instance;  // constructed once
      return instance;
  }
  ```

### `.env` file (git-ignored!)
```
TWILIO_ACCOUNT_SID=ACfbca...
TWILIO_AUTH_TOKEN=a9e05a...
OPENAI_API_KEY=sk-proj-...
ENVIRONMENT=development
```

---

## 7. Testing

We use **pytest** — Python's standard test framework. It auto-discovers
files named `test_*.py` and functions/methods prefixed with `test_`.

### Test structure

```python
from unittest.mock import patch, MagicMock, AsyncMock

class TestExtractEvents:
    @pytest.mark.asyncio                     # tells pytest this is async
    @patch("backend.services.extraction.OpenAI")  # replaces OpenAI with a mock
    async def test_single_event_extraction(self, mock_openai_class):
        # Arrange: set up mock to return controlled data
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_response

        # Act: call the function under test
        events = await extract_events("Jason ate lunch", "center_001")

        # Assert: verify the result
        assert len(events) == 1
        assert events[0].child_name == "Jason"
```

**C++ analogy for mocking:**
```cpp
// Like using dependency injection + gmock:
// Instead of calling the real OpenAI API, we inject a mock that returns
// controlled responses. This lets us test our logic without making
// real API calls (fast, deterministic, free).
```

### Running tests

```bash
source venv/bin/activate
PYTHONPATH=. python -m pytest tests/ -v

# Current result: 20 passed in 0.35s
```

### What each test file covers

| File | Tests | What It Validates |
|------|-------|-------------------|
| `test_extraction.py` | 7 | GPT-4o parsing, Pydantic validation, temperature=0 enforcement, malformed event handling |
| `test_transcription.py` | 4 | Whisper API calls, empty audio, empty transcript, API failures |
| `test_whatsapp_webhook.py` | 9 | `/child` commands, voice pipeline (mocked), photos, text extraction, error handling |

---

## 8. Infrastructure (Twilio, ngrok, uvicorn)

### How the pieces connect

```
Your Phone                Internet               Your Mac
┌─────────┐    ┌────────────────────────┐    ┌──────────────────────────┐
│WhatsApp  │───▸│ Twilio Cloud           │───▸│ ngrok tunnel             │
│  app     │    │ (receives msg,         │    │ (forwards HTTPS to local)│
│          │    │  POSTs to webhook URL) │    │         │                │
│          │◂───│ (sends TwiML reply)    │◂───│         ▼                │
└─────────┘    └────────────────────────┘    │   localhost:8000         │
                                             │   uvicorn + FastAPI      │
                                             │         │                │
                                             │         ▼                │
                                             │   Whisper API (OpenAI)   │
                                             │   GPT-4o API (OpenAI)    │
                                             └──────────────────────────┘
```

### Why ngrok?

Twilio needs a **public HTTPS URL** to POST webhook data to. Your laptop
is behind a NAT/firewall. ngrok creates a tunnel:

```
https://oophoric-carlie-unmaliciously.ngrok-free.dev
    ↕ (ngrok tunnel through internet)
http://localhost:8000
    ↕ (uvicorn serving FastAPI app)
```

In production (Week 9), we'll deploy to Railway/Fly.io with a real domain,
and ngrok goes away.

### uvicorn

`uvicorn` is the **ASGI server** — it's the runtime that actually listens
on a port and dispatches HTTP requests to FastAPI. Think of it as the
equivalent of running your compiled C++ server binary. The `--reload` flag
uses `inotify` (or `kqueue` on macOS) to watch for file changes and
restart — very useful during development.

---

## What's Next

With the voice pipeline complete, the next pieces are:

| Issue | What | Status |
|-------|------|--------|
| **#4** | PostgreSQL multi-tenant schema — replace in-memory store with real DB | Next |
| **#5** | Structured logging and error handling middleware | Next |
| **#6–#9** | Admin Review Console (React PWA) | Weeks 3–4 |
| **#10–#12** | Parent Portal + AI Narrative (Next.js) | Weeks 5–6 |
