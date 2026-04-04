"""Billing event schemas — late pickup, extra hours, drop-in.

Billing events are extracted from voice memos like any other event,
but they carry financial weight and always require director review.
These will be removed from EventType in a future refactor when billing
gets its own pipeline (Issue #13).
"""

from typing import Literal, Optional

from schemas.events import BaseEvent


class BillingEvent(BaseEvent):
    """Billing event — always requires director review.

    Extracted from voice: "Marcus was picked up 45 minutes late."
    Auto-calculates amount from center config.
    """
    billing_type: Literal['LATE_PICKUP', 'EXTRA_HOURS', 'DROP_IN']
    minutes_over: Optional[int] = None
    hours_extra: Optional[float] = None
    amount_usd: Optional[float] = None     # auto-calculated from center config
    stripe_invoice_id: Optional[str] = None
