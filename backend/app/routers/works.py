from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_auth
from ..models import WorkEntry
from ..schemas import WorkEntryCreate, WorkEntryOut, WorkEntryUpdate
from .projects import ensure_project

router = APIRouter(prefix="/api/works", tags=["works"], dependencies=[Depends(require_auth)])


@router.get("")
def list_works(
    db: Session = Depends(get_db),
    keyword: str | None = None,
    category: str | None = None,
    project: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
) -> dict:
    conditions = []
    if keyword:
        pattern = f"%{keyword.strip()}%"
        conditions.append(
            or_(WorkEntry.title.like(pattern), WorkEntry.content.like(pattern), WorkEntry.project.like(pattern))
        )
    if category:
        conditions.append(WorkEntry.category == category)
    if project:
        conditions.append(WorkEntry.project == project)
    if start_date:
        conditions.append(WorkEntry.work_date >= start_date)
    if end_date:
        conditions.append(WorkEntry.work_date <= end_date)

    total = db.execute(select(func.count()).select_from(WorkEntry).where(*conditions)).scalar_one()
    rows = db.execute(
        select(WorkEntry)
        .where(*conditions)
        .order_by(WorkEntry.work_date.desc(), WorkEntry.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    return {
        "total": int(total),
        "page": page,
        "page_size": page_size,
        "items": [WorkEntryOut.model_validate(row) for row in rows],
    }


@router.post("", status_code=201)
def create_work(payload: WorkEntryCreate, db: Session = Depends(get_db)) -> WorkEntryOut:
    entry = WorkEntry(**payload.model_dump())
    db.add(entry)
    db.commit()
    ensure_project(db, entry.project)
    db.refresh(entry)
    return WorkEntryOut.model_validate(entry)


@router.put("/{work_id}")
def update_work(work_id: int, payload: WorkEntryUpdate, db: Session = Depends(get_db)) -> WorkEntryOut:
    entry = db.get(WorkEntry, work_id)
    if not entry:
        raise HTTPException(status_code=404, detail="记录不存在")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if value is not None:
            setattr(entry, key, value)
    db.commit()
    if data.get("project"):
        ensure_project(db, entry.project)
    db.refresh(entry)
    return WorkEntryOut.model_validate(entry)


@router.delete("/{work_id}")
def delete_work(work_id: int, db: Session = Depends(get_db)) -> dict:
    entry = db.get(WorkEntry, work_id)
    if not entry:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(entry)
    db.commit()
    return {"ok": True}