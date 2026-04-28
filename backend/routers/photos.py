"""Parent-facing photo feed.

Returns photos for a child with short-lived presigned URLs. Photos are stored
in S3 (EXIF-stripped, consent-gated at upload time); rows live in the photos
table. The parent portal calls this endpoint to render the gallery.
"""
import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.storage.database import get_db
from backend.storage.events_handlers import get_photos_for_child
from backend.utils.s3 import generate_presigned_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/photos", tags=["photos"])


class PhotoOut(BaseModel):
    """Photo response shape for the parent feed."""

    id: UUID
    caption: Optional[str] = None
    s3_url: Optional[str] = None
    created_at: Optional[datetime] = None


@router.get("/feed/{center_id}/{child_id}", response_model=List[PhotoOut])
def parent_photo_feed(
    center_id: UUID,
    child_id: UUID,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Return recent photos for a child with 1-hour presigned URLs."""
    photos = get_photos_for_child(db, center_id, child_id, limit=limit)
    return [
        PhotoOut(
            id=p.id,
            caption=p.caption,
            s3_url=generate_presigned_url(p.s3_key) if p.s3_key else None,
            created_at=p.created_at,
        )
        for p in photos
    ]
