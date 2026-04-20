"""OpenAI call wrapper — Legal Compliance L-5.

Every OpenAI API call in the pipeline MUST go through call_openai_with_logging().

What it does:
  1. Calls the OpenAI API exactly as the caller specifies
  2. Writes a metadata-only log record to ai_api_logs (no prompt, no response)
  3. Returns the raw OpenAI response object unchanged

What it NEVER does:
  - Logs prompt text or response content
  - Modifies the prompt or sanitizes it
  - Suppresses exceptions (failures propagate to caller)

Legal reference: legal_prd_v1.md §7.2 + legal_agent_prompt.md Rule 6
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def call_openai_with_logging(
    *,
    client,
    db: Session,
    center_id: UUID,
    child_id: Optional[UUID],
    pipeline_stage: str,
    **openai_kwargs,
):
    """Call OpenAI chat completions and log metadata to ai_api_logs.

    Args:
        client:         OpenAI or AsyncOpenAI client instance
        db:             SQLAlchemy session (sync) — used to write the audit log
        center_id:      UUID of the center — required for multi-tenant isolation
        child_id:       UUID of the child being processed, or None if not yet resolved
        pipeline_stage: Human-readable stage label ("extraction" | "narrative" | ...)
        **openai_kwargs: Passed directly to client.chat.completions.create()

    Returns:
        The raw OpenAI ChatCompletion response object.

    Raises:
        Any exception from the OpenAI client propagates unchanged.
    """
    from backend.storage.models import AiApiLog

    model = openai_kwargs.get("model", "unknown")

    response = client.chat.completions.create(**openai_kwargs)

    # Extract token usage safely — OpenAI may sometimes return None for usage
    input_tokens: Optional[float] = None
    output_tokens: Optional[float] = None
    try:
        if response.usage:
            input_tokens = float(response.usage.prompt_tokens)
            output_tokens = float(response.usage.completion_tokens)
    except (AttributeError, TypeError):
        logger.warning("Could not extract token counts from OpenAI response")

    # Write audit log — metadata only, no prompt or response content
    log_record = AiApiLog(
        center_id=center_id,
        child_id=child_id,
        model=model,
        pipeline_stage=pipeline_stage,
        input_token_count=input_tokens,
        output_token_count=output_tokens,
        timestamp=datetime.now(timezone.utc),
    )

    try:
        db.add(log_record)
        db.commit()
    except Exception as log_err:
        # Log write failure must never mask the successful AI response
        logger.error(f"Failed to write ai_api_logs record: {log_err}")
        try:
            db.rollback()
        except Exception:
            pass

    return response


async def call_openai_async_with_logging(
    *,
    client,
    db: Session,
    center_id: UUID,
    child_id: Optional[UUID],
    pipeline_stage: str,
    **openai_kwargs,
):
    """Async variant for use with AsyncOpenAI client (narrative service).

    See call_openai_with_logging() for full documentation.
    """
    from backend.storage.models import AiApiLog

    model = openai_kwargs.get("model", "unknown")

    response = await client.chat.completions.create(**openai_kwargs)

    input_tokens: Optional[float] = None
    output_tokens: Optional[float] = None
    try:
        if response.usage:
            input_tokens = float(response.usage.prompt_tokens)
            output_tokens = float(response.usage.completion_tokens)
    except (AttributeError, TypeError):
        logger.warning("Could not extract token counts from OpenAI response (async)")

    log_record = AiApiLog(
        center_id=center_id,
        child_id=child_id,
        model=model,
        pipeline_stage=pipeline_stage,
        input_token_count=input_tokens,
        output_token_count=output_tokens,
        timestamp=datetime.now(timezone.utc),
    )

    try:
        db.add(log_record)
        db.commit()
    except Exception as log_err:
        logger.error(f"Failed to write ai_api_logs record (async): {log_err}")
        try:
            db.rollback()
        except Exception:
            pass

    return response
