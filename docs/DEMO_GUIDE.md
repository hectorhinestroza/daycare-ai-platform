# Daycare AI Platform — Demo & Testing Guide

## Overview

Three separate portals, one backend. A teacher records a voice note → AI structures it into events → teacher/director approves → parent sees it live.

```
Teacher (WhatsApp voice note)
    ↓
Backend (Whisper STT → GPT-4o extraction → events)
    ↓
Teacher Portal (review + one-tap approve)
    ↓
Director Portal (flagged events + center management)
    ↓
Parent Portal (live feed + daily snapshot)
```

---

## Portal URLs

All portals are served from the same frontend app. The URL path determines which portal loads.

| Portal | URL Pattern | Purpose |
|--------|------------|---------|
| Director | `/director/{center_id}` | Manage center, review flagged events, onboarding |
| Teacher | `/teacher/{center_id}/{teacher_id}` | Review AI-structured events, one-tap approve |
| Parent | `/parent/{center_id}/{child_id}` | Live feed of approved events for their child |
| Legacy | `/?center={center_id}` | Dev mode with role toggle (teacher/director) |

### Example URLs (replace UUIDs with real ones)

```
Director:  https://your-domain.com/director/abc123-...
Teacher:   https://your-domain.com/teacher/abc123-.../teacher-uuid-...
Parent:    https://your-domain.com/parent/abc123-.../child-uuid-...
```

---

## API Endpoints

Base URL: `http://localhost:8000` (dev) or your production URL.

Interactive docs: `{base}/docs` (Swagger UI) or `{base}/redoc`

### WhatsApp Webhook
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/webhook/whatsapp` | Twilio WhatsApp webhook — receives voice notes + photos |

### Events (Review System)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/events/pending/teacher/{center_id}` | Teacher queue (high-confidence events) |
| GET | `/api/events/pending/director/{center_id}` | Director queue (flagged/low-confidence) |
| GET | `/api/events/history/{center_id}` | Approved/rejected event history |
| GET | `/api/events/feed/{center_id}/{child_id}` | **Parent feed** — approved events for a child |
| GET | `/api/events/{center_id}/{event_id}` | Single event detail |
| POST | `/api/events/{center_id}/{event_id}/approve` | Approve an event |
| POST | `/api/events/{center_id}/{event_id}/reject` | Reject an event |
| PATCH | `/api/events/{center_id}/{event_id}` | Edit event (child_name, details, type, time) |
| POST | `/api/events/{center_id}/batch-approve` | Approve all pending events for a child |

### Onboarding (Center Management)
| Method | Endpoint | Description |
|--------|----------|-------------|
| **Rooms** | | |
| GET | `/api/rooms/{center_id}` | List rooms |
| POST | `/api/rooms/{center_id}` | Create room `{ "name": "..." }` |
| PATCH | `/api/rooms/{center_id}/{room_id}` | Rename room |
| DELETE | `/api/rooms/{center_id}/{room_id}` | Delete room |
| **Teachers** | | |
| GET | `/api/teachers/{center_id}` | List teachers |
| POST | `/api/teachers/{center_id}` | Create teacher `{ "name": "...", "phone": "+1..." }` |
| PATCH | `/api/teachers/{center_id}/{teacher_id}` | Update teacher (name, phone, room_id, is_active) |
| **Children** | | |
| GET | `/api/children/{center_id}` | List children (filters: `?room_id=...&status=...`) |
| GET | `/api/children/{center_id}/{child_id}` | Child detail (includes parent_contacts) |
| POST | `/api/children/{center_id}` | Enroll child `{ "name": "...", "dob": "2022-01-15" }` |
| PATCH | `/api/children/{center_id}/{child_id}` | Update child |
| **Contacts** | | |
| GET | `/api/children/{center_id}/{child_id}/contacts` | List contacts for a child |
| POST | `/api/children/{center_id}/{child_id}/contacts` | Add contact |
| PATCH | `/api/contacts/{center_id}/{contact_id}` | Update contact |

### Activity Log
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/activity/{center_id}` | Audit trail (filters: `?action=...&event_id=...`) |

---

## Manual Testing Walkthrough

### Prerequisites
- Backend running (`uvicorn backend.main:app --reload`)
- Frontend running (`cd frontend/console && npm run dev`)
- PostgreSQL with a center created
- Twilio WhatsApp sandbox configured (for voice note testing)

### Step 0: Get your center_id

If you don't have one yet, check the database or create via psql:

```sql
SELECT id, name FROM centers;
```

### Step 1: Director — Set up the center

1. Open **Director Portal**: `http://localhost:5173/director/{center_id}`
2. Click the **Center** tab in the bottom nav
3. **Rooms tab**: Create classrooms (e.g., "Toddlers", "Pre-K")
4. **Teachers tab**: Add teachers with their WhatsApp phone numbers and assign to rooms
5. **Children tab**: Enroll children, assign to rooms, add parent contacts
6. Expand a child card → copy the **Parent Portal Link**

### Step 2: Teacher — Send a voice note

1. Send a WhatsApp voice note to the Twilio sandbox number from the teacher's registered phone
   - Example: "Jojo had rice and beans for lunch at 12pm. He napped from 1 to 2:30. Emma did a finger painting activity."
2. The backend will:
   - Receive the audio via Twilio webhook
   - Transcribe with Whisper
   - Extract structured events with GPT-4o
   - Store as PENDING events

### Step 3: Teacher — Review events

1. Open **Teacher Portal**: `http://localhost:5173/teacher/{center_id}/{teacher_id}`
2. Pending events appear grouped by child
3. Review each event — **Confirm** (one tap) or **Edit** if AI got something wrong
4. Use **Approve All** for a child if everything looks correct

### Step 4: Director — Handle flagged events

1. Open **Director Portal**: `http://localhost:5173/director/{center_id}`
2. The **Queue** tab shows only flagged events (incidents, billing, low-confidence)
3. Approve, edit, or reject as needed
4. Check **Activity** tab for the audit trail

### Step 5: Parent — View live feed

1. Open the **Parent Portal** link (copied in Step 1): `http://localhost:5173/parent/{center_id}/{child_id}`
2. Approved events appear in real-time (auto-refreshes every 10 seconds)
3. Events are grouped by date with timestamps
4. The **Daily Snapshot** at the top summarizes the day (meals, naps, activities)

### Testing without WhatsApp (API-only)

You can create test events directly via the API to test the review flow without Twilio:

```bash
# Create a test event
curl -X POST http://localhost:8000/api/events/{center_id}/{event_id}/approve

# Or use the Swagger UI at http://localhost:8000/docs
# to create events via the database directly
```

For quick testing, insert events directly into the DB:

```sql
INSERT INTO events (id, center_id, child_id, child_name, event_type, event_time, details, raw_transcript, review_tier, confidence_score, needs_director_review, needs_review, status)
VALUES (
  gen_random_uuid(),
  '{center_id}',
  '{child_id}',
  'Jojo Washington',
  'food',
  NOW(),
  'Had rice and beans for lunch',
  'Jojo had rice and beans for lunch at noon',
  'teacher',
  0.95,
  false,
  false,
  'PENDING'
);
```

---

## Production Deployment

### Option A: Railway (recommended for quick demo)

Railway can deploy both the backend and frontend from the same repo.

**Backend service:**
- Root directory: `/` (or `/backend`)
- Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- Environment variables: `DATABASE_URL`, `OPENAI_API_KEY`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`
- Add a PostgreSQL plugin for the database

**Frontend service:**
- Root directory: `/frontend/console`
- Build command: `npm run build`
- Output directory: `dist`
- Environment variable: `VITE_API_URL=https://your-backend.up.railway.app`

### Option B: Fly.io

Similar setup — Dockerfile needed for each service.

### Option C: Quick tunnel for demo (ngrok / Cloudflare Tunnel)

If you just need your friend to access your local machine for the demo:

```bash
# Terminal 1: Backend
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Frontend (set API URL to your tunnel)
VITE_API_URL=https://your-tunnel.ngrok.io npm run dev -- --host 0.0.0.0

# Terminal 3: Tunnel
ngrok http 8000   # tunnels the backend
# or
cloudflared tunnel --url http://localhost:8000
```

Then update the frontend's `VITE_API_URL` to point to the tunneled backend URL.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `OPENAI_API_KEY` | Yes | For Whisper STT + GPT-4o extraction |
| `TWILIO_ACCOUNT_SID` | Yes | Twilio account for WhatsApp |
| `TWILIO_AUTH_TOKEN` | Yes | Twilio auth |
| `VITE_API_URL` | Frontend | Backend URL (default: `http://localhost:8000`) |
| `ENVIRONMENT` | No | `development` or `production` |
