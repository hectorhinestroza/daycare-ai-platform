from datetime import date, datetime
from typing import Optional, Dict, Literal
from pydantic import BaseModel

class DailyNarrative(BaseModel):
    child_name: str
    date: date
    center_id: str
    headline: str                   # 1 sentence
    body: str                       # 120–250 words, warm tone
    tone: Literal['upbeat', 'neutral', 'needs-attention']
    photo_captions: Dict[str, str]  # photo_id → caption
    published_at: Optional[datetime] = None
    admin_override: bool = False
