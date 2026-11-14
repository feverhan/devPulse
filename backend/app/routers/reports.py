from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_auth
from ..models import Report
from ..schemas import ReportGenerate, ReportOut, ReportUpdate
from ..services.report import generate_report, resolve_period

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
    start, end = resolve_period(
        payload.period_type,
        payload.reference_date,
        payload.start_date,
        payload.end_date,
    )
    result = await generate_report(
        db,
        period_type=payload.period_type,
        start=start,
        end=end,
        title=payload.title,
        focus=payload.focus,
        include_commits=payload.include_commits,
        include_works=payload.include_works,
        use_llm=payload.use_llm,
    )
    report = Report(
        title=result["title"],
        period_type=result["period_type"],
        start_date=result["start_date"],
        end_date=result["end_date"],
        summary=result["summary"],
        content=result["content"],
        stats_json=result["stats"],
        source_json=result["source"],
        model=result["model"],
        status=result["status"],
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return _to_out(report)


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