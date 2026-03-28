from enum import Enum
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field

class EventType(str, Enum):
    MEAL = "MEAL"
    NAP = "NAP"
    DIAPER = "DIAPER"
    ACTIVITY = "ACTIVITY"
    NOTE_TO_PARENT = "NOTE_TO_PARENT"
    PICKUP = "PICKUP"
    DROP_OFF = "DROP_OFF"
    INCIDENT_MINOR = "INCIDENT_MINOR"
    INCIDENT_MAJOR = "INCIDENT_MAJOR"
    BILLING_LATE_PICKUP = "BILLING_LATE_PICKUP"
    BILLING_EXTRA_HOURS = "BILLING_EXTRA_HOURS"
    BILLING_DROP_IN = "BILLING_DROP_IN"

class EventStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class BaseEvent(BaseModel):
    id: UUID
    review_tier: Literal["teacher", "director"] # who must approve
    confidence_score: float
    needs_director_review: bool  # True for incidents, billing, low confidence
    center_id: str
    child_name: str
    event_type: EventType
    event_time: Optional[datetime] = None
    needs_review: bool = False
    status: EventStatus = EventStatus.PENDING
    raw_transcript: str
    photo_ids: List[str] = Field(default_factory=list)

class EventResponse(BaseModel):
    message: str
    events: List[BaseEvent]
