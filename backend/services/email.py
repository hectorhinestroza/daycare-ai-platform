"""Transactional email service using Resend.

Sends consent magic links and other platform emails.
Falls back to logging if RESEND_API_KEY is not configured (dev mode).
"""

import logging
from typing import Optional

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


async def send_consent_email(
    to_email: str,
    parent_name: str,
    child_name: str,
    center_name: str,
    token: str,
) -> bool:
    """Send the parental consent magic link email.

    Args:
        to_email:    Parent's email address
        parent_name: Parent's display name
        child_name:  Child's first name (for personalization)
        center_name: Daycare center name
        token:       Consent token UUID string

    Returns:
        True if sent successfully, False otherwise.
    """
    settings = get_settings()
    magic_link = f"{settings.app_base_url}/consent/{token}"

    if not settings.resend_api_key:
        logger.warning(
            f"RESEND_API_KEY not set — logging email instead.\n"
            f"  To: {to_email}\n"
            f"  Magic link: {magic_link}"
        )
        return False

    subject = f"{center_name} — Complete enrollment for {child_name}"

    html_body = f"""
    <div style="font-family: 'Inter', -apple-system, sans-serif; max-width: 520px; margin: 0 auto; padding: 40px 24px; color: #1a1a1a;">
      <h2 style="font-size: 22px; font-weight: 600; margin-bottom: 8px;">Welcome to {center_name} 🌿</h2>
      <p style="color: #666; font-size: 15px; line-height: 1.6; margin-bottom: 24px;">
        Hi {parent_name}, we need your consent before we can start sharing {child_name}'s daily updates with you.
      </p>
      <p style="font-size: 15px; line-height: 1.6; margin-bottom: 32px;">
        This takes about 30 seconds. You'll review four simple consent items covering daily reports, photos, voice memo processing, and billing data.
      </p>
      <a href="{magic_link}"
         style="display: inline-block; background: #2d6a4f; color: white; text-decoration: none;
                padding: 14px 32px; border-radius: 8px; font-size: 15px; font-weight: 600;">
        Complete Enrollment →
      </a>
      <p style="color: #999; font-size: 12px; margin-top: 32px; line-height: 1.5;">
        This link expires in 7 days. If you didn't expect this email, you can safely ignore it.
        <br>— The Raina Team
      </p>
    </div>
    """

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                RESEND_API_URL,
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": settings.resend_from_email,
                    "to": [to_email],
                    "subject": subject,
                    "html": html_body,
                },
                timeout=10.0,
            )

        if resp.status_code in (200, 201):
            logger.info(f"Consent email sent to {to_email} for child {child_name}")
            return True
        else:
            logger.error(f"Resend API error {resp.status_code}: {resp.text}")
            return False

    except Exception as e:
        logger.error(f"Failed to send consent email to {to_email}: {e}")
        return False


async def send_email(
    to: str,
    subject: str,
    html: str,
    from_email: Optional[str] = None,
) -> bool:
    """Generic email send — for future use (invoices, notifications, etc.)."""
    settings = get_settings()

    if not settings.resend_api_key:
        logger.warning(f"RESEND_API_KEY not set — email to {to} not sent.")
        return False

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                RESEND_API_URL,
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": from_email or settings.resend_from_email,
                    "to": [to],
                    "subject": subject,
                    "html": html,
                },
                timeout=10.0,
            )

        if resp.status_code in (200, 201):
            logger.info(f"Email sent to {to}: {subject}")
            return True
        else:
            logger.error(f"Resend API error {resp.status_code}: {resp.text}")
            return False

    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        return False
