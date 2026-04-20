"""REST API for center onboarding — rooms, teachers, children, parent contacts.

All endpoints scoped by center_id for multi-tenant isolation.
"""

import logging
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.storage.database import get_db
from backend.storage.onboarding_handlers import (
    add_parent_contact,
    create_child,
    create_room,
    create_teacher,
    delete_child,
    delete_room,
    get_child,
    list_children,
    list_parent_contacts,
    list_rooms,
    list_teachers,
    update_child,
    update_parent_contact,
    update_room,
    update_teacher,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["onboarding"])


# ─── Schemas ──────────────────────────────────────────────────


class RoomCreate(BaseModel):
    name: str


class RoomOut(BaseModel):
    id: UUID
    center_id: UUID
    name: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TeacherCreate(BaseModel):
    name: str
    phone: str
    room_id: Optional[UUID] = None


class TeacherUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    room_id: Optional[UUID] = None
    is_active: Optional[bool] = None


class TeacherOut(BaseModel):
    id: UUID
    center_id: UUID
    name: str
    phone: str
    room_id: Optional[UUID] = None
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ChildCreate(BaseModel):
    name: str
    dob: Optional[date] = None
    room_id: Optional[UUID] = None
    allergies: Optional[str] = None
    medical_notes: Optional[str] = None
    status: str = "PENDING_CONSENT"


class ChildUpdate(BaseModel):
    name: Optional[str] = None
    dob: Optional[date] = None
    room_id: Optional[UUID] = None
    allergies: Optional[str] = None
    medical_notes: Optional[str] = None
    status: Optional[str] = None


class ContactCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    relationship_type: str = "parent"
    can_pickup: bool = True
    is_primary: bool = False


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    relationship_type: Optional[str] = None
    can_pickup: Optional[bool] = None
    is_primary: Optional[bool] = None


class ContactOut(BaseModel):
    id: UUID
    center_id: UUID
    child_id: UUID
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    relationship_type: str
    can_pickup: bool
    is_primary: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ChildOut(BaseModel):
    id: UUID
    center_id: UUID
    name: str
    dob: Optional[date] = None
    room_id: Optional[UUID] = None
    status: str
    allergies: Optional[str] = None
    medical_notes: Optional[str] = None
    enrollment_date: Optional[date] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ChildDetailOut(ChildOut):
    """Child profile with parent contacts."""

    parent_contacts: List[ContactOut] = []


# ─── Room Endpoints ───────────────────────────────────────────


@router.post("/api/rooms/{center_id}", response_model=RoomOut, status_code=201)
def create_room_endpoint(center_id: UUID, body: RoomCreate, db: Session = Depends(get_db)):
    """Create a new room."""
    room = create_room(db, center_id, body.name)
    logger.info(f"Created room '{body.name}' in center {center_id}")
    return room


@router.get("/api/rooms/{center_id}", response_model=List[RoomOut])
def list_rooms_endpoint(center_id: UUID, db: Session = Depends(get_db)):
    """List all rooms for a center."""
    return list_rooms(db, center_id)


@router.patch("/api/rooms/{center_id}/{room_id}", response_model=RoomOut)
def update_room_endpoint(center_id: UUID, room_id: UUID, body: RoomCreate, db: Session = Depends(get_db)):
    """Rename a room."""
    room = update_room(db, center_id, room_id, body.name)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room


@router.delete("/api/rooms/{center_id}/{room_id}", status_code=204)
def delete_room_endpoint(center_id: UUID, room_id: UUID, db: Session = Depends(get_db)):
    """Delete a room."""
    if not delete_room(db, center_id, room_id):
        raise HTTPException(status_code=404, detail="Room not found")


# ─── Teacher Endpoints ────────────────────────────────────────


@router.post("/api/teachers/{center_id}", response_model=TeacherOut, status_code=201)
def create_teacher_endpoint(center_id: UUID, body: TeacherCreate, db: Session = Depends(get_db)):
    """Register a new teacher."""
    teacher = create_teacher(db, center_id, body.name, body.phone, body.room_id)
    logger.info(f"Registered teacher '{body.name}' in center {center_id}")
    return teacher


@router.get("/api/teachers/{center_id}", response_model=List[TeacherOut])
def list_teachers_endpoint(center_id: UUID, db: Session = Depends(get_db)):
    """List all active teachers for a center."""
    return list_teachers(db, center_id)


@router.patch("/api/teachers/{center_id}/{teacher_id}", response_model=TeacherOut)
def update_teacher_endpoint(center_id: UUID, teacher_id: UUID, body: TeacherUpdate, db: Session = Depends(get_db)):
    """Update a teacher (name, phone, room assignment, active status)."""
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    teacher = update_teacher(db, center_id, teacher_id, updates)
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    return teacher


# ─── Children Endpoints ───────────────────────────────────────


@router.post("/api/children/{center_id}", response_model=ChildOut, status_code=201)
def create_child_endpoint(center_id: UUID, body: ChildCreate, db: Session = Depends(get_db)):
    """Enroll a new child."""
    child = create_child(
        db,
        center_id,
        body.name,
        dob=body.dob,
        room_id=body.room_id,
        allergies=body.allergies,
        medical_notes=body.medical_notes,
        status=body.status,
    )
    logger.info(f"Enrolled child '{body.name}' in center {center_id}")
    return child


@router.get("/api/children/{center_id}", response_model=List[ChildOut])
def list_children_endpoint(
    center_id: UUID,
    room_id: Optional[UUID] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List children, optionally filtered by room or status."""
    return list_children(db, center_id, room_id=room_id, status=status)


@router.get("/api/children/{center_id}/{child_id}", response_model=ChildDetailOut)
def get_child_endpoint(center_id: UUID, child_id: UUID, db: Session = Depends(get_db)):
    """Get a child profile with parent contacts."""
    child = get_child(db, center_id, child_id)
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    contacts = list_parent_contacts(db, center_id, child_id)
    return ChildDetailOut(
        **ChildOut.model_validate(child).model_dump(),
        parent_contacts=[ContactOut.model_validate(c) for c in contacts],
    )


@router.patch("/api/children/{center_id}/{child_id}", response_model=ChildOut)
def update_child_endpoint(center_id: UUID, child_id: UUID, body: ChildUpdate, db: Session = Depends(get_db)):
    """Update a child's profile."""
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    child = update_child(db, center_id, child_id, updates)
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    return child


@router.delete("/api/children/{center_id}/{child_id}", status_code=204)
def delete_child_endpoint(center_id: UUID, child_id: UUID, db: Session = Depends(get_db)):
    """Delete a child."""
    if not delete_child(db, center_id, child_id):
        raise HTTPException(status_code=404, detail="Child not found")


# ─── Parent Contact Endpoints ─────────────────────────────────


@router.post("/api/children/{center_id}/{child_id}/contacts", response_model=ContactOut, status_code=201)
def add_contact_endpoint(center_id: UUID, child_id: UUID, body: ContactCreate, db: Session = Depends(get_db)):
    """Add a parent or emergency contact to a child."""
    contact = add_parent_contact(
        db,
        center_id,
        child_id,
        body.name,
        relationship_type=body.relationship_type,
        email=body.email,
        phone=body.phone,
        can_pickup=body.can_pickup,
        is_primary=body.is_primary,
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Child not found")
    logger.info(f"Added contact '{body.name}' for child {child_id}")
    return contact


@router.get("/api/children/{center_id}/{child_id}/contacts", response_model=List[ContactOut])
def list_contacts_endpoint(center_id: UUID, child_id: UUID, db: Session = Depends(get_db)):
    """List all contacts for a child."""
    return list_parent_contacts(db, center_id, child_id)


@router.patch("/api/contacts/{center_id}/{contact_id}", response_model=ContactOut)
def update_contact_endpoint(center_id: UUID, contact_id: UUID, body: ContactUpdate, db: Session = Depends(get_db)):
    """Update a parent contact."""
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    contact = update_parent_contact(db, center_id, contact_id, updates)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact
