from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_auth
from ..models import Commit, CodeReview, Monitor, Repo, Report, ReviewFinding, ReviewTask, WorkEntry
from ..services.config_store import get_llm_config
from ..timeutil import day_bounds, now_local

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(require_auth)])


def _count_commits(db: Session, start, end) -> int:
    low, high = day_bounds(start, end)
    return int(
        db.execute(
            select(func.count()).select_from(Commit).where(Commit.committed_at >= low, Commit.committed_at <= high)
        ).scalar_one()
    )


@router.get("/overview")
def overview(db: Session = Depends(get_db)) -> dict:
    today = now_local().date()
    week_start = today - timedelta(days=today.weekday())
    prev_week_start = week_start - timedelta(days=7)
    prev_week_end = week_start - timedelta(days=1)
    lo_today, hi_today = day_bounds(today, today)

    repo_count = db.execute(select(func.count()).select_from(Repo)).scalar_one()
    commit_total = db.execute(select(func.count()).select_from(Commit)).scalar_one()
    commit_today = db.execute(
        select(func.count()).select_from(Commit).where(Commit.committed_at >= lo_today, Commit.committed_at <= hi_today)
    ).scalar_one()
    commit_week = _count_commits(db, week_start, today)
    commit_week_prev = _count_commits(db, prev_week_start, prev_week_end)
    work_total = db.execute(select(func.count()).select_from(WorkEntry)).scalar_one()
    work_week = db.execute(
        select(func.count()).select_from(WorkEntry).where(WorkEntry.work_date >= week_start, WorkEntry.work_date <= today)
    ).scalar_one()
    hours_week = db.execute(
        select(func.coalesce(func.sum(WorkEntry.hours), 0)).where(WorkEntry.work_date >= week_start, WorkEntry.work_date <= today)
    ).scalar_one()
    report_count = db.execute(select(func.count()).select_from(Report)).scalar_one()
    project_count = db.execute(
        select(func.count(func.distinct(WorkEntry.project)))
    ).scalar_one()
    project_count = int(project_count or 0)
    repo_projects = {
        (row[0] or row[1] or "").strip()
        for row in db.execute(select(Repo.project, Repo.name)).all()
    }
    project_count += len({name for name in repo_projects if name})

    monitor_total = db.execute(select(func.count()).select_from(Monitor)).scalar_one()
    monitor_ok = db.execute(
        select(func.count()).select_from(Monitor).where(Monitor.last_status == "ok")
    ).scalar_one()
    monitor_fail = db.execute(
        select(func.count()).select_from(Monitor).where(Monitor.last_status == "fail")
    ).scalar_one()

    line_rows = db.execute(
        select(func.coalesce(func.sum(Commit.additions), 0), func.coalesce(func.sum(Commit.deletions), 0))
    ).one()
    total_additions = int(line_rows[0] or 0)
    total_deletions = int(line_rows[1] or 0)

    review_count = db.execute(select(func.count()).select_from(CodeReview)).scalar_one()
    finding_total = db.execute(select(func.count()).select_from(ReviewFinding)).scalar_one()
    finding_pending = db.execute(
        select(func.count()).select_from(ReviewFinding).where(ReviewFinding.status == "pending")
    ).scalar_one()
    review_running = db.execute(
        select(func.count()).select_from(ReviewTask).where(ReviewTask.status.in_(["pending", "running"]))
    ).scalar_one()

    trend_start = today - timedelta(days=13)
    lo_trend, _ = day_bounds(trend_start, today)
    trend_rows = db.execute(
        select(func.date(Commit.committed_at), func.count())
        .where(Commit.committed_at >= lo_trend)
        .group_by(func.date(Commit.committed_at))
        .order_by(func.date(Commit.committed_at))
    ).all()
    counter = {str(day): int(count) for day, count in trend_rows}
    trend = [
        {
            "date": (trend_start + timedelta(days=offset)).isoformat(),
            "count": counter.get((trend_start + timedelta(days=offset)).isoformat(), 0),
        }
        for offset in range(14)
    ]

    repo_rows = db.execute(
        select(
            Repo.id,
            Repo.name,
            func.count(Commit.id),
            func.coalesce(func.sum(Commit.additions), 0),
            func.coalesce(func.sum(Commit.deletions), 0),
        )
        .join(Commit, Commit.repo_id == Repo.id)
        .group_by(Repo.id)
        .order_by(func.count(Commit.id).desc())
    ).all()
    by_repo = [
        {
            "name": name,
            "count": int(count),
            "additions": int(additions or 0),
            "deletions": int(deletions or 0),
        }
        for _, name, count, additions, deletions in repo_rows
    ]

    project_map: dict[str, dict] = {}

    def project_bucket(label: str) -> dict:
        return project_map.setdefault(label, {"name": label, "count": 0})

    repo_meta = db.execute(select(Repo.id, Repo.project, Repo.name)).all()
    commit_counts = dict(db.execute(select(Commit.repo_id, func.count()).group_by(Commit.repo_id)).all())
    for repo_id, project, name in repo_meta:
        label = (project or name or "").strip()
        if not label:
            continue
        project_bucket(label)["count"] += int(commit_counts.get(repo_id, 0))
    for label, count in db.execute(select(WorkEntry.project, func.count()).group_by(WorkEntry.project)).all():
        name = (label or "").strip()
        if not name:
            continue
        project_bucket(name)["count"] += int(count)
    by_project = sorted(project_map.values(), key=lambda item: item["count"], reverse=True)

    recent_rows = db.execute(
        select(Commit, Repo).join(Repo, Commit.repo_id == Repo.id).order_by(Commit.committed_at.desc()).limit(5)
    ).all()
    recent_commits = [
        {
            "id": commit.id,
            "repo_name": repo.name,
            "short_sha": commit.short_sha or commit.sha[:8],
            "subject": (commit.message or "").splitlines()[0] if commit.message else "",
            "author_name": commit.author_name,
            "committed_at": commit.committed_at.isoformat(),
        }
        for commit, repo in recent_rows
    ]

    recent_reports = db.execute(select(Report).order_by(Report.created_at.desc()).limit(4)).scalars().all()
    report_items = [
        {
            "id": item.id,
            "title": item.title,
            "period_type": item.period_type,
            "finding_count": item.stats_json.get("commit_count", 0) if item.stats_json else 0,
            "created_at": item.created_at.isoformat(),
        }
        for item in recent_reports
    ]

    recent_reviews = db.execute(
        select(CodeReview).order_by(CodeReview.created_at.desc()).limit(3)
    ).scalars().all()
    review_items = [
        {
            "id": item.id,
            "repo_id": item.repo_id,
            "short_sha": item.commit_sha[:8],
            "subject": item.commit_subject,
            "status": item.status,
            "finding_count": item.finding_count,
            "created_at": item.created_at.isoformat(),
        }
        for item in recent_reviews
    ]

    activity: list[dict] = []
    for item in recent_commits:
        activity.append(
            {
                "kind": "commit",
                "text": item["subject"],
                "meta": item["repo_name"],
                "time": item["committed_at"],
            }
        )
    for item in report_items:
        activity.append(
            {"kind": "report", "text": item["title"], "meta": "报告", "time": item["created_at"]}
        )
    for item in review_items:
        activity.append(
            {
                "kind": "review",
                "text": item["subject"] or item["short_sha"],
                "meta": "代码审查",
                "time": item["created_at"],
            }
        )
    activity.sort(key=lambda row: row["time"], reverse=True)
    activity = activity[:8]

    last_sync = db.execute(select(func.max(Repo.last_sync_at))).scalar_one()
    llm = get_llm_config(db)

    return {
        "repo_count": int(repo_count),
        "commit_total": int(commit_total),
        "commit_today": int(commit_today),
        "commit_week": int(commit_week),
        "commit_week_prev": int(commit_week_prev),
        "work_total": int(work_total),
        "work_week": int(work_week),
        "hours_week": float(hours_week or 0),
        "report_count": int(report_count),
        "project_count": project_count,
        "monitor_total": int(monitor_total),
        "monitor_ok": int(monitor_ok),
        "monitor_fail": int(monitor_fail),
        "review_count": int(review_count),
        "finding_total": int(finding_total),
        "finding_pending": int(finding_pending),
        "review_running": int(review_running),
        "total_additions": total_additions,
        "total_deletions": total_deletions,
        "llm_ready": llm.ready,
        "llm_model": llm.model,
        "last_sync_at": last_sync.isoformat() if last_sync else None,
        "trend": trend,
        "by_repo": by_repo,
        "by_project": by_project,
        "recent_commits": recent_commits,
        "recent_reports": report_items,
        "recent_reviews": review_items,
        "activity": activity,
    }