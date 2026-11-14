from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_auth
from ..models import CodeReview, Repo, ReviewFinding, ReviewTask
from ..services import task_queue
from ..services.gitplatform import PlatformError
from ..services.review import push_findings, run_task

router = APIRouter(prefix="/api/reviews", tags=["reviews"], dependencies=[Depends(require_auth)])


class ReviewRunIn(BaseModel):
    repo_id: int
    limit: int = Field(default=10, ge=1, le=50)
    only_new: bool = True


def _task_out(task: ReviewTask, repo_name: str = "") -> dict:
    return {
        "id": task.id,
        "repo_id": task.repo_id,
        "repo_name": repo_name,
        "status": task.status,
        "limit": task.limit,
        "only_new": task.only_new,
        "total": task.total,
        "processed": task.processed,
        "finding_count": task.finding_count,
        "model": task.model,
        "message": task.message,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
    }


def _finding_out(finding: ReviewFinding) -> dict:
    return {
        "id": finding.id,
        "review_id": finding.review_id,
        "file_path": finding.file_path,
        "line": finding.line,
        "severity": finding.severity,
        "category": finding.category,
        "title": finding.title,
        "detail": finding.detail,
        "status": finding.status,
        "issue_number": finding.issue_number,
        "issue_url": finding.issue_url,
        "created_at": finding.created_at.isoformat() if finding.created_at else None,
    }


def _review_out(review: CodeReview, repo_name: str = "") -> dict:
    return {
        "id": review.id,
        "task_id": review.task_id,
        "repo_id": review.repo_id,
        "repo_name": repo_name,
        "commit_sha": review.commit_sha,
        "short_sha": review.commit_sha[:8],
        "commit_subject": review.commit_subject,
        "commit_url": review.commit_url,
        "author_name": review.author_name,
        "status": review.status,
        "finding_count": review.finding_count,
        "model": review.model,
        "message": review.message,
        "created_at": review.created_at.isoformat() if review.created_at else None,
        "findings": [_finding_out(item) for item in review.findings],
    }


def _repo_names(db: Session) -> dict[int, str]:
    return {item.id: item.name for item in db.execute(select(Repo)).scalars().all()}


@router.post("/tasks", status_code=201)
async def create_task(payload: ReviewRunIn, db: Session = Depends(get_db)) -> dict:
    """创建代码审查任务，后台执行，立即返回任务状态。"""
    repo = db.get(Repo, payload.repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="仓库不存在")
    task = ReviewTask(
        repo_id=repo.id,
        status="pending",
        limit=payload.limit,
        only_new=payload.only_new,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    task_queue.submit(lambda: run_task(task.id))
    return _task_out(task, repo.name)


@router.get("/tasks")
def list_tasks(db: Session = Depends(get_db), limit: int = 30) -> list[dict]:
    tasks = db.execute(select(ReviewTask).order_by(ReviewTask.created_at.desc()).limit(limit)).scalars().all()
    names = _repo_names(db)
    return [_task_out(task, names.get(task.repo_id, "")) for task in tasks]


@router.get("/tasks/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db)) -> dict:
    task = db.get(ReviewTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    names = _repo_names(db)
    return _task_out(task, names.get(task.repo_id, ""))


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: int, db: Session = Depends(get_db)) -> dict:
    task = db.get(ReviewTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status in ("pending", "running"):
        task.status = "cancelled"
        task.message = "已取消"
    db.commit()
    return _task_out(task)


@router.get("")
def list_reviews(
    db: Session = Depends(get_db),
    repo_id: int | None = None,
    task_id: int | None = None,
    limit: int = 50,
) -> list[dict]:
    query = select(CodeReview).order_by(CodeReview.created_at.desc()).limit(limit)
    if repo_id:
        query = query.where(CodeReview.repo_id == repo_id)
    if task_id:
        query = query.where(CodeReview.task_id == task_id)
    reviews = db.execute(query).scalars().all()
    names = _repo_names(db)
    return [_review_out(review, names.get(review.repo_id, "")) for review in reviews]


@router.get("/{review_id}")
def get_review(review_id: int, db: Session = Depends(get_db)) -> dict:
    review = db.get(CodeReview, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="审查记录不存在")
    repo = db.get(Repo, review.repo_id)
    return _review_out(review, repo.name if repo else "")


@router.post("/{review_id}/issues")
async def push_issues(review_id: int, db: Session = Depends(get_db)) -> dict:
    review = db.get(CodeReview, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="审查记录不存在")
    repo = db.get(Repo, review.repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="仓库不存在")
    try:
        return await push_findings(db, repo, review)
    except PlatformError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/findings/{finding_id}/ignore")
def ignore_finding(finding_id: int, db: Session = Depends(get_db)) -> dict:
    finding = db.get(ReviewFinding, finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="问题不存在")
    finding.status = "ignored"
    db.commit()
    return {"ok": True}


@router.delete("/{review_id}")
def delete_review(review_id: int, db: Session = Depends(get_db)) -> dict:
    review = db.get(CodeReview, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="审查记录不存在")
    db.delete(review)
    db.commit()
    return {"ok": True}