"""SQLAlchemy ORM models — mirrors Pydantic schemas in /schemas.

Every table has center_id for multi-tenant isolation.
Every query MUST filter by center_id — this is non-negotiable.

Tables: centers, admins, teachers, rooms, children, events, photos
"""

import uuid
from datetime import datetime, date
from sqlalchemy import (
    Column, String, Text, Float, Boolean, DateTime, Date,
    ForeignKey, Enum as SAEnum, Integer,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.storage.database import Base


# ─── Centers ──────────────────────────────────────────────────

class Center(Base):
    __tablename__ = "centers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    timezone = Column(String(50), default="America/New_York")
    created_at = Column(DateTime, default=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow)

    center = relationship("Center", back_populates="admins")


# ─── Teachers ─────────────────────────────────────────────────

class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    center_id = Column(UUID(as_uuid=True), ForeignKey("centers.id"), nullable=False)
    name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False, unique=True)  # WhatsApp number
    room_id = Column(UUID(as_uuid=True), ForeignKey("rooms.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    center = relationship("Center", back_populates="teachers")
    room = relationship("Room", back_populates="teachers")
    events = relationship("Event", back_populates="teacher")


# ─── Rooms ────────────────────────────────────────────────────

class Room(Base):
    __tablename__ = "rooms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    center_id = Column(UUID(as_uuid=True), ForeignKey("centers.id"), nullable=False)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

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
    status = Column(String(20), default="ENROLLED")  # ACTIVE | ENROLLED | WAITLIST | UNENROLLED
    allergies = Column(Text, nullable=True)
    medical_notes = Column(Text, nullable=True)
    enrollment_date = Column(Date, default=date.today)
    created_at = Column(DateTime, default=datetime.utcnow)

    center = relationship("Center", back_populates="children")
    room = relationship("Room", back_populates="children")
    events = relationship("Event", back_populates="child")


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
    event_type = Column(String(50), nullable=False)    # food, nap, potty, etc.
    event_time = Column(DateTime, nullable=True)
    details = Column(Text, nullable=True)
    raw_transcript = Column(Text, nullable=False)

    # Three-tier review
    review_tier = Column(String(20), nullable=False, default="teacher")  # teacher | director
    confidence_score = Column(Float, nullable=False, default=0.5)
    needs_director_review = Column(Boolean, nullable=False, default=False)
    needs_review = Column(Boolean, nullable=False, default=False)

    # Status
    status = Column(String(20), nullable=False, default="PENDING")  # PENDING | APPROVED | REJECTED
    reviewed_by = Column(UUID(as_uuid=True), nullable=True)  # admin or teacher who approved
    reviewed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    center = relationship("Center", back_populates="events")
    child = relationship("Child", back_populates="events")
    teacher = relationship("Teacher", back_populates="events")
    photos = relationship("Photo", back_populates="event")


# ─── Photos ───────────────────────────────────────────────────

class Photo(Base):
    """Photo references — actual images stored in S3, not in DB."""
    __tablename__ = "photos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    center_id = Column(UUID(as_uuid=True), ForeignKey("centers.id"), nullable=False)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=True)
    s3_key = Column(String(500), nullable=True)  # populated when S3 is set up
    caption = Column(Text, nullable=True)
    content_type = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    event = relationship("Event", back_populates="photos")
