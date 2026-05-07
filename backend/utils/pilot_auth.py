"""FastAPI dependencies for role-gated endpoints (pilot Phase 2).

Usage:
    @router.get("/foo", dependencies=[Depends(require_role("staff"))])
    async def foo(): ...

Or to read the verified payload inside the handler:

    @router.get("/foo")
    async def foo(payload: TokenPayload = Depends(require_role("parent"))):
        # payload.child_ids etc.
        ...

Roles:
  - "staff"     — teacher OR director
  - "director"  — director only
  - "parent"    — parent only

Dev/test bypass: when ENVIRONMENT is "development" or "test", a missing
or invalid token still gets through with a synthetic payload, logged at
WARNING. Production never bypasses.
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.storage.database import get_db
from backend.utils.auth_tokens import TokenPayload, verify_token

logger = logging.getLogger(__name__)

RoleGuard = str  # "staff" | "director" | "parent"


def _extract_bearer(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    return auth[7:].strip() or None


def _make_dev_payload(role: str) -> TokenPayload:
    """Synthetic payload returned by the dev/test bypass."""
    if role == "staff":
        actual_role = "director"
    elif role == "director":
        actual_role = "director"
    elif role == "parent":
        actual_role = "parent"
    else:
        actual_role = role
    return TokenPayload(
        role=actual_role,  # type: ignore[arg-type]
        sub=uuid4(),
        center_id=uuid4(),
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        nonce="devbypass",
        child_ids=(uuid4(),) if actual_role == "parent" else (),
    )


def require_role(required: RoleGuard):
    """Build a dependency that enforces `required` role on a request.

    Raises 401 on missing/invalid token (production) and 403 if the token
    is valid but the role doesn't match.

    Returns the verified TokenPayload so handlers can use payload.sub,
    payload.center_id, payload.child_ids without re-verifying.
    """
    if required not in ("staff", "director", "parent"):
        raise ValueError(f"unknown role guard: {required!r}")

    async def dependency(
        request: Request,
        db: Session = Depends(get_db),
    ) -> TokenPayload:
        settings = get_settings()
        env = settings.environment.lower()

        token = _extract_bearer(request)

        # Dev/test bypass — keep existing TestClient suites working without
        # per-test token plumbing. Logged loudly so the bypass is visible.
        if env in ("development", "test"):
            if not token:
                logger.warning(
                    "pilot_auth: AUTH BYPASSED (environment=%s, role=%s) — "
                    "production will enforce.",
                    env, required,
                )
                return _make_dev_payload(required)

        if not token:
            raise HTTPException(status_code=401, detail="Missing bearer token")

        payload = verify_token(token, db)
        if payload is None:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        # Role match
        ok = (
            (required == "staff" and payload.role in ("teacher", "director"))
            or (required == "director" and payload.role == "director")
            or (required == "parent" and payload.role == "parent")
        )
        if not ok:
            raise HTTPException(status_code=403, detail="Forbidden")

        # Stash on request.state for routers that want it without a Depends arg.
        request.state.auth = payload
        return payload

    return dependency


def require_parent_owns_child(child_id: UUID, payload: TokenPayload) -> None:
    """Verify a parent token actually covers `child_id`. Raises 403 otherwise.

    Defense against URL manipulation — parent A holding a valid token must not
    be able to read parent B's child by guessing the child's UUID.
    """
    if payload.role != "parent":
        # Director / teacher accessing a parent feed is fine — they're staff.
        return
    if child_id not in payload.child_ids:
        raise HTTPException(
            status_code=403,
            detail="This token does not grant access to that child",
        )
