"""Twilio webhook signature verification — pilot §1.3.

Twilio signs every webhook with HMAC-SHA1 using the account auth token. Without
verification, anyone who learns the public webhook URL can POST forged events
into the system. This dependency rejects requests with missing or invalid
signatures in production.

Two important deployment details:

  1. **HTTPS behind a proxy.** Railway terminates TLS, so uvicorn sees an
     http:// URL but Twilio signed an https:// URL. We rebuild the URL from
     the X-Forwarded-Proto header before validating.

  2. **Dev/test bypass.** Test client and local development don't sign
     requests. We bypass verification when ENVIRONMENT is "development" or
     "test", logging a warning so the bypass is obvious in stdout.
"""

import logging

from fastapi import HTTPException, Request
from twilio.request_validator import RequestValidator

from backend.config import get_settings

logger = logging.getLogger(__name__)


def _twilio_request_url(request: Request) -> str:
    """Return the URL Twilio actually called (https-aware behind a proxy)."""
    url = str(request.url)
    proto = request.headers.get("x-forwarded-proto", "").lower()
    if proto == "https" and url.startswith("http://"):
        url = "https://" + url[len("http://") :]
    return url


async def verify_twilio_signature(request: Request) -> None:
    """FastAPI dependency that validates the X-Twilio-Signature header.

    Raises HTTPException(403) on missing or invalid signatures in production.
    """
    settings = get_settings()
    env = settings.environment.lower()

    if env in ("development", "test"):
        logger.warning(
            "twilio_security: signature verification BYPASSED (environment=%s) — "
            "production will enforce.",
            env,
        )
        return

    auth_token = settings.twilio_auth_token
    if not auth_token:
        # Fail closed: without the auth token we cannot validate, which means
        # we cannot trust the request. Better a 500 than silently accepting.
        logger.error("twilio_security: TWILIO_AUTH_TOKEN is empty in production")
        raise HTTPException(status_code=500, detail="Server misconfigured")

    signature = request.headers.get("x-twilio-signature", "")
    if not signature:
        raise HTTPException(status_code=403, detail="Missing Twilio signature")

    # Starlette caches request.form() on the request object, so the downstream
    # handler can still read its Form(...) parameters after we call this.
    form = await request.form()
    params = {k: v for k, v in form.items()}

    validator = RequestValidator(auth_token)
    url = _twilio_request_url(request)

    if not validator.validate(url, params, signature):
        logger.warning("twilio_security: signature mismatch for url=%s", url)
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")
