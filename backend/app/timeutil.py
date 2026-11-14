from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from .config import settings


def app_tz() -> ZoneInfo:
    """业务时区。名称非法时回退到 Asia/Shanghai，避免因配置错误起不来。"""
    name = (settings.app_timezone or "").strip() or "Asia/Shanghai"
    try:
        return ZoneInfo(name)
    except Exception:  # noqa: BLE001 - 时区名可能非法
        logging.getLogger("worklog").warning("时区 %s 无效，回退到 Asia/Shanghai", name)
        return ZoneInfo("Asia/Shanghai")


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