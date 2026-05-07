"""Singleton AsyncOpenAI client.

Per-call OpenAI() instantiation creates a new HTTP connection pool every
time, which is wasteful and (on the sync client) blocks the event loop on
the first request after process start. Using AsyncOpenAI as a module-level
singleton:

  - shares a single connection pool across the whole pipeline
  - lets multiple inflight requests interleave on one event loop
  - removes the per-request setup cost

Cached via @lru_cache so the first caller pays the construction cost and
everyone after gets the same object.
"""

from functools import lru_cache

from openai import AsyncOpenAI

from backend.config import get_settings


@lru_cache(maxsize=1)
def get_openai_client() -> AsyncOpenAI:
    """Return the shared AsyncOpenAI client. Constructed on first call."""
    settings = get_settings()
    return AsyncOpenAI(api_key=settings.openai_api_key)
