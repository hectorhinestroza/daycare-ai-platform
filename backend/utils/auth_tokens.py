"""HMAC-signed bearer tokens for the pilot.

One signing secret (`AUTH_TOKEN_SECRET`) issues tokens for all three roles
(parent, teacher, director). Each token is a unique signed payload — the
secret never leaves the server.

Token format:
    <base64url(payload_json)>.<hex(hmac_sha256(secret, base64))>

Payload (v=1):
    {
      "v": 1,
      "role": "parent" | "teacher" | "director",
      "sub": "<uuid>",          # parent_contact_id | teacher_id | admin_id
      "center": "<uuid>",
      "child_ids": ["..."],     # only for role=parent
      "exp": <unix_seconds>,
      "n": "<8-char nonce>"     # for revocation
    }

Verification rejects on:
  - bad signature
  - expired
  - nonce in revoked_token_nonces
  - missing required fields
  - schema version mismatch (v != 1)

This is a pilot-only design. v2 will move to passkeys / WebAuthn.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets as _secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.config import get_settings

logger = logging.getLogger(__name__)

TOKEN_VERSION = 1
DEFAULT_EXPIRY_DAYS = 90
NONCE_LENGTH_BYTES = 6  # → 8 chars urlsafe base64

Role = Literal["parent", "teacher", "director"]


# ─── Public dataclass ─────────────────────────────────────────


@dataclass(frozen=True)
class TokenPayload:
    role: Role
    sub: UUID
    center_id: UUID
    expires_at: datetime
    nonce: str
    child_ids: tuple[UUID, ...] = ()

    def to_dict(self) -> dict:
        d = {
            "v": TOKEN_VERSION,
            "role": self.role,
            "sub": str(self.sub),
            "center": str(self.center_id),
            "exp": int(self.expires_at.timestamp()),
            "n": self.nonce,
        }
        if self.child_ids:
            d["child_ids"] = [str(cid) for cid in self.child_ids]
        return d


# ─── Encoding helpers ─────────────────────────────────────────


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign(payload_b64: str, secret: str) -> str:
    return hmac.new(
        secret.encode(),
        payload_b64.encode(),
        hashlib.sha256,
    ).hexdigest()


# ─── Token issuance ───────────────────────────────────────────


def generate_token(
    *,
    role: Role,
    sub: UUID,
    center_id: UUID,
    child_ids: Optional[List[UUID]] = None,
    expires_in_days: int = DEFAULT_EXPIRY_DAYS,
    secret: Optional[str] = None,
) -> tuple[str, TokenPayload]:
    """Issue a fresh signed token. Returns (token_str, payload)."""
    secret = get_settings().auth_token_secret if secret is None else secret
    if not secret:
        raise RuntimeError(
            "AUTH_TOKEN_SECRET is not set — cannot issue tokens"
        )

    if role == "parent" and not child_ids:
        raise ValueError("parent tokens require at least one child_id")
    if role != "parent" and child_ids:
        raise ValueError("only parent tokens may carry child_ids")

    nonce = _b64url_encode(_secrets.token_bytes(NONCE_LENGTH_BYTES))[:8]
    expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

    payload = TokenPayload(
        role=role,
        sub=sub,
        center_id=center_id,
        expires_at=expires_at,
        nonce=nonce,
        child_ids=tuple(child_ids or ()),
    )

    payload_json = json.dumps(payload.to_dict(), sort_keys=True, separators=(",", ":"))
    payload_b64 = _b64url_encode(payload_json.encode())
    sig = _sign(payload_b64, secret)
    return f"{payload_b64}.{sig}", payload


# ─── Token verification ───────────────────────────────────────


def verify_token(
    token: str,
    db: Session,
    *,
    secret: Optional[str] = None,
) -> Optional[TokenPayload]:
    """Verify a bearer token. Returns the payload or None on any failure.

    Reasons for None: bad shape, bad signature, expired, revoked nonce,
    schema version mismatch, missing fields.

    Caller logs the failure; we don't log here to avoid leaking partial
    token state on each request.
    """
    secret = get_settings().auth_token_secret if secret is None else secret
    if not secret:
        return None

    if not token or "." not in token:
        return None

    try:
        payload_b64, sig = token.rsplit(".", 1)
    except ValueError:
        return None

    expected_sig = _sign(payload_b64, secret)
    if not hmac.compare_digest(sig, expected_sig):
        return None

    try:
        raw = _b64url_decode(payload_b64).decode()
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None

    # Schema check
    if data.get("v") != TOKEN_VERSION:
        return None

    role = data.get("role")
    sub_str = data.get("sub")
    center_str = data.get("center")
    exp = data.get("exp")
    nonce = data.get("n")
    if not all([role, sub_str, center_str, exp, nonce]):
        return None
    if role not in ("parent", "teacher", "director"):
        return None

    # Expiry
    if datetime.now(timezone.utc).timestamp() >= exp:
        return None

    # Parent-specific shape
    child_ids_raw = data.get("child_ids", [])
    if role == "parent" and not child_ids_raw:
        return None
    if role != "parent" and child_ids_raw:
        return None

    try:
        sub = UUID(sub_str)
        center_id = UUID(center_str)
        child_ids = tuple(UUID(cid) for cid in child_ids_raw)
    except (ValueError, TypeError):
        return None

    # Revocation check (per-subject + nonce)
    if _is_revoked(db, sub, nonce):
        return None

    return TokenPayload(
        role=role,  # type: ignore[arg-type]
        sub=sub,
        center_id=center_id,
        expires_at=datetime.fromtimestamp(exp, tz=timezone.utc),
        nonce=nonce,
        child_ids=child_ids,
    )


# ─── Revocation ───────────────────────────────────────────────


def _is_revoked(db: Session, sub: UUID, nonce: str) -> bool:
    row = db.execute(
        text(
            "SELECT 1 FROM revoked_token_nonces "
            "WHERE sub_id = :sub AND nonce = :nonce LIMIT 1"
        ),
        {"sub": str(sub), "nonce": nonce},
    ).fetchone()
    return row is not None


def revoke_nonce(db: Session, sub: UUID, nonce: str) -> None:
    """Add a (sub, nonce) pair to the revocation list. Idempotent."""
    # CURRENT_TIMESTAMP is portable across Postgres and SQLite (used in tests).
    db.execute(
        text(
            "INSERT INTO revoked_token_nonces (sub_id, nonce, revoked_at) "
            "VALUES (:sub, :nonce, CURRENT_TIMESTAMP) "
            "ON CONFLICT (sub_id, nonce) DO NOTHING"
        ),
        {"sub": str(sub), "nonce": nonce},
    )
    db.commit()
