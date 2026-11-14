from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from .config import settings


def app_tz() -> ZoneInfo:
    return ZoneInfo(settings.app_timezone or "Asia/Shanghai")


def now_local() -> datetime:
    """Naive datetime in the business timezone."""
    return datetime.now(app_tz()).replace(tzinfo=None)


def today_local() -> date:
    return now_local().date()


def to_local_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(app_tz()).replace(tzinfo=None)


def parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp into naive business-timezone datetime."""
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return to_local_naive(parsed)


def day_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(start, datetime.min.time()),
        datetime.combine(end, datetime.max.time()),
    )