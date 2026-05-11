"""Temporary debug endpoints used to verify Sentry + PII scrubber.

All endpoints here are director-only. Remove this router after pilot-day
acceptance is complete — these exist to force on-demand failure cases
that prove the observability pipeline works end-to-end.

Mounted in main.py alongside the other routers.
"""

import logging

from fastapi import APIRouter, Depends

from backend.utils.pilot_auth import require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/debug", tags=["debug"])


@router.get(
    "/sentry-test",
    dependencies=[Depends(require_role("director"))],
)
def sentry_test():
    """Raises a plain RuntimeError. Sentry's FastAPI integration captures
    unhandled exceptions automatically — calling this should produce a
    fresh issue in the FastAPI Sentry project within ~30 seconds.

    Verifies: SDK is initialized, DSN is correct, network reaches Sentry.
    """
    raise RuntimeError("sentry-test: this is an intentional test exception")


@router.get(
    "/sentry-pii-test",
    dependencies=[Depends(require_role("director"))],
)
def sentry_pii_test():
    """Raises with PII-shaped local variables in scope.

    Sentry's `with_locals` setting captures frame variables when an
    exception bubbles up. Our `pii_scrubber` (before_send hook in
    main.py) must redact `transcript` and `child_name` from those frame
    vars before the event ships to Sentry.

    Verifies: pii_scrubber actually runs and actually redacts.
    """
    # These local names match PII_FIELD_NAMES in safe_logging.py. The
    # scrubber walks event.exception.values[*].stacktrace.frames[*].vars
    # and replaces matching keys with "[redacted]".
    transcript = "Annie ate her lunch and took a nap at 1pm"
    child_name = "Annie"
    parent_email = "annies-mom@example.com"
    phone = "+15551234567"

    # Reference locals so they survive Python optimizer/inlining and
    # actually appear in the captured stack frame.
    _all_locals = (transcript, child_name, parent_email, phone)
    raise RuntimeError(
        "sentry-pii-test: locals must show [redacted], NOT 'Annie' etc."
    )
