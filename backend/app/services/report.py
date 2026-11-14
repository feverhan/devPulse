from __future__ import annotations

import re
from calendar import monthrange
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Commit, Repo, WorkEntry
from ..timeutil import day_bounds, now_local
from .config_store import get_llm_config
from .llm import LLMError, chat

PERIOD_LABELS = {
    "weekly": "周报",
    "monthly": "月报",
    "quarterly": "季报",
    "yearly": "年报",
    "custom": "工作报告",
}

MAX_COMMIT_LINES = 250
MAX_ITEMS_PER_PROJECT = 12
MAX_FACT_ITEMS_PER_PROJECT = 40

CN_DIGITS = "零一二三四五六七八九"


def cn_number(value: int) -> str:
    if value < 10:
        return CN_DIGITS[value]
    if value < 20:
        return "十" + (CN_DIGITS[value % 10] if value % 10 else "")
    if value < 100:
        return CN_DIGITS[value // 10] + "十" + (CN_DIGITS[value % 10] if value % 10 else "")
    return str(value)


def resolve_period(
    period_type: str,
    reference_date: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[date, date]:
    ref = reference_date or now_local().date()
    if period_type == "weekly":
        start = ref - timedelta(days=ref.weekday())
        end = start + timedelta(days=6)
    elif period_type == "monthly":
        start = ref.replace(day=1)
        end = ref.replace(day=monthrange(ref.year, ref.month)[1])
    elif period_type == "quarterly":
        quarter = (ref.month - 1) // 3
        start = date(ref.year, quarter * 3 + 1, 1)
        last_month = quarter * 3 + 3
        end = date(ref.year, last_month, monthrange(ref.year, last_month)[1])
    elif period_type == "yearly":
        start = date(ref.year, 1, 1)
        end = date(ref.year, 12, 31)
    else:
        start = start_date or ref
        end = end_date or ref
        if end < start:
            start, end = end, start
    return start, end


def default_title(period_type: str, start: date, end: date) -> str:
    label = PERIOD_LABELS.get(period_type, "报告")
    if period_type == "yearly":
        return f"{start.year} 年度报告"
    return f"{start.isoformat()} 至 {end.isoformat()} {label}"


def clean_subject(subject: str) -> str:
    """去掉 feat(xxx): / fix: 之类的提交前缀，只保留事项描述。"""
    text = (subject or "").splitlines()[0] if subject else ""
    text = re.sub(r"^\s*[a-zA-Z]+(\([^)]*\))?\s*[:!]\s*", "", text)
    return text.strip()


def gather_source(
    db: Session,
    start: date,
    end: date,
    include_commits: bool = True,
    include_works: bool = True,
) -> dict:
    commits: list[dict] = []
    works: list[dict] = []
    if include_commits:
        low, high = day_bounds(start, end)
        rows = db.execute(
            select(Commit, Repo)
            .join(Repo, Commit.repo_id == Repo.id)
            .where(Commit.committed_at >= low, Commit.committed_at <= high)
            .order_by(Commit.committed_at.desc())
        ).all()
        for commit, repo in rows:
            project = (repo.project or repo.name or "").strip() or "未分类项目"
            commits.append(
                {
                    "sha": commit.short_sha or commit.sha[:8],
                    "repo": repo.name,
                    "project": project,
                    "date": commit.committed_at.date().isoformat(),
                    "author": commit.author_name or commit.author_login,
                    "subject": (commit.message or "").splitlines()[0] if commit.message else "",
                    "item": clean_subject(commit.message),
                    "additions": commit.additions,
                    "deletions": commit.deletions,
                    "changed_files": commit.changed_files,
                }
            )
    if include_works:
        rows = db.execute(
            select(WorkEntry)
            .where(WorkEntry.work_date >= start, WorkEntry.work_date <= end)
            .order_by(WorkEntry.work_date.desc())
        ).scalars().all()
        for entry in rows:
            project = (entry.project or "").strip() or "未分类项目"
            works.append(
                {
                    "date": entry.work_date.isoformat(),
                    "title": entry.title,
                    "content": entry.content or "",
                    "category": entry.category or "",
                    "project": project,
                    "tags": entry.tags or "",
                    "hours": entry.hours,
                }
            )
    return {"commits": commits, "works": works}


def group_by_project(source: dict) -> list[dict]:
    """按项目分组，组内先放工作记录，再放提交事项。"""
    projects: dict[str, dict] = {}

    def bucket(name: str) -> dict:
        key = name.strip() or "未分类项目"
        return projects.setdefault(key, {"name": key, "works": [], "commits": []})

    for item in source.get("works") or []:
        bucket(item["project"])["works"].append(item)
    for item in source.get("commits") or []:
        bucket(item["project"])["commits"].append(item)

    ordered = list(projects.values())
    for group in ordered:
        group["works"].sort(key=lambda x: (x["date"], x["title"]), reverse=True)
        group["commits"].sort(key=lambda x: x["date"], reverse=True)
    ordered.sort(key=lambda g: (-len(g["works"]), -len(g["commits"]), g["name"]))
    return ordered


def project_items(group: dict, limit: int = MAX_ITEMS_PER_PROJECT) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()

    for work in group["works"]:
        text = work["title"].strip()
        if not text:
            continue
        key = re.sub(r"\s+", "", text)
        if key in seen:
            continue
        seen.add(key)
        items.append(text)

    for commit in group["commits"]:
        text = commit["item"].strip()
        if not text:
            continue
        key = re.sub(r"\s+", "", text)
        if key in seen:
            continue
        seen.add(key)
        items.append(text)
        if len(items) >= limit:
            break

    return items[:limit]


def compute_stats(source: dict) -> dict:
    commits = source.get("commits") or []
    works = source.get("works") or []

    by_repo: dict[str, dict] = {}
    for item in commits:
        bucket = by_repo.setdefault(item["repo"], {"name": item["repo"], "count": 0, "additions": 0, "deletions": 0})
        bucket["count"] += 1
        bucket["additions"] += item.get("additions") or 0
        bucket["deletions"] += item.get("deletions") or 0

    by_category: dict[str, int] = {}
    for item in works:
        key = item.get("category") or "其他"
        by_category[key] = by_category.get(key, 0) + 1

    by_day: dict[str, int] = {}
    for item in commits:
        by_day[item["date"]] = by_day.get(item["date"], 0) + 1

    by_project: dict[str, dict] = {}
    for group in group_by_project(source):
        entry = by_project.setdefault(
            group["name"], {"name": group["name"], "commits": len(group["commits"]), "works": len(group["works"])}
        )
        entry["commits"] += len(group["commits"])
        entry["works"] += len(group["works"])

    hours = sum(float(item.get("hours") or 0) for item in works)
    return {
        "commit_count": len(commits),
        "work_count": len(works),
        "hours": round(hours, 1),
        "additions": sum(item.get("additions") or 0 for item in commits),
        "deletions": sum(item.get("deletions") or 0 for item in commits),
        "changed_files": sum(item.get("changed_files") or 0 for item in commits),
        "repo_count": len(by_repo),
        "project_count": len(by_project),
        "active_days": len(by_day),
        "by_repo": sorted(by_repo.values(), key=lambda x: x["count"], reverse=True),
        "by_project": sorted(by_project.values(), key=lambda x: (x["works"], x["commits"]), reverse=True),
        "by_category": [{"name": k, "count": v} for k, v in sorted(by_category.items(), key=lambda x: x[1], reverse=True)],
        "by_day": [{"date": k, "count": by_day[k]} for k in sorted(by_day)],
    }


def build_facts(source: dict, stats: dict) -> str:
    lines: list[str] = []
    lines.append(f"统计区间：{stats.get('start_date', '')} 至 {stats.get('end_date', '')}")
    lines.append(
        f"数据总量：代码提交 {stats['commit_count']} 次，工作记录 {stats['work_count']} 条，"
        f"登记工时 {stats['hours']} 小时，涉及 {stats['project_count']} 个项目"
    )

    for group in group_by_project(source):
        lines.append("")
        lines.append(f"【项目】{group['name']}")
        for work in group["works"][:MAX_FACT_ITEMS_PER_PROJECT]:
            detail = work["content"].strip().replace("\n", " ")
            suffix = f"：{detail[:160]}" if detail else ""
            lines.append(f"- （工作记录 {work['date']}）{work['title']}{suffix}")
        for commit in group["commits"][:MAX_FACT_ITEMS_PER_PROJECT]:
            text = commit["item"] or commit["subject"]
            if not text:
                continue
            lines.append(f"- （代码提交 {commit['date']}）{text}")
    return "\n".join(lines)


SYSTEM_PROMPT = (
    "你是一名研发团队的汇报撰写人，负责把工作事实整理成周报。"
    "你只能使用给定事实，不得虚构项目、事项或数据。\n"
    "输出必须严格符合以下格式，不得添加任何其他内容：\n"
    "1. 按项目分组，组与组之间空一行。\n"
    "2. 每个项目先输出一行标题，格式为「一、」「二、」「三、」……加项目名，序号使用中文数字。\n"
    "3. 项目标题下面是若干条事项，每条独占一行，以「1.」「2.」「3.」……编号，编号使用阿拉伯数字并紧跟英文句点。\n"
    "4. 事项写成动宾结构的短句，去掉「feat」「fix」等提交前缀，不要出现提交哈希。\n"
    "5. 同一项目下把内容相近的事项合并成一条，不要罗列琐碎改动。\n"
    "6. 不要输出标题行、总结、统计、说明或任何解释性文字。\n"
    "输出示例：\n"
    "一、集团访客系统\n\n"
    "1.企业微信界面调整，默认发起时间各端统一\n\n"
    "二、南通海事短临预警系统\n\n"
    "1.短临预警系统MCP服务开发\n"
    "2.风电场模块打卡业务调整"
)


def build_messages(label: str, start: date, end: date, facts: str, focus: str = "") -> list[dict[str, str]]:
    focus_block = f"\n\n本次重点关注：{focus.strip()}" if focus and focus.strip() else ""
    user = (
        f"请把下列工作事实整理成一份{label}（{start.isoformat()} 至 {end.isoformat()}）。{focus_block}\n\n"
        f"工作事实：\n\n{facts}\n\n请按指定格式输出。"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def fallback_markdown(groups: list[dict]) -> str:
    parts: list[str] = []
    index = 0
    for group in groups:
        items = project_items(group)
        if not items:
            continue
        index += 1
        parts.append(f"{cn_number(index)}、{group['name']}")
        parts.append("")
        for number, text in enumerate(items, start=1):
            parts.append(f"{number}.{text}")
        parts.append("")
    if not parts:
        return "本期无工作记录"
    return "\n".join(parts).rstrip() + "\n"


def build_summary(groups: list[dict]) -> str:
    names = [group["name"] for group in groups if project_items(group)]
    if not names:
        return ""
    if len(names) == 1:
        return f"涉及 {names[0]} 1 个项目"
    return f"涉及 {len(names)} 个项目：{'、'.join(names[:6])}"


async def generate_report(
    db: Session,
    period_type: str,
    start: date,
    end: date,
    title: str = "",
    focus: str = "",
    include_commits: bool = True,
    include_works: bool = True,
    use_llm: bool = True,
) -> dict:
    label = PERIOD_LABELS.get(period_type, "报告")
    source = gather_source(db, start, end, include_commits, include_works)
    stats = compute_stats(source)
    stats["start_date"] = start.isoformat()
    stats["end_date"] = end.isoformat()
    groups = group_by_project(source)
    facts = build_facts(source, stats)

    content = ""
    model_name = ""
    error = ""
    if use_llm:
        config = get_llm_config(db)
        if config.ready:
            try:
                content = await chat(build_messages(label, start, end, facts, focus), config)
                model_name = config.model
            except LLMError as exc:
                error = str(exc)
        else:
            error = "未配置大模型"

    if not content:
        content = fallback_markdown(groups)
        if not model_name:
            model_name = "本地模板"

    return {
        "title": title or default_title(period_type, start, end),
        "period_type": period_type,
        "start_date": start,
        "end_date": end,
        "summary": build_summary(groups),
        "content": content,
        "stats": stats,
        "source": {"facts": facts, "focus": focus, "llm_error": error},
        "model": model_name,
        "status": "published",
    }