"""Authentication endpoints for the pilot.

  GET  /api/auth/whoami           — anyone with a valid token; returns role + ids
  POST /api/admin/tokens/issue    — director only; mints a bootstrap URL for any role
  POST /api/admin/tokens/revoke   — director only; adds a (sub, nonce) to revoked list

The PWA frontend's /app dispatcher hits whoami on every cold start to
decide which portal to route to.
"""

import logging
from typing import List, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.storage.database import get_db
from backend.storage.models import Admin, Child, ParentContact, Teacher
from backend.utils.auth_tokens import (
    DEFAULT_EXPIRY_DAYS,
    TokenPayload,
    generate_token,
    revoke_nonce,
)
from backend.utils.pilot_auth import require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["auth"])


# ─── /api/auth/whoami ─────────────────────────────────────────


class WhoamiResponse(BaseModel):
    role: Literal["parent", "teacher", "director"]
    sub: UUID
    center_id: UUID
    child_ids: List[UUID] = Field(default_factory=list)


@router.get("/auth/whoami", response_model=WhoamiResponse)
async def whoami(payload: TokenPayload = Depends(require_role("staff"))):
    """Return identity for any valid token.

    Note: the dependency uses "staff" as the gate but staff matches both
    teacher AND director. We then short-circuit for parent tokens via
    a second resolver below — see the wrapper route.
    """
    return WhoamiResponse(
        role=payload.role,
        sub=payload.sub,
        center_id=payload.center_id,
        child_ids=list(payload.child_ids),
    )


# Parents need their own whoami — the staff guard above would 403 them.
# We expose a separate path that accepts ANY valid role.


@router.get("/auth/whoami/parent", response_model=WhoamiResponse)
async def whoami_parent(payload: TokenPayload = Depends(require_role("parent"))):
    return WhoamiResponse(
        role=payload.role,
        sub=payload.sub,
        center_id=payload.center_id,
        child_ids=list(payload.child_ids),
    )


# ─── /api/admin/tokens/issue ──────────────────────────────────


class IssueTokenRequest(BaseModel):
    role: Literal["parent", "teacher", "director"]
    sub: UUID  # parent_contact_id | teacher_id | admin_id
    center_id: UUID
    child_ids: Optional[List[UUID]] = None  # required when role=parent
    expires_in_days: int = DEFAULT_EXPIRY_DAYS


class IssueTokenResponse(BaseModel):
    token: str
    bootstrap_url: str
    expires_at: int  # unix seconds
    nonce: str


@router.post(
    "/admin/tokens/issue",
    response_model=IssueTokenResponse,
)
async def issue_token(
    body: IssueTokenRequest,
    _director: TokenPayload = Depends(require_role("director")),
    db: Session = Depends(get_db),
):
    """Mint a bootstrap URL for a single user. Director-only.

    The URL is what gets handed to the user (printed handout, SMS, etc.).
    They open it once on iOS Safari, the PWA dispatcher captures the token,
    Add to Home Screen, and from then on the icon opens the right portal.
    """
    settings = get_settings()

    # Verify the subject actually exists in the right table (defensive — keeps
    # us from minting tokens for non-existent users that would fail silently
    # at use time).
    if body.role == "parent":
        if not body.child_ids:
            raise HTTPException(400, "parent tokens require child_ids")
        parent = (
            db.query(ParentContact)
            .filter(ParentContact.id == body.sub, ParentContact.center_id == body.center_id)
            .first()
        )
        if not parent:
            raise HTTPException(404, "parent contact not found in that center")
        # Verify each child belongs to that parent's center
        children = (
            db.query(Child)
            .filter(Child.id.in_(body.child_ids), Child.center_id == body.center_id)
            .all()
        )
        if len(children) != len(body.child_ids):
            raise HTTPException(404, "one or more child_ids not found in that center")
    elif body.role == "teacher":
        teacher = (
            db.query(Teacher)
            .filter(Teacher.id == body.sub, Teacher.center_id == body.center_id)
            .first()
        )
        if not teacher:
            raise HTTPException(404, "teacher not found in that center")
    else:  # director
        admin = (
            db.query(Admin)
            .filter(Admin.id == body.sub, Admin.center_id == body.center_id)
            .first()
        )
        if not admin:
            raise HTTPException(404, "admin not found in that center")

    token, payload = generate_token(
        role=body.role,
        sub=body.sub,
        center_id=body.center_id,
        child_ids=body.child_ids,
        expires_in_days=body.expires_in_days,
    )

    base = settings.app_base_url.rstrip("/")
    bootstrap_url = f"{base}/app?token={token}"

    logger.info(
        "auth.token_issued role=%s sub=%s center=%s expires_at=%s",
        body.role, body.sub, body.center_id, int(payload.expires_at.timestamp()),
    )

    return IssueTokenResponse(
        token=token,
        bootstrap_url=bootstrap_url,
        expires_at=int(payload.expires_at.timestamp()),
        nonce=payload.nonce,
    )


# ─── /api/admin/tokens/revoke ─────────────────────────────────


class RevokeTokenRequest(BaseModel):
    sub: UUID
    nonce: str


@router.post("/admin/tokens/revoke")
async def revoke_token(
    body: RevokeTokenRequest,
    _director: TokenPayload = Depends(require_role("director")),
    db: Session = Depends(get_db),
):
    """Revoke a specific (sub, nonce). Director-only.

    To rotate a user's bookmark URL: revoke their old nonce here, then
    issue a fresh token via /api/admin/tokens/issue and hand it out.
    """
    revoke_nonce(db, body.sub, body.nonce)
    logger.info("auth.token_revoked sub=%s", body.sub)
    return {"revoked": True}
