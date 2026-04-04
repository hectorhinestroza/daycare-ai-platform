"""Core event schemas — source of truth for the entire platform.

Tier 1: Voice-capturable events (food, nap, potty, kudos, observation,
        health_check, absence, note, activity)
Tier 2: High-stakes events with mandatory review (incident, medication)
Tier 3: Skip for V1 (photo/video handled as media attachments, not events)
"""

from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

# ─── Event Types ──────────────────────────────────────────────

class EventType(str, Enum):
    """Matches Brightwheel categories. Lowercase values for consistency."""
    # Tier 1 — Core voice-capturable
    FOOD = "food"
    NAP = "nap"
    POTTY = "potty"
    KUDOS = "kudos"
    OBSERVATION = "observation"
    HEALTH_CHECK = "health_check"
    ABSENCE = "absence"
    NOTE = "note"
    ACTIVITY = "activity"  # Basketball, art, music, outdoor play, etc.
    # Tier 2 — High-stakes (always needs_review=True)
    INCIDENT = "incident"
    MEDICATION = "medication"


class EventStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


# ─── needs_review defaults by event type ──────────────────────

# These types ALWAYS require director review — non-negotiable
ALWAYS_REVIEW_TYPES = {EventType.INCIDENT, EventType.MEDICATION}

# These types are low-stakes and default to auto-approve via teacher
LOW_RISK_TYPES = {
    EventType.FOOD, EventType.NAP, EventType.POTTY,
    EventType.KUDOS, EventType.ABSENCE, EventType.ACTIVITY,
}

# Standard ops — no special handling
STANDARD_TYPES = {EventType.NOTE, EventType.OBSERVATION, EventType.HEALTH_CHECK}


# ─── Base Event ───────────────────────────────────────────────

class BaseEvent(BaseModel):
    """Base event extracted from a teacher's voice memo or text.

    Every event flows through: AI extraction → Pydantic validation
    → review (teacher or director) → parent portal.
    """
    id: UUID
    center_id: str                                     # multi-tenant key
    child_name: str
    event_type: EventType
    event_time: Optional[datetime] = None
    details: Optional[str] = None                      # free-text description

    # Three-tier review system
    review_tier: Literal["teacher", "director"]        # who must approve
    confidence_score: float                            # 0.0–1.0 from GPT-4o
    needs_director_review: bool                        # True for incidents, meds, low confidence
    needs_review: bool = False                         # legacy compat flag

    status: EventStatus = EventStatus.PENDING
    raw_transcript: str                                # original text for audit
    photo_ids: List[str] = Field(default_factory=list)


# ─── Tier 2: Specialized Event Models ─────────────────────────

class NapEvent(BaseEvent):
    """Nap has duration logic — AI calculates duration if both times given."""
    event_type: Literal[EventType.NAP] = EventType.NAP
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None             # AI calculates if both times given
    quality: Optional[Literal["restful", "restless", "refused"]] = None


class IncidentEvent(BaseEvent):
    """Incidents ALWAYS require director review — legal/liability weight.

    Many states require parent signature on incident reports.
    """
    event_type: Literal[EventType.INCIDENT] = EventType.INCIDENT
    description: str = ""
    body_location: Optional[str] = None                # "left knee", "forehead"
    severity: Literal["minor", "moderate", "urgent"] = "minor"
    requires_parent_notification: bool = True
    requires_signature: bool = True                    # many states require this
    needs_review: Literal[True] = True                 # ALWAYS true, non-negotiable
    review_tier: Literal["director"] = "director"      # ALWAYS director
    needs_director_review: Literal[True] = True        # ALWAYS true


class MedicationEvent(BaseEvent):
    """Medication ALWAYS requires director review — HIPAA + state law."""
    event_type: Literal[EventType.MEDICATION] = EventType.MEDICATION
    medication_name: str = ""
    dosage: Optional[str] = None
    time_administered: Optional[datetime] = None
    administered_by: Optional[str] = None
    requires_parent_auth_on_file: bool = True
    needs_review: Literal[True] = True                 # ALWAYS true
    review_tier: Literal["director"] = "director"      # ALWAYS director
    needs_director_review: Literal[True] = True        # ALWAYS true


# ─── Response Models ──────────────────────────────────────────

class EventResponse(BaseModel):
    message: str
    events: List[BaseEvent]
