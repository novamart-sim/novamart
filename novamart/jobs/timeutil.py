"""Shared time helpers for the batch jobs.

Business days are local (see constants.LOCAL_TZ); data timestamps are UTC.
"""
import os
from datetime import datetime, timedelta, timezone
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

    We normalize to UTC right away and work in UTC from there — avoids all
    the timezone weirdness downstream.
    """
    tz = ZoneInfo(LOCAL_TZ)
    start = datetime(day.year, day.month, day.day, tzinfo=tz).astimezone(timezone.utc)
    end = start + timedelta(hours=24)
    return start, end


def local_month_window_utc(year, month):
    """UTC window covering one local business month."""
    tz = ZoneInfo(LOCAL_TZ)
    start = datetime(year, month, 1, tzinfo=tz)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=tz)
    else:
        end = datetime(year, month + 1, 1, tzinfo=tz)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)
