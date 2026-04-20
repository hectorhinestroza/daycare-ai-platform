"""DPA Verification Startup Guard — Legal Compliance L-9.

Runs on application startup. Enforces that all required Data Processing Agreements
are confirmed before the application starts in production mode.

Required env vars (all must equal "confirmed" in production):
    DPA_OPENAI_CONFIRMED        — OpenAI Data Processing Addendum executed
    DPA_TWILIO_CONFIRMED        — Twilio Data Protection Addendum executed
    OPENAI_ZERO_RETENTION_CONFIRMED — OpenAI "no training" API mode verified active

In development / sandbox mode: logs warnings only, does not block startup.

Legal reference: legal_prd_v1.md §8 + legal_agent_prompt.md Issue L-9
"""

import logging

logger = logging.getLogger(__name__)

# Required vars and instructions for error messages
_REQUIRED_CHECKS = [
    (
        "dpa_openai_confirmed",
        "DPA_OPENAI_CONFIRMED",
        "Execute OpenAI DPA at platform.openai.com/account/data-processing-agreement "
        "then set DPA_OPENAI_CONFIRMED=confirmed in your environment.",
    ),
    (
        "dpa_twilio_confirmed",
        "DPA_TWILIO_CONFIRMED",
        "Execute Twilio DPA at twilio.com/legal/data-protection-addendum "
        "then set DPA_TWILIO_CONFIRMED=confirmed in your environment.",
    ),
    (
        "openai_zero_retention_confirmed",
        "OPENAI_ZERO_RETENTION_CONFIRMED",
        "Verify OpenAI 'no training' API mode is active on your account dashboard "
        "(platform.openai.com → Settings → Data Controls → API data usage policies). "
        "Then set OPENAI_ZERO_RETENTION_CONFIRMED=confirmed in your environment.",
    ),
]


def run_legal_checks(environment: str, settings) -> None:
    """Run DPA verification checks on startup.

    Args:
        environment: Value of the ENVIRONMENT env var ("production" | "development" | "sandbox")
        settings:    Pydantic Settings object with DPA confirmation fields

    Raises:
        RuntimeError: In production mode if any required DPA confirmation is missing.
    """
    is_production = environment.lower() == "production"
    failures = []

    for attr, env_var_name, instruction in _REQUIRED_CHECKS:
        value = getattr(settings, attr, "")
        if value != "confirmed":
            failures.append((env_var_name, instruction))

    if not failures:
        logger.info("Legal checks: all DPA confirmations present ✓")
        return

    for env_var_name, instruction in failures:
        if is_production:
            logger.error(
                f"LEGAL GATE FAILURE: {env_var_name} not set to 'confirmed'. "
                f"{instruction}"
            )
        else:
            logger.warning(
                f"Legal warning [{environment}]: {env_var_name} not confirmed. "
                f"This would block production startup. {instruction}"
            )

    if is_production:
        var_names = ", ".join(name for name, _ in failures)
        raise RuntimeError(
            f"Production startup blocked — missing DPA confirmations: {var_names}. "
            f"Set each variable to 'confirmed' after executing the required agreements. "
            f"See README_LEGAL.md for instructions."
        )


def get_legal_checks_status(settings) -> str:
    """Return the current legal checks status for the /health endpoint.

    Returns:
        "passing"  — all DPA confirmations present
        "warning"  — some confirmations missing (non-production)
        "blocking" — all confirmations missing
    """
    missing_count = 0
    total = len(_REQUIRED_CHECKS)

    for attr, _, _ in _REQUIRED_CHECKS:
        value = getattr(settings, attr, "")
        if value != "confirmed":
            missing_count += 1

    if missing_count == 0:
        return "passing"
    elif missing_count == total:
        return "blocking"
    else:
        return "warning"
