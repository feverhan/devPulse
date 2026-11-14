from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_auth
from ..models import Monitor, MonitorCheck
from ..services import task_queue
from ..services.monitor import due_monitors, perform_check, probe_health_paths, run_check
from ..timeutil import now_local

router = APIRouter(prefix="/api/monitors", tags=["monitors"], dependencies=[Depends(require_auth)])


class MonitorIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=1, max_length=500)
    health_path: str = "/"
    method: str = "GET"
    expect_status: int = 200
    keyword: str = ""
    interval_minutes: int = Field(default=5, ge=1, le=1440)
    timeout: int = Field(default=10, ge=1, le=120)
    enabled: bool = True
    alert_enabled: bool = True


class ProbeIn(BaseModel):
    url: str
    use_llm: bool = True


def _out(monitor: Monitor) -> dict:
    uptime = 0.0
    if monitor.total_checks:
        uptime = round(monitor.ok_checks * 100.0 / monitor.total_checks, 1)
    next_check = None
    if monitor.enabled:
        if monitor.last_check_at is None:
            next_check = now_local().isoformat()
        else:
            next_check = (
                monitor.last_check_at + timedelta(minutes=max(1, monitor.interval_minutes))
            ).isoformat()
    return {
        "next_check_at": next_check,
        "id": monitor.id,
        "name": monitor.name,
        "url": monitor.url,
        "health_path": monitor.health_path,
        "method": monitor.method,
        "expect_status": monitor.expect_status,
        "keyword": monitor.keyword,
        "interval_minutes": monitor.interval_minutes,
        "timeout": monitor.timeout,
        "enabled": monitor.enabled,
        "alert_enabled": monitor.alert_enabled,
        "last_status": monitor.last_status,
        "last_check_at": monitor.last_check_at.isoformat() if monitor.last_check_at else None,
        "last_latency_ms": monitor.last_latency_ms,
        "last_error": monitor.last_error,
        "fail_count": monitor.fail_count,
        "total_checks": monitor.total_checks,
        "uptime": uptime,
        "created_at": monitor.created_at.isoformat() if monitor.created_at else None,
    }


@router.get("")
def list_monitors(db: Session = Depends(get_db)) -> list[dict]:
    monitors = db.execute(select(Monitor).order_by(Monitor.id.desc())).scalars().all()
    return [_out(item) for item in monitors]


@router.get("/overview")
def overview(db: Session = Depends(get_db)) -> dict:
    monitors = db.execute(select(Monitor)).scalars().all()
    items = [_out(item) for item in monitors]
    ok = [item for item in items if item["last_status"] == "ok"]
    fail = [item for item in items if item["last_status"] == "fail"]
    latencies = [item["last_latency_ms"] for item in items if item["last_latency_ms"] > 0]
    return {
        "total": len(items),
        "ok": len(ok),
        "fail": len(fail),
        "pending": len([item for item in items if not item["last_status"]]),
        "avg_latency_ms": int(sum(latencies) / len(latencies)) if latencies else 0,
        "monitors": items,
    }


@router.post("", status_code=201)
def create_monitor(payload: MonitorIn, db: Session = Depends(get_db)) -> dict:
    monitor = Monitor(**payload.model_dump())
    db.add(monitor)
    db.commit()
    db.refresh(monitor)
    return _out(monitor)


@router.put("/{monitor_id}")
def update_monitor(monitor_id: int, payload: MonitorIn, db: Session = Depends(get_db)) -> dict:
    monitor = db.get(Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="监控目标不存在")
    for key, value in payload.model_dump().items():
        setattr(monitor, key, value)
    db.commit()
    db.refresh(monitor)
    return _out(monitor)


@router.delete("/{monitor_id}")
def delete_monitor(monitor_id: int, db: Session = Depends(get_db)) -> dict:
    monitor = db.get(Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="监控目标不存在")
    db.delete(monitor)
    db.commit()
    return {"ok": True}


@router.post("/probe")
async def probe(payload: ProbeIn) -> dict:
    """探测服务可用的健康检查路径。"""
    try:
        return await probe_health_paths(payload.url, use_llm=payload.use_llm)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{monitor_id}/check")
async def check_now(monitor_id: int, db: Session = Depends(get_db)) -> dict:
    monitor = db.get(Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="监控目标不存在")
    return await perform_check(db, monitor)


@router.post("/{monitor_id}/run")
def run_now(monitor_id: int, db: Session = Depends(get_db)) -> dict:
    """放入后台队列异步检查。"""
    monitor = db.get(Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="监控目标不存在")
    task_queue.submit(lambda: run_check(monitor_id))
    return {"ok": True, "message": "已排入检查队列"}


@router.get("/{monitor_id}/checks")
def check_history(monitor_id: int, db: Session = Depends(get_db), limit: int = 50) -> list[dict]:
    rows = db.execute(
        select(MonitorCheck)
        .where(MonitorCheck.monitor_id == monitor_id)
        .order_by(MonitorCheck.checked_at.desc())
        .limit(min(limit, 200))
    ).scalars().all()
    return [
        {
            "id": row.id,
            "status": row.status,
            "status_code": row.status_code,
            "latency_ms": row.latency_ms,
            "error": row.error,
            "checked_at": row.checked_at.isoformat() if row.checked_at else None,
        }
        for row in rows
    ]