from __future__ import annotations

import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal
from ..models import CodeReview, Commit, Repo, ReviewFinding, ReviewTask
from ..security import decrypt
from ..timeutil import now_local
from .config_store import get_llm_config
from .gitplatform import PlatformError, build_client
from .llm import LLMError, chat

SEVERITIES = ("high", "medium", "low")
SEVERITY_LABEL = {"high": "严重", "medium": "一般", "low": "轻微"}
SEVERITY_ALIAS = {
    "critical": "high",
    "blocker": "high",
    "error": "high",
    "严重": "high",
    "warning": "medium",
    "warn": "medium",
    "一般": "medium",
    "minor": "low",
    "info": "low",
    "提示": "low",
    "轻微": "low",
}

MAX_DIFF_CHARS = 12000
MAX_PATCH_FILES = 8
MAX_PATCH_CHARS = 4000
REVIEW_LLM_TIMEOUT = 600.0

REVIEW_SYSTEM_PROMPT = (
    "你是一名资深代码审查专家。请针对给出的代码变更，找出其中真实存在的质量问题。\n"
    "审查原则：\n"
    "1. 只报告客观可验证的缺陷：逻辑错误、异常未处理、资源泄漏、并发问题、安全漏洞、"
    "明显的性能陷阱、边界条件遗漏。\n"
    "2. 不报告代码风格、命名、注释、格式、缩进、import 顺序等主观偏好。\n"
    "3. 不为了凑数而报告；不确定的可以不报。\n"
    "4. 每条问题必须指明具体文件与行号。\n"
    "输出格式：只输出一个 JSON 数组，不要输出任何其他文字，也不要用 Markdown 代码块包裹。\n"
    "数组中每个元素形如：\n"
    '{"file": "相对路径", "line": 12, "severity": "high|medium|low", '
    '"category": "异常处理|安全|性能|并发|逻辑错误|资源泄漏", '
    '"title": "一句话概括问题", "detail": "说明成因与影响，2 到 3 句"}\n'
    "没有问题时输出 []。"
)


def _first_bracket(text: str) -> str | None:
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


def parse_findings(raw: str) -> list[dict]:
    """从模型输出中解析问题列表，容忍代码块包裹等常见格式。"""
    if not raw:
        return []
    match = re.search(r"```(?:json)?\s*(.*?)```", raw, re.S)
    candidate = (match.group(1) if match else raw).strip()
    data = None
    for attempt in (candidate, _first_bracket(candidate)):
        if not attempt:
            continue
        try:
            data = json.loads(attempt)
            break
        except json.JSONDecodeError:
            continue
    if isinstance(data, dict):
        data = data.get("findings") or data.get("issues") or []
    if not isinstance(data, list):
        return []
    results: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_finding(item)
        if normalized:
            results.append(normalized)
    return results


def _normalize_finding(item: dict) -> dict | None:
    title = str(item.get("title") or item.get("summary") or "").strip()
    if not title:
        return None
    severity = str(item.get("severity") or item.get("level") or "medium").strip().lower()
    if severity not in SEVERITIES:
        severity = SEVERITY_ALIAS.get(severity, "medium")
    try:
        line = int(item.get("line") or item.get("line_number") or 0)
    except (TypeError, ValueError):
        line = 0
    return {
        "file": str(item.get("file") or item.get("path") or item.get("filename") or "").strip()[:500],
        "line": max(0, line),
        "severity": severity,
        "category": str(item.get("category") or item.get("type") or "").strip()[:60],
        "title": title[:300],
        "detail": str(item.get("detail") or item.get("description") or item.get("body") or "").strip()[:4000],
    }


async def gather_material(client, repo: Repo, commit: Commit) -> str:
    """取审查素材：优先 diff，其次提交详情里的 patch，最后退回文件原文。"""
    diff = await client.get_commit_diff(repo.owner, repo.repo, commit.sha)
    if diff and diff.strip():
        return diff[:MAX_DIFF_CHARS]

    files = commit.files_json or []
    if not files:
        files = await client.get_commit_files(repo.owner, repo.repo, commit.sha)

    patches: list[str] = []
    for item in files[:MAX_PATCH_FILES]:
        patch = item.get("patch")
        if not patch:
            continue
        name = item.get("filename") or item.get("path") or ""
        body = str(patch)[:MAX_PATCH_CHARS]
        patches.append(f"--- {name} ---\n{body}")
    if patches:
        return "\n\n".join(patches)[:MAX_DIFF_CHARS]

    return await client.get_file_contents(repo.owner, repo.repo, commit.sha, files)


async def review_commit(
    db: Session,
    repo: Repo,
    commit: Commit,
    client,
    config,
    task_id: int | None = None,
) -> CodeReview:
    review = CodeReview(
        task_id=task_id,
        repo_id=repo.id,
        commit_sha=commit.sha,
        commit_subject=(commit.message or "").splitlines()[0] if commit.message else "",
        commit_url=commit.url or "",
        author_name=commit.author_name or "",
        status="completed",
        model=config.model,
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    try:
        material = await gather_material(client, repo, commit)
    except PlatformError as exc:
        review.status = "failed"
        review.message = str(exc)[:500]
        db.commit()
        return review

    if not material.strip():
        review.status = "skipped"
        review.message = "未取到变更内容"
        db.commit()
        return review

    user = (
        f"仓库：{repo.owner}/{repo.repo}\n"
        f"提交：{commit.sha}\n"
        f"提交说明：{review.commit_subject}\n\n"
        f"代码变更：\n{material}"
    )
    try:
        raw = await chat(
            [{"role": "system", "content": REVIEW_SYSTEM_PROMPT}, {"role": "user", "content": user}],
            config,
            timeout=REVIEW_LLM_TIMEOUT,
        )
    except LLMError as exc:
        review.status = "failed"
        review.message = str(exc)[:500]
        db.commit()
        return review

    findings = parse_findings(raw)
    for item in findings:
        db.add(
            ReviewFinding(
                review_id=review.id,
                status="pending",
                file_path=item["file"],
                line=item["line"],
                severity=item["severity"],
                category=item["category"],
                title=item["title"],
                detail=item["detail"],
            )
        )
    review.finding_count = len(findings)
    review.message = "" if findings else "未发现明显质量问题"
    db.commit()
    db.refresh(review)
    return review


def pick_commits(db: Session, repo: Repo, limit: int, only_new: bool) -> list[Commit]:
    reviewed = {
        sha
        for (sha,) in db.execute(
            select(CodeReview.commit_sha).where(CodeReview.repo_id == repo.id)
        ).all()
    }
    candidates = db.execute(
        select(Commit).where(Commit.repo_id == repo.id).order_by(Commit.committed_at.desc()).limit(limit * 3)
    ).scalars().all()
    if only_new:
        return [item for item in candidates if item.sha not in reviewed][:limit]
    return candidates[:limit]


async def run_task(task_id: int) -> None:
    """后台执行一次代码审查任务。"""
    db = SessionLocal()
    try:
        task = db.get(ReviewTask, task_id)
        if not task:
            return
        task.status = "running"
        task.updated_at = now_local()
        db.commit()

        repo = db.get(Repo, task.repo_id)
        if not repo:
            task.status = "failed"
            task.message = "仓库不存在"
            task.finished_at = now_local()
            db.commit()
            return

        config = get_llm_config(db)
        if not config.ready:
            task.status = "failed"
            task.message = "未配置大模型"
            task.finished_at = now_local()
            db.commit()
            return

        task.model = config.model
        db.commit()

        client = build_client(repo.platform, repo.base_url, decrypt(repo.token_enc), settings.request_timeout)
        commits = pick_commits(db, repo, task.limit, task.only_new)
        task.total = len(commits)
        db.commit()

        for commit in commits:
            db.refresh(task)
            if task.status == "cancelled":
                break
            review = await review_commit(db, repo, commit, client, config, task_id=task.id)
            task.processed += 1
            task.finding_count += review.finding_count
            task.updated_at = now_local()
            db.commit()

        db.refresh(task)
        if task.status == "cancelled":
            task.message = "已取消"
        else:
            task.status = "done"
            task.message = f"已审查 {task.processed} 个提交，发现 {task.finding_count} 个问题"
        task.finished_at = now_local()
        db.commit()
    except Exception as exc:  # noqa: BLE001 - 任务失败要留痕
        db.rollback()
        task = db.get(ReviewTask, task_id)
        if task:
            task.status = "failed"
            task.message = _short_error(exc)
            task.finished_at = now_local()
            db.commit()
    finally:
        db.close()


def _short_error(exc: Exception, limit: int = 160) -> str:
    text = " ".join(str(exc).split())
    return text[:limit]


def build_issue_body(finding: ReviewFinding, review: CodeReview) -> str:
    lines = ["## 问题描述", "", finding.detail or finding.title, "", "## 位置", ""]
    if finding.file_path:
        lines.append(f"- 文件：`{finding.file_path}`")
    if finding.line:
        lines.append(f"- 行号：{finding.line}")
    if finding.category:
        lines.append(f"- 类别：{finding.category}")
    lines.extend(["", "## 来源", "", f"- 提交：`{review.commit_sha}`"])
    if review.commit_subject:
        lines.append(f"- 提交说明：{review.commit_subject}")
    if review.commit_url:
        lines.append(f"- 链接：{review.commit_url}")
    lines.extend(["", "---", "由工时周报自动代码审查生成。"])
    return "\n".join(lines)


async def push_findings(db: Session, repo: Repo, review: CodeReview) -> dict:
    client = build_client(repo.platform, repo.base_url, decrypt(repo.token_enc), settings.request_timeout)
    created = 0
    failed = 0
    for finding in review.findings:
        if finding.status != "pending":
            continue
        title = f"[{SEVERITY_LABEL.get(finding.severity, '一般')}] {finding.title}"
        try:
            result = await client.create_issue(
                repo.owner, repo.repo, title, build_issue_body(finding, review)
            )
        except PlatformError as exc:
            finding.status = "failed"
            finding.detail = f"{finding.detail}\n\n推送失败：{exc}".strip()
            failed += 1
            continue
        finding.issue_number = result.get("number")
        finding.issue_url = result.get("url") or ""
        finding.status = "created"
        created += 1
    db.commit()
    db.refresh(review)
    return {"created": created, "failed": failed, "review_id": review.id}