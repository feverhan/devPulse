from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ..config import settings
from ..database import SessionLocal
from .sync import sync_all

logger = logging.getLogger("worklog.scheduler")

_scheduler: AsyncIOScheduler | None = None


async def _run_sync() -> None:
    db = SessionLocal()
    try:
        await sync_all(db)
    except Exception:  # noqa: BLE001 - keep the scheduler alive
        logger.exception("定时同步失败")
    finally:
        db.close()


async def _run_monitors() -> None:
    """巡检到期的监控目标，实际检查放进后台队列，避免阻塞调度。"""
    from . import task_queue
    from .monitor import due_monitors, run_check

    db = SessionLocal()
    try:
        for monitor in due_monitors(db):
            task_queue.submit(lambda mid=monitor.id: run_check(mid))
    except Exception:  # noqa: BLE001
        logger.exception("监控巡检失败")
    finally:
        db.close()


def _interval_minutes() -> int:
    db = SessionLocal()
    try:
        from .config_store import get_sync_settings

        return max(5, int(get_sync_settings(db)["sync_interval_minutes"]))
    except Exception:  # noqa: BLE001
        return max(5, int(settings.sync_interval_minutes))
    finally:
        db.close()


def start_scheduler() -> AsyncIOScheduler | None:
    global _scheduler
    if _scheduler:
        return _scheduler
    scheduler = AsyncIOScheduler(timezone=settings.app_timezone)
    minutes = _interval_minutes()
    scheduler.add_job(
        _run_sync,
        trigger=IntervalTrigger(minutes=minutes),
        id="repo_sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _run_monitors,
        trigger=IntervalTrigger(minutes=1),
        id="monitor_check",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info("定时同步已启动，间隔 %s 分钟", minutes)
    return scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def reschedule_sync(minutes: int) -> None:
    if not _scheduler:
        return
    _scheduler.add_job(
        _run_sync,
        trigger=IntervalTrigger(minutes=max(5, int(minutes))),
        id="repo_sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )