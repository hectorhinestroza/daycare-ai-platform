"""Tests for HMAC-signed bearer tokens (pilot Phase 2)."""

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.storage.models  # noqa: F401 — register tables with Base
from backend.storage.database import Base
from backend.utils.auth_tokens import (
    TOKEN_VERSION,
    _b64url_encode,
    _sign,
    generate_token,
    revoke_nonce,
    verify_token,
)

SECRET = "test-secret-do-not-use-in-prod-32-bytes-long-pls"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


# ─── Round-trip per role ──────────────────────────────────────


def test_director_token_roundtrip(db):
    sub = uuid4()
    center = uuid4()
    token, payload = generate_token(
        role="director", sub=sub, center_id=center, secret=SECRET
    )
    verified = verify_token(token, db, secret=SECRET)
    assert verified is not None
    assert verified.role == "director"
    assert verified.sub == sub
    assert verified.center_id == center
    assert verified.child_ids == ()
    assert verified.nonce == payload.nonce


def test_teacher_token_roundtrip(db):
    sub = uuid4()
    token, _ = generate_token(
        role="teacher", sub=sub, center_id=uuid4(), secret=SECRET
    )
    verified = verify_token(token, db, secret=SECRET)
    assert verified is not None
    assert verified.role == "teacher"
    assert verified.sub == sub


def test_parent_token_roundtrip_with_children(db):
    sub = uuid4()
    children = [uuid4(), uuid4()]
    token, _ = generate_token(
        role="parent", sub=sub, center_id=uuid4(),
        child_ids=children, secret=SECRET,
    )
    verified = verify_token(token, db, secret=SECRET)
    assert verified is not None
    assert verified.role == "parent"
    assert list(verified.child_ids) == children


# ─── Issuance validation ──────────────────────────────────────


def test_parent_token_requires_child_ids():
    with pytest.raises(ValueError, match="parent tokens require"):
        generate_token(
            role="parent", sub=uuid4(), center_id=uuid4(),
            child_ids=None, secret=SECRET,
        )


def test_non_parent_rejects_child_ids():
    with pytest.raises(ValueError, match="only parent tokens"):
        generate_token(
            role="teacher", sub=uuid4(), center_id=uuid4(),
            child_ids=[uuid4()], secret=SECRET,
        )


def test_issuance_refuses_empty_secret():
    with pytest.raises(RuntimeError, match="AUTH_TOKEN_SECRET"):
        generate_token(
            role="teacher", sub=uuid4(), center_id=uuid4(),
            secret="",
        )


# ─── Verification — failure modes ─────────────────────────────


def test_garbled_token_returns_none(db):
    assert verify_token("not-a-token", db, secret=SECRET) is None
    assert verify_token("", db, secret=SECRET) is None
    assert verify_token("a.b.c.d", db, secret=SECRET) is None


def test_signature_mismatch_returns_none(db):
    token, _ = generate_token(
        role="teacher", sub=uuid4(), center_id=uuid4(), secret=SECRET
    )
    payload_b64, sig = token.rsplit(".", 1)
    tampered = f"{payload_b64}.{'0' * len(sig)}"
    assert verify_token(tampered, db, secret=SECRET) is None


def test_wrong_secret_returns_none(db):
    token, _ = generate_token(
        role="teacher", sub=uuid4(), center_id=uuid4(), secret=SECRET
    )
    assert verify_token(token, db, secret="some-other-secret") is None


def test_expired_token_returns_none(db):
    token, _ = generate_token(
        role="teacher", sub=uuid4(), center_id=uuid4(),
        expires_in_days=-1, secret=SECRET,
    )
    assert verify_token(token, db, secret=SECRET) is None


def test_old_schema_version_rejected(db):
    """Token with v=0 must be refused."""
    payload = {
        "v": 0,  # wrong version
        "role": "teacher",
        "sub": str(uuid4()),
        "center": str(uuid4()),
        "exp": int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp()),
        "n": "abcd1234",
    }
    payload_b64 = _b64url_encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    sig = _sign(payload_b64, SECRET)
    token = f"{payload_b64}.{sig}"
    assert verify_token(token, db, secret=SECRET) is None


def test_unknown_role_rejected(db):
    payload = {
        "v": TOKEN_VERSION,
        "role": "superadmin",
        "sub": str(uuid4()),
        "center": str(uuid4()),
        "exp": int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp()),
        "n": "abcd1234",
    }
    payload_b64 = _b64url_encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    sig = _sign(payload_b64, SECRET)
    token = f"{payload_b64}.{sig}"
    assert verify_token(token, db, secret=SECRET) is None


def test_parent_without_children_rejected(db):
    """Even if signed, a parent token without child_ids is malformed."""
    payload = {
        "v": TOKEN_VERSION,
        "role": "parent",
        "sub": str(uuid4()),
        "center": str(uuid4()),
        "exp": int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp()),
        "n": "abcd1234",
    }
    payload_b64 = _b64url_encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    sig = _sign(payload_b64, SECRET)
    token = f"{payload_b64}.{sig}"
    assert verify_token(token, db, secret=SECRET) is None


# ─── Revocation ───────────────────────────────────────────────


def test_revoked_token_returns_none(db):
    sub = uuid4()
    token, payload = generate_token(
        role="parent", sub=sub, center_id=uuid4(),
        child_ids=[uuid4()], secret=SECRET,
    )
    # Verify before revoke — should pass
    assert verify_token(token, db, secret=SECRET) is not None

    revoke_nonce(db, sub, payload.nonce)

    # Verify after revoke — must fail
    assert verify_token(token, db, secret=SECRET) is None


def test_revoking_one_nonce_does_not_affect_other(db):
    sub = uuid4()
    center = uuid4()
    token1, p1 = generate_token(
        role="teacher", sub=sub, center_id=center, secret=SECRET
    )
    token2, p2 = generate_token(
        role="teacher", sub=sub, center_id=center, secret=SECRET
    )
    revoke_nonce(db, sub, p1.nonce)
    assert verify_token(token1, db, secret=SECRET) is None
    assert verify_token(token2, db, secret=SECRET) is not None


def test_revoke_is_idempotent(db):
    sub = uuid4()
    token, payload = generate_token(
        role="director", sub=sub, center_id=uuid4(), secret=SECRET
    )
    revoke_nonce(db, sub, payload.nonce)
    revoke_nonce(db, sub, payload.nonce)  # second call must not raise
    assert verify_token(token, db, secret=SECRET) is None
