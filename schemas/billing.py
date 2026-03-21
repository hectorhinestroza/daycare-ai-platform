from typing import Optional, Literal
from schemas.events import BaseEvent

class BillingEvent(BaseEvent):
    billing_type: Literal['LATE_PICKUP', 'EXTRA_HOURS', 'DROP_IN']
    minutes_over: Optional[int] = None
    hours_extra: Optional[float] = None
    amount_usd: Optional[float] = None     # auto-calculated from center config
    stripe_invoice_id: Optional[str] = None
