from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..deps import require_auth
from ..models import Report
from ..schemas import ReportGenerate, ReportOut, ReportUpdate
from ..services import task_queue
from ..services.report import default_title, generate_report, resolve_period, run_report_task

router = APIRouter(prefix="/api/reports", tags=["reports"], dependencies=[Depends(require_auth)])


def _to_out(report: Report) -> ReportOut:
    return ReportOut(
        id=report.id,
        title=report.title,
        period_type=report.period_type,
        start_date=report.start_date,
        end_date=report.end_date,
        summary=report.summary,
        content=report.content,
        stats=report.stats_json,
        model=report.model,
        status=report.status,
        stage=report.stage or "",
        progress=report.progress or 0,
        error=report.error,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


@router.get("")
def list_reports(
    db: Session = Depends(get_db),
    period_type: str | None = None,
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
) -> dict:
    conditions = []
    if period_type:
        conditions.append(Report.period_type == period_type)
    if keyword:
        conditions.append(Report.title.like(f"%{keyword.strip()}%"))
    total = db.execute(select(func.count()).select_from(Report).where(*conditions)).scalar_one()
    rows = db.execute(
        select(Report)
        .where(*conditions)
        .order_by(Report.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    return {
        "total": int(total),
        "page": page,
        "page_size": page_size,
        "items": [_to_out(row) for row in rows],
    }


@router.post("/generate", status_code=201)
async def generate(payload: ReportGenerate, db: Session = Depends(get_db)) -> ReportOut:
    """建立生成任务并立即返回，实际生成在后台进行。"""
    start, end = resolve_period(
        payload.period_type,
        payload.reference_date,
        payload.start_date,
        payload.end_date,
    )
    report = Report(
        title=payload.title or default_title(payload.period_type, start, end),
        period_type=payload.period_type,
        start_date=start,
        end_date=end,
        status="generating",
        stage="排队中",
        progress=5,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    options = {
        "period_type": payload.period_type,
        "start": start,
        "end": end,
        "title": payload.title,
        "focus": payload.focus,
        "include_commits": payload.include_commits,
        "include_works": payload.include_works,
        "use_llm": payload.use_llm,
    }
    task_queue.submit(lambda: run_report_task(report.id, options))
    return _to_out(report)


@router.get("/{report_id}/stream")
async def stream_report(report_id: int) -> StreamingResponse:
    """推送生成进度与正文增量。"""

    async def event_source():
        last: dict | None = None
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            db = SessionLocal()
            try:
                report = db.get(Report, report_id)
                if not report:
                    yield "event: error\ndata: {\"message\":\"报告不存在\"}\n\n"
                    return
                payload = {
                    "id": report.id,
                    "status": report.status,
                    "stage": report.stage or "",
                    "progress": report.progress or 0,
                    "content": report.content or "",
                    "error": report.error or "",
                    "model": report.model or "",
                    "summary": report.summary or "",
                    "stats": report.stats_json or {},
                }
            finally:
                db.close()

            if payload != last:
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                last = payload
            if payload["status"] in ("published", "failed"):
                return
            await asyncio.sleep(0.4)

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{report_id}")
def get_report(report_id: int, db: Session = Depends(get_db)) -> ReportOut:
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    return _to_out(report)


@router.put("/{report_id}")
def update_report(report_id: int, payload: ReportUpdate, db: Session = Depends(get_db)) -> ReportOut:
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(report, key, value)
    db.commit()
    db.refresh(report)
    return _to_out(report)


@router.delete("/{report_id}")
def delete_report(report_id: int, db: Session = Depends(get_db)) -> dict:
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    db.delete(report)
    db.commit()
    return {"ok": True}