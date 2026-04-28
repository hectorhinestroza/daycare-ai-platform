"""CRUD operations for center onboarding — rooms, teachers, children, and parent contacts.

All queries filter by center_id for multi-tenant isolation.
"""
import asyncio
import logging
import threading
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.services.email import send_consent_email
from backend.storage.models import (
    Center,
    Child,
    ConsentToken,
    DailyNarrative,
    ParentalConsent,
    ParentContact,
    PendingConsentQueue,
    Room,
    Teacher,
)

logger = logging.getLogger(__name__)

# ─── Rooms ────────────────────────────────────────────────────


def create_room(db: Session, center_id: uuid.UUID, name: str) -> Room:
    """Create a new room/classroom."""
    room = Room(id=uuid.uuid4(), center_id=center_id, name=name)
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


def list_rooms(db: Session, center_id: uuid.UUID) -> List[Room]:
    """List all rooms for a center."""
    return db.query(Room).filter(Room.center_id == center_id).order_by(Room.name).all()


def update_room(db: Session, center_id: uuid.UUID, room_id: uuid.UUID, name: str) -> Optional[Room]:
    """Rename a room."""
    room = db.query(Room).filter(Room.id == room_id, Room.center_id == center_id).first()
    if not room:
        return None
    room.name = name
    db.commit()
    db.refresh(room)
    return room


def delete_room(db: Session, center_id: uuid.UUID, room_id: uuid.UUID) -> bool:
    """Delete a room. Returns True if deleted."""
    room = db.query(Room).filter(Room.id == room_id, Room.center_id == center_id).first()
    if not room:
        return False
    db.delete(room)
    db.commit()
    return True


# ─── Teachers ─────────────────────────────────────────────────


def create_teacher(
    db: Session,
    center_id: uuid.UUID,
    name: str,
    phone: str,
    room_id: Optional[uuid.UUID] = None,
) -> Teacher:
    """Register a new teacher."""
    teacher = Teacher(
        id=uuid.uuid4(),
        center_id=center_id,
        name=name,
        phone=phone,
        room_id=room_id,
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    return teacher


def list_teachers(db: Session, center_id: uuid.UUID) -> List[Teacher]:
    """List all active teachers for a center."""
    return db.query(Teacher).filter(Teacher.center_id == center_id, Teacher.is_active).order_by(Teacher.name).all()


def update_teacher(
    db: Session,
    center_id: uuid.UUID,
    teacher_id: uuid.UUID,
    updates: dict,
) -> Optional[Teacher]:
    """Update teacher fields (name, phone, room_id, is_active)."""
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id, Teacher.center_id == center_id).first()
    if not teacher:
        return None
    allowed = {"name", "phone", "room_id", "is_active"}
    for key, value in updates.items():
        if key in allowed:
            setattr(teacher, key, value)
    db.commit()
    db.refresh(teacher)
    return teacher


# ─── Children ─────────────────────────────────────────────────


def create_child(
    db: Session,
    center_id: uuid.UUID,
    name: str,
    dob: Optional[date] = None,
    room_id: Optional[uuid.UUID] = None,
    allergies: Optional[str] = None,
    medical_notes: Optional[str] = None,
    status: str = "PENDING_CONSENT",
) -> Child:
    """Enroll a new child."""
    child = Child(
        id=uuid.uuid4(),
        center_id=center_id,
        name=name,
        dob=dob,
        room_id=room_id,
        allergies=allergies,
        medical_notes=medical_notes,
        status=status,
    )
    db.add(child)
    db.commit()
    db.refresh(child)
    return child


def list_children(
    db: Session,
    center_id: uuid.UUID,
    room_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
) -> List[Child]:
    """List children, optionally filtered by room or status."""
    q = db.query(Child).filter(Child.center_id == center_id)
    if room_id:
        q = q.filter(Child.room_id == room_id)
    if status:
        q = q.filter(Child.status == status)
    return q.order_by(Child.name).all()


def get_child(db: Session, center_id: uuid.UUID, child_id: uuid.UUID) -> Optional[Child]:
    """Get a single child profile."""
    return db.query(Child).filter(Child.id == child_id, Child.center_id == center_id).first()


def update_child(
    db: Session,
    center_id: uuid.UUID,
    child_id: uuid.UUID,
    updates: dict,
) -> Optional[Child]:
    """Update child fields."""
    child = get_child(db, center_id, child_id)
    if not child:
        return None
    allowed = {"name", "dob", "room_id", "allergies", "medical_notes", "status"}
    for key, value in updates.items():
        if key in allowed:
            setattr(child, key, value)
    db.commit()
    db.refresh(child)
    return child


def delete_child(db: Session, center_id: uuid.UUID, child_id: uuid.UUID) -> bool:
    """Delete a child profile and cascade delete their contacts/events (depending on DB constraints)."""

    child = get_child(db, center_id, child_id)
    if not child:
        return False

    # Manually delete dependent records that lack DB/ORM-level cascade deletes
    db.query(ConsentToken).filter(ConsentToken.child_id == child_id).delete()
    db.query(ParentalConsent).filter(ParentalConsent.child_id == child_id).delete()
    db.query(PendingConsentQueue).filter(PendingConsentQueue.child_id == child_id).delete()
    db.query(DailyNarrative).filter(DailyNarrative.child_id == child_id).delete()

    db.delete(child)
    db.commit()
    return True


# ─── Parent Contacts ──────────────────────────────────────────


def add_parent_contact(
    db: Session,
    center_id: uuid.UUID,
    child_id: uuid.UUID,
    name: str,
    relationship_type: str = "parent",
    email: Optional[str] = None,
    phone: Optional[str] = None,
    can_pickup: bool = True,
    is_primary: bool = False,
) -> Optional[ParentContact]:
    """Add a parent or emergency contact to a child."""
    child = get_child(db, center_id, child_id)
    if not child:
        return None
    contact = ParentContact(
        id=uuid.uuid4(),
        center_id=center_id,
        child_id=child_id,
        name=name,
        email=email,
        phone=phone,
        relationship_type=relationship_type,
        can_pickup=can_pickup,
        is_primary=is_primary,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)

    # Auto-trigger magic link when primary email is added to a PENDING_CONSENT child
    if child.status == "PENDING_CONSENT" and is_primary and email:

        token_record = ConsentToken(
            id=uuid.uuid4(),
            center_id=center_id,
            child_id=child_id,
            parent_id=contact.id,
            token=uuid.uuid4(),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db.add(token_record)
        db.commit()

        # Look up center name for email personalization
        center = db.query(Center).filter(Center.id == center_id).first()
        center_name = center.name if center else "Your Daycare"
        child_first = child.name.split()[0] if child.name else "your child"

        # Fire email in a background thread (this handler is sync, no event loop)

        def _send():
            asyncio.run(send_consent_email(
                to_email=email,
                parent_name=name,
                child_name=child_first,
                center_name=center_name,
                token=str(token_record.token),
            ))

        threading.Thread(target=_send, daemon=True).start()

    return contact


def list_parent_contacts(db: Session, center_id: uuid.UUID, child_id: uuid.UUID) -> List[ParentContact]:
    """List all contacts for a child."""
    return (
        db.query(ParentContact)
        .filter(
            ParentContact.center_id == center_id,
            ParentContact.child_id == child_id,
        )
        .order_by(ParentContact.is_primary.desc(), ParentContact.name)
        .all()
    )


def update_parent_contact(
    db: Session,
    center_id: uuid.UUID,
    contact_id: uuid.UUID,
    updates: dict,
) -> Optional[ParentContact]:
    """Update a parent contact."""
    contact = (
        db.query(ParentContact).filter(ParentContact.id == contact_id, ParentContact.center_id == center_id).first()
    )
    if not contact:
        return None
    allowed = {"name", "email", "phone", "relationship_type", "can_pickup", "is_primary"}
    for key, value in updates.items():
        if key in allowed:
            setattr(contact, key, value)
    db.commit()
    db.refresh(contact)
    return contact
