"""Shared time helpers for the batch jobs.

Business days are local (see constants.LOCAL_TZ); data timestamps are UTC.
"""
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ..constants import LOCAL_TZ


def now():
    """Current time. Jobs run under cron; FAKE_NOW is only set in test rigs."""
    fake = os.environ.get("FAKE_NOW")
    if fake:
        return datetime.fromisoformat(fake)
    return datetime.now(timezone.utc)


def local_day_window_utc(day):
    """UTC window covering one local business day.

    Compute both local midnights first, then normalize to UTC. Some local days
    are not exactly 24 hours long across DST transitions.
    """
    tz = ZoneInfo(LOCAL_TZ)
    start = datetime(day.year, day.month, day.day, tzinfo=tz)
    end = datetime.fromordinal(day.toordinal() + 1).replace(tzinfo=tz)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def local_month_window_utc(year, month):
    """UTC window covering one local business month."""
    tz = ZoneInfo(LOCAL_TZ)
    start = datetime(year, month, 1, tzinfo=tz)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=tz)
    else:
        end = datetime(year, month + 1, 1, tzinfo=tz)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)
