"""PII-refusing structured log helper.

Use `safe_log()` for every new log call in the pipeline. It refuses to
emit fields whose name is in `PII_FIELD_NAMES`:

  - In development/test: raises ValueError so the bad call surfaces in CI.
  - In production: drops the offending field, adds `_dropped_pii_fields`
    so we can grep for accidents post-hoc.

The companion `pii_scrubber()` is the Sentry `before_send` hook — it walks
event["extra"], stack-frame vars, and request data, replacing any matching
key's value with "[redacted]".

Why both:
  - safe_log catches PII at the log call site (proactive).
  - pii_scrubber catches PII inside exception payloads Sentry collects
    automatically (defensive — exception locals can pull in transcripts).

request_id contextvar:
  RequestIDMiddleware sets the current request's ID into a ContextVar
  on every request. safe_log() auto-reads it and includes request_id in
  the log record without callsite changes. Background tasks (scheduler)
  don't have one — the field is omitted in that case.
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
from typing import Any, Dict, Iterable, MutableMapping, Optional

PII_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "child_name",
        "name",
        "transcript",
        "raw_transcript",
        "body",
        "caption",
        "parent_name",
        "parent_email",
        "phone",
    }
)

REDACTED = "[redacted]"

# Per-request ID, set by RequestIDMiddleware on each incoming request.
# safe_log() reads this and includes it as `request_id` in every record.
_request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "dc_request_id", default=None
)


def set_request_id(request_id: Optional[str]) -> contextvars.Token:
    """Bind a request ID to the current async context. Returns a token
    that can be passed to `reset_request_id()` to restore the previous
    value (used by middleware to clean up after the response is sent).
    """
    return _request_id_var.set(request_id)


def reset_request_id(token: contextvars.Token) -> None:
    _request_id_var.reset(token)


def get_request_id() -> Optional[str]:
    """Return the request ID for the current async context, or None."""
    return _request_id_var.get()


_LEVEL_MAP = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


def _is_dev() -> bool:
    return os.getenv("ENVIRONMENT", "development").lower() in ("development", "test")


def safe_log(
    logger: logging.Logger,
    level: str,
    event: str,
    **fields: Any,
) -> None:
    """Emit a structured log line that refuses PII fields.

    Args:
        logger: standard logging.Logger
        level:  one of "debug" | "info" | "warning" | "error" | "critical"
        event:  short event name (e.g. "webhook.received")
        **fields: arbitrary keyword fields. Any key in PII_FIELD_NAMES will
                  be rejected (dev) or dropped (prod).
    """
    pii_violations = PII_FIELD_NAMES & fields.keys()
    if pii_violations:
        if _is_dev():
            raise ValueError(
                f"safe_log refused to emit PII fields: {sorted(pii_violations)} "
                f"(event={event!r})"
            )
        for k in pii_violations:
            fields.pop(k)
        fields["_dropped_pii_fields"] = sorted(pii_violations)

    record = {"event": event}
    rid = get_request_id()
    if rid is not None and "request_id" not in fields:
        record["request_id"] = rid
    record.update(fields)

    log_fn = getattr(logger, level.lower(), logger.info)
    try:
        log_fn(json.dumps(record, default=str))
    except (TypeError, ValueError):
        # Last-resort fallback — never let logging crash the request
        log_fn(f"event={event} (unserializable fields)")


# ─── Sentry before_send scrubber ──────────────────────────────────────


def _scrub_mapping(data: MutableMapping[str, Any], keys: Iterable[str]) -> None:
    for key in list(data.keys()):
        if key in keys:
            data[key] = REDACTED


def _scrub_frame_vars(frames: list[Dict[str, Any]]) -> None:
    for frame in frames:
        local_vars = frame.get("vars")
        if isinstance(local_vars, dict):
            _scrub_mapping(local_vars, PII_FIELD_NAMES)


def pii_scrubber(event: Dict[str, Any], _hint: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Sentry `before_send` hook. Strips known PII from event payloads.

    Returns the mutated event. Sentry passes back whatever we return.
    """
    extra = event.get("extra")
    if isinstance(extra, dict):
        _scrub_mapping(extra, PII_FIELD_NAMES)

    request = event.get("request")
    if isinstance(request, dict):
        for key in ("data", "query_string", "headers", "cookies"):
            inner = request.get(key)
            if isinstance(inner, dict):
                _scrub_mapping(inner, PII_FIELD_NAMES)

    # Walk every exception in the chain, scrubbing local vars in stack frames.
    exception = event.get("exception")
    if isinstance(exception, dict):
        for value in exception.get("values", []) or []:
            stacktrace = value.get("stacktrace") if isinstance(value, dict) else None
            if isinstance(stacktrace, dict):
                frames = stacktrace.get("frames")
                if isinstance(frames, list):
                    _scrub_frame_vars(frames)

    # Top-level `threads` (rare but possible) — scrub too.
    threads = event.get("threads")
    if isinstance(threads, dict):
        for value in threads.get("values", []) or []:
            stacktrace = value.get("stacktrace") if isinstance(value, dict) else None
            if isinstance(stacktrace, dict):
                frames = stacktrace.get("frames")
                if isinstance(frames, list):
                    _scrub_frame_vars(frames)

    return event
