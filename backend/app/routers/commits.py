from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_auth
from ..models import Commit, Repo
from ..timeutil import day_bounds

router = APIRouter(prefix="/api/commits", tags=["commits"], dependencies=[Depends(require_auth)])


@router.get("/authors")
def list_authors(db: Session = Depends(get_db)) -> list[dict]:
    """已同步提交中出现过的作者，用于挑选「我的作者标识」。"""
    rows = db.execute(
        select(
            Commit.author_name,
            Commit.author_email,
            Commit.author_login,
            func.count().label("total"),
        )
        .group_by(Commit.author_name, Commit.author_email, Commit.author_login)
        .order_by(func.count().desc())
    ).all()
    return [
        {
            "author_name": name or "",
            "author_email": email or "",
            "author_login": login or "",
            "count": int(total),
        }
        for name, email, login, total in rows
    ]


@router.get("")
def list_commits(
    db: Session = Depends(get_db),
    repo_id: int | None = None,
    keyword: str | None = None,
    author: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
) -> dict:
    conditions = []
    if repo_id:
        conditions.append(Commit.repo_id == repo_id)
    if keyword:
        pattern = f"%{keyword.strip()}%"
        conditions.append(
            or_(Commit.message.like(pattern), Commit.author_name.like(pattern), Commit.sha.like(pattern))
        )
    if author:
        pattern = f"%{author.strip()}%"
        conditions.append(or_(Commit.author_name.like(pattern), Commit.author_login.like(pattern)))
    if start_date:
        low, _ = day_bounds(start_date, start_date)
        conditions.append(Commit.committed_at >= low)
    if end_date:
        _, high = day_bounds(end_date, end_date)
        conditions.append(Commit.committed_at <= high)

    total = db.execute(select(func.count()).select_from(Commit).where(*conditions)).scalar_one()
    rows = db.execute(
        select(Commit, Repo)
        .join(Repo, Commit.repo_id == Repo.id)
        .where(*conditions)
        .order_by(Commit.committed_at.desc(), Commit.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [
        {
            "id": commit.id,
            "repo_id": commit.repo_id,
            "repo_name": repo.name,
            "sha": commit.sha,
            "short_sha": commit.short_sha or commit.sha[:8],
            "message": commit.message,
            "author_name": commit.author_name,
            "author_email": commit.author_email,
            "author_login": commit.author_login,
            "url": commit.url,
            "additions": commit.additions,
            "deletions": commit.deletions,
            "changed_files": commit.changed_files,
            "committed_at": commit.committed_at.isoformat(),
        }
        for commit, repo in rows
    ]
    return {"total": int(total), "page": page, "page_size": page_size, "items": items}