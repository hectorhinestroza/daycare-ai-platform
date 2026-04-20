"""Legal compliance status helpers — L-9 (passive observability only).

DPAs are one-time founder actions documented in README_LEGAL.md.
This module provides a passive status read for the /health endpoint.

There is NO startup blocker here (by design). Reasoning:
- DPA confirmation cannot drift between deploys — it's either done or it isn't.
- A startup blocker would be bypassed instantly with `DPA_OPENAI_CONFIRMED=confirmed`
  without any real enforcement, making it pure theater.
- Every Railway/Fly deploy would break until someone sets dummy env vars.
- The actual enforcement is the PDF in /legal/dpa/ + the README_LEGAL checklist.

What this module does:
- Reads DPA confirmation env vars at runtime
- Returns a boolean status dict for the /health endpoint
- Gives observability with zero friction

Legal reference: legal_prd_v1.md §8. Pre-production checklist: README_LEGAL.md.
"""

import os


def get_legal_status_fields() -> dict:
    """Return passive DPA status booleans for the /health endpoint.

    Returns:
        Dict with True/False for each DPA confirmation.
        False = env var not set (reminder, not a blocker).

    Example response:
        {
            "openai_dpa_confirmed": True,
            "twilio_dpa_confirmed": False,
            "openai_zero_retention_confirmed": True,
        }
    """
    return {
        "openai_dpa_confirmed": os.getenv("DPA_OPENAI_CONFIRMED") == "confirmed",
        "twilio_dpa_confirmed": os.getenv("DPA_TWILIO_CONFIRMED") == "confirmed",
        "openai_zero_retention_confirmed": os.getenv("OPENAI_ZERO_RETENTION_CONFIRMED") == "confirmed",
    }
