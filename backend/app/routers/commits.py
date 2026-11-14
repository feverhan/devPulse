from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_auth
from ..models import Commit, Repo, RepoAuthor
from ..timeutil import day_bounds

router = APIRouter(prefix="/api/commits", tags=["commits"], dependencies=[Depends(require_auth)])


@router.get("/authors")
def list_authors(db: Session = Depends(get_db)) -> list[dict]:
    """用于挑选「我的作者标识」的候选作者。

    两个来源合并：本地已入库的提交作者，以及同步时见过但未入库的作者。
    只看已入库的作者会形成循环：先按标识过滤掉他人，候选里就永远没有他人。
    """
    committed: dict[tuple[str, str, str], int] = {}
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
    for name, email, login, total in rows:
        key = ((name or "").strip(), (email or "").strip(), (login or "").strip())
        committed[key] = committed.get(key, 0) + int(total)

    seen: dict[tuple[str, str, str], int] = {}
    for row in db.execute(select(RepoAuthor)).scalars().all():
        key = ((row.author_name or "").strip(), (row.author_email or "").strip(), (row.author_login or "").strip())
        seen[key] = max(seen.get(key, 0), int(row.commit_count or 0))

    merged: list[dict] = []
    for key in set(committed) | set(seen):
        name, email, login = key
        local = committed.get(key, 0)
        merged.append(
            {
                "author_name": name,
                "author_email": email,
                "author_login": login,
                "count": local or seen.get(key, 0),
                "committed": local,
                "seen": seen.get(key, 0),
            }
        )
    merged.sort(key=lambda item: (item["committed"], item["seen"], item["count"]), reverse=True)
    return merged


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