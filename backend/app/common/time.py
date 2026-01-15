"""
Time Utilities

Backend policy:
- Store/query in database as UTC (naive) timestamps.
- Use UTC-aware datetimes at the domain/API boundary.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

UTC = timezone.utc


def utc_now() -> datetime:
    """Return current UTC time (timezone-aware)."""
    return datetime.now(UTC)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Ensure a datetime is UTC-aware.

    - If `dt` is naive, treat it as UTC.
    - If `dt` is timezone-aware, convert it to UTC.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_utc_naive(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Convert a datetime to naive UTC for database storage/query.

    Returns `None` if input is `None`.
    """
    aware = ensure_utc(dt)
    if aware is None:
        return None
    return aware.replace(tzinfo=None)

