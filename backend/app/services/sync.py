from __future__ import annotations

import hashlib
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Commit, Repo, RepoAuthor
from ..security import decrypt
from ..timeutil import now_local
from .config_store import get_author_filter
from .gitplatform import build_client

MAX_COMMITS_PER_REPO = 5000
OVERLAP_HOURS = 24


DEFAULT_EXCLUDED_PREFIXES = ("merge ", "merge:", "revert ", "revert:", "merge branch")


def _keywords(value: str) -> list[str]:
    return [item.strip() for item in (value or "").replace("，", ",").split(",") if item.strip()]


def _matches(message: str, include: str, exclude: str) -> bool:
    text = (message or "").lower()
    if text.startswith(DEFAULT_EXCLUDED_PREFIXES):
        return False
    inc = _keywords(include)
    exc = _keywords(exclude)
    if inc and not any(k.lower() in text for k in inc):
        return False
    if exc and any(k.lower() in text for k in exc):
        return False
    return True


def _author_matches(author_name: str, author_email: str, author_login: str, identifiers: list[str]) -> bool:
    """提交作者是否属于「我」。标识与姓名、登录名、邮箱或邮箱前缀精确匹配。"""
    if not identifiers:
        return True
    fields = [author_name or "", author_login or "", author_email or ""]
    email_local = (author_email or "").split("@")[0]
    if email_local:
        fields.append(email_local)
    normalized = [value.strip().lower() for value in fields if value and value.strip()]
    for identifier in identifiers:
        target = identifier.strip().lower()
        if not target:
            continue
        if target in normalized:
            return True
    return False


def _identity(name: str, email: str, login: str) -> str:
    """作者身份指纹。"""
    raw = f"{(name or '').strip()}|{(email or '').strip()}|{(login or '').strip()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _record_authors(db: Session, repo: Repo, commits: list) -> int:
    """记录本次同步见过的全部作者，包括不属于「我」的。

    候选列表靠这张表维持，否则只能看到已入库的提交，
    而已入库的提交又是按标识过滤过的——候选会永远缺少外部作者。
    """
    counter: dict[str, tuple[str, str, str]] = {}
    tally: dict[str, int] = {}
    for item in commits:
        name = (item.author_name or "").strip()
        email = (item.author_email or "").strip()
        login = (item.author_login or "").strip()
        if not (name or email or login):
            continue
        key = _identity(name, email, login)
        counter[key] = (name, email, login)
        tally[key] = tally.get(key, 0) + 1
    if not counter:
        return 0

    existing = {
        row.identity: row
        for row in db.execute(select(RepoAuthor).where(RepoAuthor.repo_id == repo.id)).scalars().all()
    }
    stamp = now_local()
    for key, (name, email, login) in counter.items():
        row = existing.get(key)
        if row is None:
            db.add(
                RepoAuthor(
                    repo_id=repo.id,
                    identity=key,
                    author_name=name,
                    author_email=email,
                    author_login=login,
                    commit_count=tally.get(key, 1),
                    last_seen_at=stamp,
                )
            )
        else:
            row.author_name = name or row.author_name
            row.author_email = email or row.author_email
            row.author_login = login or row.author_login
            row.commit_count = tally.get(key, row.commit_count)
            row.last_seen_at = stamp
    db.commit()
    return len(counter)


def _prune_other_commits(db: Session, repo: Repo, identifiers: list[str]) -> int:
    """清理该仓库中不属于我的历史提交。"""
    if not identifiers:
        return 0
    rows = db.execute(select(Commit).where(Commit.repo_id == repo.id)).scalars().all()
    removed = 0
    for commit in rows:
        if not _author_matches(commit.author_name, commit.author_email, commit.author_login, identifiers):
            db.delete(commit)
            removed += 1
    if removed:
        db.commit()
    return removed


def _mark_failed(db: Session, repo: Repo, error: Exception) -> None:
    """记录失败原因。last_sync_at 保持为上次成功同步的时间，
    否则下次重试只会回看 24 小时，漏掉历史提交。"""
    repo.last_sync_status = "failed"
    repo.last_sync_message = str(error)[:500]
    db.commit()


def reset_sync_cursor(db: Session) -> int:
    """清空同步游标，下次同步会重新扫完整历史。

    「我的作者标识」变化时需要这一步：否则新选的人在旧提交里的记录不会被补回。
    """
    repos = db.execute(select(Repo).where(Repo.enabled.is_(True))).scalars().all()
    for repo in repos:
        repo.last_sync_at = None
    db.commit()
    return len(repos)


async def sync_repo(db: Session, repo: Repo, max_pages: int | None = None) -> dict:
    token = decrypt(repo.token_enc)
    client = build_client(repo.platform, repo.base_url, token, settings.request_timeout)
    since = None
    if repo.last_sync_at:
        since = repo.last_sync_at - timedelta(hours=OVERLAP_HOURS)

    pages = max_pages or settings.max_pages_per_sync
    try:
        fetched = await client.list_commits(repo.owner, repo.repo, since=since, max_pages=pages)
    except Exception as exc:
        _mark_failed(db, repo, exc)
        raise

    _record_authors(db, repo, fetched)

    identifiers = get_author_filter(db)
    existing = {sha for (sha,) in db.execute(select(Commit.sha).where(Commit.repo_id == repo.id)).all()}
    created = 0
    skipped_other = 0
    for item in fetched:
        if item.sha in existing:
            continue
        if not _matches(item.message, repo.include_keywords, repo.exclude_keywords):
            continue
        if not _author_matches(item.author_name, item.author_email, item.author_login, identifiers):
            skipped_other += 1
            continue
        db.add(
            Commit(
                repo_id=repo.id,
                sha=item.sha,
                short_sha=item.sha[:8],
                message=item.message,
                author_name=item.author_name,
                author_email=item.author_email,
                author_login=item.author_login,
                url=item.url,
                additions=item.additions,
                deletions=item.deletions,
                changed_files=item.changed_files,
                files_json=item.files or None,
                committed_at=item.committed_at or now_local(),
            )
        )
        created += 1
    db.commit()

    pruned = _prune_other_commits(db, repo, identifiers)
    total = db.execute(select(func.count()).select_from(Commit).where(Commit.repo_id == repo.id)).scalar_one()
    if total and total > MAX_COMMITS_PER_REPO:
        cutoff = db.execute(
            select(Commit.id).where(Commit.repo_id == repo.id).order_by(Commit.committed_at.desc()).offset(MAX_COMMITS_PER_REPO)
        ).scalars().first()
        if cutoff:
            db.execute(delete(Commit).where(Commit.repo_id == repo.id, Commit.id < cutoff))
            db.commit()

    repo.last_sync_at = now_local()
    repo.last_sync_status = "success"
    parts = [f"新增 {created} 条"]
    if skipped_other:
        parts.append(f"跳过他人提交 {skipped_other} 条")
    if pruned:
        parts.append(f"清理他人提交 {pruned} 条")
    repo.last_sync_message = "，".join(parts)
    db.commit()
    return {
        "created": created,
        "fetched": len(fetched),
        "skipped_other": skipped_other,
        "pruned_other": pruned,
        "total": int(total or 0),
    }


async def sync_all(db: Session, max_pages: int | None = None) -> dict:
    repos = db.execute(select(Repo).where(Repo.enabled.is_(True))).scalars().all()
    results = []
    for repo in repos:
        try:
            outcome = await sync_repo(db, repo, max_pages=max_pages)
            results.append({"repo_id": repo.id, "name": repo.name, "ok": True, **outcome})
        except Exception as exc:  # noqa: BLE001 - 单个仓库失败不影响其余仓库
            results.append({"repo_id": repo.id, "name": repo.name, "ok": False, "error": str(exc)[:500]})
    return {"total": len(results), "results": results}