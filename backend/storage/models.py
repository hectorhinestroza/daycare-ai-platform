"""SQLAlchemy ORM models — mirrors Pydantic schemas in /schemas.

Every table has center_id for multi-tenant isolation.
Every query MUST filter by center_id — this is non-negotiable.

Tables: centers, admins, teachers, rooms, children, events, photos
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from backend.storage.database import Base

# ─── Centers ──────────────────────────────────────────────────


class Center(Base):
    __tablename__ = "centers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    timezone = Column(String(50), default="America/New_York")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    admins = relationship("Admin", back_populates="center")
    teachers = relationship("Teacher", back_populates="center")
    rooms = relationship("Room", back_populates="center")
    children = relationship("Child", back_populates="center")
    events = relationship("Event", back_populates="center")


# ─── Admins ───────────────────────────────────────────────────


class Admin(Base):
    """Directors and VAs who review events and manage the center."""

    __tablename__ = "admins"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    center_id = Column(UUID(as_uuid=True), ForeignKey("centers.id"), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    role = Column(String(20), nullable=False, default="director")  # director | admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    center = relationship("Center", back_populates="admins")


# ─── Teachers ─────────────────────────────────────────────────


class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    center_id = Column(UUID(as_uuid=True), ForeignKey("centers.id"), nullable=False)
    name = Column(String(255), nullable=False)
    phone = Column(String(30), nullable=False, unique=True)  # WhatsApp number (E.164)
    room_id = Column(UUID(as_uuid=True), ForeignKey("rooms.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    center = relationship("Center", back_populates="teachers")
    room = relationship("Room", back_populates="teachers")
    events = relationship("Event", back_populates="teacher")


# ─── Rooms ────────────────────────────────────────────────────


class Room(Base):
    __tablename__ = "rooms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    center_id = Column(UUID(as_uuid=True), ForeignKey("centers.id"), nullable=False)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    center = relationship("Center", back_populates="rooms")
    teachers = relationship("Teacher", back_populates="room")
    children = relationship("Child", back_populates="room")


# ─── Children ─────────────────────────────────────────────────


class Child(Base):
    __tablename__ = "children"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    center_id = Column(UUID(as_uuid=True), ForeignKey("centers.id"), nullable=False)
    name = Column(String(255), nullable=False)
    dob = Column(Date, nullable=True)
    room_id = Column(UUID(as_uuid=True), ForeignKey("rooms.id"), nullable=True)
    status = Column(String(20), default="PENDING_CONSENT")  # ACTIVE | ENROLLED | WAITLIST | UNENROLLED | PENDING_CONSENT
    allergies = Column(Text, nullable=True)
    medical_notes = Column(Text, nullable=True)
    enrollment_date = Column(Date, default=date.today)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    center = relationship("Center", back_populates="children")
    room = relationship("Room", back_populates="children")
    events = relationship("Event", back_populates="child")
    parent_contacts = relationship("ParentContact", back_populates="child", cascade="all, delete-orphan")

    # Functional index for case-insensitive name lookup within a center
    __table_args__ = (
        Index("ix_children_center_name_lower", "center_id", func.lower(name)),
    )


# ─── Parent Contacts ──────────────────────────────────────────


class ParentContact(Base):
    """Parent or emergency contact linked to a child."""

    __tablename__ = "parent_contacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    center_id = Column(UUID(as_uuid=True), ForeignKey("centers.id"), nullable=False)
    child_id = Column(UUID(as_uuid=True), ForeignKey("children.id"), nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(30), nullable=True)
    relationship_type = Column(String(50), nullable=False, default="parent")  # parent | guardian | emergency
    can_pickup = Column(Boolean, default=True)
    is_primary = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    child = relationship("Child", back_populates="parent_contacts")
    center = relationship("Center")


# ─── Events ───────────────────────────────────────────────────


class Event(Base):
    """Core event table — every AI-extracted event is stored here.

    Multi-tenant: center_id is required.
    Review: review_tier determines teacher vs director queue.
    """

    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    center_id = Column(UUID(as_uuid=True), ForeignKey("centers.id"), nullable=False)
    child_id = Column(UUID(as_uuid=True), ForeignKey("children.id"), nullable=True)  # nullable until child resolution
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=True)

    # Event data
    child_name = Column(String(255), nullable=False)  # from transcript, before child_id resolution
    event_type = Column(String(50), nullable=False)  # food, nap, potty, etc.
    event_time = Column(DateTime(timezone=True), nullable=True)
    details = Column(Text, nullable=True)
    raw_transcript = Column(Text, nullable=False)

    # Three-tier review
    review_tier = Column(String(20), nullable=False, default="teacher")  # teacher | director
    confidence_score = Column(Float, nullable=False, default=0.5)
    needs_director_review = Column(Boolean, nullable=False, default=False)
    needs_review = Column(Boolean, nullable=False, default=False)

    # Batch event support — "all kids ate rice and beans"
    # applies_to_all: AI detected a group statement; fan_out_batch_event() was called
    # batch_id: shared UUID linking all sibling events from the same group statement
    applies_to_all = Column(Boolean, nullable=False, default=False)
    batch_id = Column(UUID(as_uuid=True), nullable=True)

    # Status
    status = Column(String(20), nullable=False, default="PENDING")  # PENDING | APPROVED | REJECTED
    reviewed_by = Column(UUID(as_uuid=True), nullable=True)  # admin or teacher who approved
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    center = relationship("Center", back_populates="events")
    child = relationship("Child", back_populates="events")
    teacher = relationship("Teacher", back_populates="events")
    photos = relationship("Photo", back_populates="event")


# ─── Pending Events ──────────────────────────────────────────


class PendingEvent(Base):
    """Holds extracted events for unrecognized children.

    When a teacher replies via WhatsApp mapping the unrecognized name to an enrolled child,
    these events are updated and moved to the main events table.
    """

    __tablename__ = "pending_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    center_id = Column(UUID(as_uuid=True), ForeignKey("centers.id"), nullable=False)
    teacher_phone = Column(String(30), nullable=False)  # WhatsApp number to bind the session
    unrecognized_name = Column(String(255), nullable=False)
    original_transcript = Column(Text, nullable=False)
    pending_event_data = Column(JSON().with_variant(JSONB, 'postgresql'), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    center = relationship("Center")


# ─── Photos ───────────────────────────────────────────────────


class Photo(Base):
    """Photo references — legal-compliant shape.

    Actual image bytes stored in S3 (EXIF-stripped before upload).
    S3 key format: photos/{center_id}/{child_id}/{date}/{uuid}.jpg — no PII.
    Photos older than 90 days are deleted nightly.
    All delivery via pre-signed URLs with 1-hour expiry maximum.
    """

    __tablename__ = "photos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    center_id = Column(UUID(as_uuid=True), ForeignKey("centers.id"), nullable=False)
    child_id = Column(UUID(as_uuid=True), ForeignKey("children.id"), nullable=True)  #required for 90-day deletion
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=True)
    s3_key = Column(String(500), nullable=True)  # format: photos/{center_id}/{child_id}/{date}/{uuid}.jpg
    caption = Column(Text, nullable=True)
    content_type = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    deleted_at = Column(DateTime(timezone=True), nullable=True)  #/set by retention job, not hard-deleted

    event = relationship("Event", back_populates="photos")


# ─── Pending Photos ──────────────────────────────────────────


class PendingPhoto(Base):
    """Temporarily holds photo references before child association.

    Photos are downloaded from Twilio and EXIF-stripped immediately,
    then stored under a pending/ S3 prefix. The teacher has 30 minutes
    to assign the photo to a child via /child [name]. Expired entries
    are cleaned up by a scheduler job every 10 minutes.
    """

    __tablename__ = "pending_photos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    center_id = Column(UUID(as_uuid=True), ForeignKey("centers.id"), nullable=False)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=False)
    s3_temp_key = Column(String(500), nullable=False)
    caption = Column(Text, nullable=True)
    content_type = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=False)

    center = relationship("Center")
    teacher = relationship("Teacher")


# ─── Activity Log ─────────────────────────────────────────────


class ActivityLog(Base):
    """Audit trail — every admin action is recorded here.

    Actions: APPROVE, REJECT, EDIT, BATCH_APPROVE, CREATE
    """

    __tablename__ = "activity_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    center_id = Column(UUID(as_uuid=True), ForeignKey("centers.id"), nullable=False)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=True)
    child_id = Column(UUID(as_uuid=True), ForeignKey("children.id"), nullable=True)
    actor_id = Column(UUID(as_uuid=True), nullable=True)  # teacher or admin who acted
    actor_type = Column(String(20), nullable=False, default="system")  # teacher | director | system
    action = Column(String(30), nullable=False)  # APPROVE | REJECT | EDIT | BATCH_APPROVE | CREATE
    details = Column(Text, nullable=True)  # JSON — what changed
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    center = relationship("Center")
    event = relationship("Event")
    child = relationship("Child")


# ─── Daily Narratives ─────────────────────────────────────────


class DailyNarrative(Base):
    """AI-generated EOD summary for a child on a given date.

    One row per (center_id, child_id, date) — upserted on regeneration.
    photo_captions stored as JSON text: { photo_id: caption }.
    """

    __tablename__ = "daily_narratives"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    center_id = Column(UUID(as_uuid=True), ForeignKey("centers.id"), nullable=False)
    child_id = Column(UUID(as_uuid=True), ForeignKey("children.id"), nullable=False)
    date = Column(Date, nullable=False)
    headline = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    tone = Column(String(20), nullable=False, default="neutral")  # upbeat | neutral | needs-attention
    photo_captions = Column(Text, nullable=True)  # JSON: { photo_id → caption }
    published_at = Column(DateTime(timezone=True), nullable=True)
    admin_override = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    center = relationship("Center")
    child = relationship("Child")

    __table_args__ = (
        UniqueConstraint("center_id", "child_id", "date", name="uq_narrative_center_child_date"),
    )


# ─── AI API Logs ─────────────────────────────────


class AiApiLog(Base):
    """Audit log for every OpenAI API call.

    Legal requirement: log model, tokens, stage per call.
    NEVER log prompt content or response content — by design.
    Fields intentionally limited to metadata only.
    """

    __tablename__ = "ai_api_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    center_id = Column(UUID(as_uuid=True), ForeignKey("centers.id"), nullable=False)
    child_id = Column(UUID(as_uuid=True), ForeignKey("children.id"), nullable=True)  # nullable: some stages pre-resolution
    model = Column(String(50), nullable=False)
    pipeline_stage = Column(String(50), nullable=False)  # extraction | narrative | transcription
    input_token_count = Column(Float, nullable=True)   # from response.usage.prompt_tokens
    output_token_count = Column(Float, nullable=True)  # from response.usage.completion_tokens
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # DO NOT ADD: prompt, response, content, or any PII fields here.
    # This table is intentionally prompt-free for legal compliance.


# ─── Parental Consent ────────────────────────────


class ParentalConsent(Base):
    """Parental consent record — IMMUTABLE, INSERT-ONLY by design.

    No update operations exist on this table (legal requirement).
    Consent changes are modeled as new versioned inserts with is_active toggled.
    Withdrawal sets is_active=False and withdrawn_at on the existing row.

    Legal reference: legal_prd_v1.md §5.2
    """

    __tablename__ = "parental_consent"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    center_id = Column(UUID(as_uuid=True), ForeignKey("centers.id"), nullable=False)
    child_id = Column(UUID(as_uuid=True), ForeignKey("children.id"), nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("parent_contacts.id"), nullable=False)

    consent_version = Column(String(20), nullable=False, default="v1.0")

    # Required consent flags — ALL must be TRUE for child to enter pipeline
    consent_daily_reports = Column(Boolean, nullable=False, default=False)
    consent_photos = Column(Boolean, nullable=False, default=False)
    consent_audio_processing = Column(Boolean, nullable=False, default=False)
    consent_billing_data = Column(Boolean, nullable=False, default=False)

    # AI training consent: always FALSE in V1 — hidden from consent form UI
    # legal_prd_v1.md §7.1: never set to True without explicit product owner approval
    consent_ai_training = Column(Boolean, nullable=False, default=False)

    # How the consent was collected
    consent_method = Column(
        String(20), nullable=False
    )  # paper_scan | docusign | email_confirm

    # Audit metadata
    ip_address = Column(String(50), nullable=True)
    consented_at = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    withdrawn_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    # Unique constraint: only one active consent per child at a time
    __table_args__ = (
        UniqueConstraint("child_id", "is_active", name="unique_active_consent"),
    )


# ─── Pending Consent Queue ───────────────────────


class PendingConsentQueue(Base):
    """Events/voice memos blocked by the consent gate.

    When get_child_for_processing() returns None (no active consent),
    the raw event reference is stored here instead of being silently dropped.
    Director receives an in-app alert to collect consent.

    Legal reference: legal_agent_prompt.md the Legal PRD issue 2
    """

    __tablename__ = "pending_consent_queue"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    center_id = Column(UUID(as_uuid=True), ForeignKey("centers.id"), nullable=False)
    child_id = Column(UUID(as_uuid=True), ForeignKey("children.id"), nullable=False)
    raw_event_ref = Column(Text, nullable=True)  # JSON reference to the blocked event payload
    pipeline_stage = Column(String(50), nullable=True)  # which stage was blocked
    blocked_at = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)  # set when consent collected


# ─── Consent Gate Audit ──────────────────────────


class ConsentGateAudit(Base):
    """Append-only log of every consent gate block event.

    Written each time get_child_for_processing() returns None.
    Never modified after insert.

    Legal reference: legal_agent_prompt.md the Legal PRD issue 2, Rule 4
    """

    __tablename__ = "consent_gate_audit"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    center_id = Column(UUID(as_uuid=True), ForeignKey("centers.id"), nullable=False)
    child_id = Column(UUID(as_uuid=True), nullable=False)  # not FK — child may not exist
    pipeline_stage = Column(String(50), nullable=False)
    timestamp = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


# ─── Consent Tokens ──────────────────────────────


class ConsentToken(Base):
    """Magic link tokens for parental consent onboarding.
    
    Generated when a primary email contact is added to a PENDING_CONSENT child.
    Sent via email (stubbed for now).
    """

    __tablename__ = "consent_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    center_id = Column(UUID(as_uuid=True), ForeignKey("centers.id"), nullable=False)
    child_id = Column(UUID(as_uuid=True), ForeignKey("children.id"), nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("parent_contacts.id"), nullable=False)
    
    token = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    child = relationship("Child")
    parent = relationship("ParentContact")
    center = relationship("Center")
