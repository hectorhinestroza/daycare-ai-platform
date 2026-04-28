"""Tests forOpenAI call wrapper + ai_api_logs.

Verifies:
- Log record is written with correct fields after every call
- Log record never contains prompt or response content
- Token counts are captured from the response usage object
- child_id / center_id / pipeline_stage are recorded correctly
"""
import uuid
from unittest.mock import MagicMock

import pytest

from backend.storage.models import AiApiLog
from backend.utils.openai_wrapper import call_openai_with_logging

# ─── Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def center_id():
    return uuid.uuid4()


@pytest.fixture
def child_id():
    return uuid.uuid4()


def _make_mock_response(input_tokens: int = 100, output_tokens: int = 50):
    """Build a minimal mock OpenAI response object."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = '{"headline": "Test", "body": "test body", "tone": "neutral"}'
    response.model = "gpt-4o"
    response.usage = MagicMock()
    response.usage.prompt_tokens = input_tokens
    response.usage.completion_tokens = output_tokens
    return response


# ─── Tests: call_openai_with_logging ──────────────────────────


class TestCallOpenaiWithLogging:
    """Unit tests for the call_openai_with_logging wrapper."""

    def test_returns_response_unchanged(self, center_id, child_id):
        """Wrapper must return the raw OpenAI response transparently."""

        mock_client = MagicMock()
        mock_response = _make_mock_response()
        mock_client.chat.completions.create.return_value = mock_response

        mock_db = MagicMock()

        result = call_openai_with_logging(
            client=mock_client,
            db=mock_db,
            center_id=center_id,
            child_id=child_id,
            pipeline_stage="extraction",
            model="gpt-4o",
            temperature=0,
            messages=[{"role": "user", "content": "Tell me about Carlos today."}],
        )

        assert result is mock_response

    def test_log_record_written_to_db(self, center_id, child_id):
        """A log record must be inserted into the db session after every call."""

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response(80, 40)

        mock_db = MagicMock()

        call_openai_with_logging(
            client=mock_client,
            db=mock_db,
            center_id=center_id,
            child_id=child_id,
            pipeline_stage="extraction",
            model="gpt-4o",
            temperature=0,
            messages=[{"role": "user", "content": "test prompt"}],
        )

        # db.add() and db.commit() must be called once
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_log_record_has_correct_fields(self, center_id, child_id):
        """Log record must have model, center_id, child_id, stage, token counts."""

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response(75, 30)

        captured_log = {}

        def capture_add(obj):
            if isinstance(obj, AiApiLog):
                captured_log["log"] = obj

        mock_db = MagicMock()
        mock_db.add.side_effect = capture_add

        call_openai_with_logging(
            client=mock_client,
            db=mock_db,
            center_id=center_id,
            child_id=child_id,
            pipeline_stage="narrative",
            model="gpt-4o",
            temperature=0,
            messages=[{"role": "user", "content": "child events here"}],
        )

        log = captured_log.get("log")
        assert log is not None, "AiApiLog record was not created"
        assert log.center_id == center_id
        assert log.child_id == child_id
        assert log.pipeline_stage == "narrative"
        assert log.model == "gpt-4o"
        assert log.input_token_count == 75
        assert log.output_token_count == 30

    def test_log_record_contains_no_prompt_content(self, center_id, child_id):
        """CRITICAL: Log record must NOT contain prompt text or response content."""

        secret_prompt = "Child: Maria Santos, DOB: 2021-03-12"
        secret_response = '{"headline": "Maria had a great day!", "body": "Sensitive info here"}'

        mock_response = _make_mock_response()
        mock_response.choices[0].message.content = secret_response

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        captured_log = {}

        def capture_add(obj):
            if isinstance(obj, AiApiLog):
                captured_log["log"] = obj

        mock_db = MagicMock()
        mock_db.add.side_effect = capture_add

        call_openai_with_logging(
            client=mock_client,
            db=mock_db,
            center_id=center_id,
            child_id=child_id,
            pipeline_stage="extraction",
            model="gpt-4o",
            temperature=0,
            messages=[{"role": "user", "content": secret_prompt}],
        )

        log = captured_log.get("log")
        assert log is not None

        # Serialize the log to check no PII leaked into any field
        log_dict = {
            "model": log.model,
            "pipeline_stage": log.pipeline_stage,
            "input_token_count": log.input_token_count,
            "output_token_count": log.output_token_count,
        }
        log_str = str(log_dict)

        assert "Maria Santos" not in log_str, "Child surname found in log"
        assert "2021-03-12" not in log_str, "DOB found in log"
        assert "Sensitive info" not in log_str, "Response content found in log"
        assert "great day" not in log_str, "Response narrative found in log"

    def test_token_counts_from_usage_object(self, center_id, child_id):
        """Token counts must come from response.usage, not hardcoded."""

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response(
            input_tokens=312, output_tokens=88
        )

        captured_log = {}

        def capture_add(obj):
            if isinstance(obj, AiApiLog):
                captured_log["log"] = obj

        mock_db = MagicMock()
        mock_db.add.side_effect = capture_add

        call_openai_with_logging(
            client=mock_client,
            db=mock_db,
            center_id=center_id,
            child_id=child_id,
            pipeline_stage="extraction",
            model="gpt-4o",
            temperature=0,
            messages=[],
        )

        log = captured_log["log"]
        assert log.input_token_count == 312
        assert log.output_token_count == 88

    def test_child_id_can_be_none(self, center_id):
        """child_id is optional — some pipeline stages don't have it yet."""

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()
        mock_db = MagicMock()

        # Should not raise
        call_openai_with_logging(
            client=mock_client,
            db=mock_db,
            center_id=center_id,
            child_id=None,
            pipeline_stage="extraction",
            model="gpt-4o",
            temperature=0,
            messages=[],
        )

        mock_db.add.assert_called_once()


# ─── Tests: AiApiLog model field presence ─────────────────────


class TestAiApiLogModel:
    """Verify AiApiLog ORM model has the required fields."""

    def test_model_has_required_fields(self):
        """AiApiLog must expose all legally required fields."""

        required_fields = {
            "id",
            "model",
            "center_id",
            "child_id",
            "timestamp",
            "input_token_count",
            "output_token_count",
            "pipeline_stage",
        }

        model_columns = {col.name for col in AiApiLog.__table__.columns}
        missing = required_fields - model_columns
        assert not missing, f"AiApiLog missing columns: {missing}"

    def test_model_has_no_prompt_column(self):
        """AiApiLog must NOT have a prompt or response column (by design)."""

        prohibited = {"prompt", "response", "prompt_text", "response_text", "content"}
        model_columns = {col.name for col in AiApiLog.__table__.columns}
        leaking = prohibited & model_columns
        assert not leaking, f"AiApiLog must not store prompt/response content: {leaking}"
