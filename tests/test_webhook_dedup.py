"""Tests for Twilio MessageSid deduplication (pilot §1.2)."""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.routers.whatsapp import _claim_message_sid
from backend.storage.database import Base


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_first_claim_returns_true(db):
    assert _claim_message_sid(db, "SM1234567890") is True


def test_repeat_claim_returns_false(db):
    sid = "SM1234567890"
    assert _claim_message_sid(db, sid) is True
    assert _claim_message_sid(db, sid) is False
    assert _claim_message_sid(db, sid) is False


def test_distinct_sids_each_claim_independently(db):
    assert _claim_message_sid(db, "SM-A") is True
    assert _claim_message_sid(db, "SM-B") is True
    assert _claim_message_sid(db, "SM-A") is False
    assert _claim_message_sid(db, "SM-B") is False


def test_empty_sid_falls_through(db):
    """Defensive: missing SID should not block processing — just skip dedup."""
    assert _claim_message_sid(db, "") is True
    assert _claim_message_sid(db, None) is True


def test_claim_persists_row(db):
    _claim_message_sid(db, "SM-row-check")
    row = db.execute(
        text("SELECT message_sid FROM processed_messages WHERE message_sid = :sid"),
        {"sid": "SM-row-check"},
    ).fetchone()
    assert row is not None
    assert row[0] == "SM-row-check"
