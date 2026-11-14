from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_auth
from ..models import Commit, Project, Repo, WorkEntry

router = APIRouter(prefix="/api/projects", tags=["projects"], dependencies=[Depends(require_auth)])


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    note: str = ""


def ensure_project(db: Session, name: str, source: str = "auto") -> Project:
    """登记项目名，已存在时直接返回。"""
    label = (name or "").strip()
    if not label:
        raise ValueError("项目名不能为空")
    existing = db.execute(select(Project).where(Project.name == label)).scalar_one_or_none()
    if existing:
        return existing
    project = Project(name=label, source=source)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def _merged_projects(db: Session) -> list[dict]:
    """合并手工登记的项目、仓库归属的项目与工作记录里的项目。"""
    stats: dict[str, dict] = {}

    def bucket(name: str, source: str, note: str = "") -> dict:
        key = name.strip()
        entry = stats.get(key)
        if entry is None:
            entry = {
                "id": None,
                "name": key,
                "source": source,
                "note": note,
                "repos": 0,
                "commits": 0,
                "works": 0,
            }
            stats[key] = entry
        return entry

    for project in db.execute(select(Project)).scalars().all():
        entry = bucket(project.name, project.source, project.note or "")
        entry["id"] = project.id
        if project.source == "manual":
            entry["source"] = "manual"

    commit_counts = dict(
        db.execute(select(Commit.repo_id, func.count()).group_by(Commit.repo_id)).all()
    )
    for repo in db.execute(select(Repo)).scalars().all():
        label = (repo.project or repo.name or "").strip()
        if not label:
            continue
        entry = bucket(label, "auto")
        entry["repos"] += 1
        entry["commits"] += int(commit_counts.get(repo.id, 0))

    work_counts = dict(
        db.execute(select(WorkEntry.project, func.count()).group_by(WorkEntry.project)).all()
    )
    for label, count in work_counts.items():
        name = (label or "").strip()
        if not name:
            continue
        entry = bucket(name, "auto")
        entry["works"] += int(count)

    items = list(stats.values())
    items.sort(key=lambda item: (item["source"] != "manual", -item["commits"], -item["works"], item["name"]))
    return items


@router.get("")
def list_projects(db: Session = Depends(get_db)) -> list[dict]:
    """项目清单：手工登记的 + 从提交记录中抽取的。"""
    return _merged_projects(db)


@router.post("", status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> dict:
    label = payload.name.strip()
    exists = db.execute(select(Project).where(Project.name == label)).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="项目已存在")
    project = Project(name=label, source="manual", note=payload.note.strip())
    db.add(project)
    db.commit()
    db.refresh(project)
    for item in _merged_projects(db):
        if item["name"] == label:
            return item
    return {
        "id": project.id,
        "name": label,
        "source": "manual",
        "note": project.note,
        "repos": 0,
        "commits": 0,
        "works": 0,
    }


@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)) -> dict:
    """删除项目登记，并删除该项目下的工作记录。"""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    label = project.name
    entries = db.execute(select(WorkEntry).where(WorkEntry.project == label)).scalars().all()
    removed_works = len(entries)
    for entry in entries:
        db.delete(entry)
    db.delete(project)
    db.commit()
    return {"ok": True, "removed_works": removed_works}