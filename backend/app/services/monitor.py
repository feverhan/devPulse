from __future__ import annotations

import asyncio
import re
from datetime import timedelta
from time import perf_counter
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Monitor, MonitorCheck
from ..timeutil import now_local
from .config_store import get_llm_config, get_wechat_webhook
from .llm import LLMError, chat

# 常见健康检查路径候选
CANDIDATE_PATHS: list[str] = [
    "/health",
    "/healthz",
    "/healthcheck",
    "/health-check",
    "/readyz",
    "/livez",
    "/ready",
    "/live",
    "/alive",
    "/status",
    "/ping",
    "/up",
    "/api/health",
    "/api/healthz",
    "/api/status",
    "/api/ping",
    "/api/version",
    "/v1/health",
    "/v2/health",
    "/admin/health",
    "/system/health",
    "/actuator/health",
    "/actuator/info",
    "/actuator",
    "/version",
]

PATH_PROMPT = (
    "你是一名熟悉常见 Web 框架的运维工程师。下面是一个服务的首页内容片段。\n"
    "请根据框架特征（Spring Boot / Django / Express / Gin / FastAPI / ASP.NET 等）"
    "推测该服务可能使用的健康检查路径。\n"
    "只输出 3 到 6 个候选路径，每行一个，必须以 / 开头，不要输出任何解释。\n"
    "常见形式如 /actuator/health、/api/health、/healthz、/status、/ping。\n"
    "片段：\n"
)


def _normalize_base(url: str) -> str:
    text = (url or "").strip()
    if not text:
        return ""
    if "://" not in text:
        text = f"http://{text}"
    return text.rstrip("/")


def _join(base: str, path: str) -> str:
    if not path or path == "/":
        return base + "/"
    return f"{base}/{path.lstrip('/')}"


def _is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False
    if any(char.isspace() for char in parsed.netloc):
        return False
    host = parsed.hostname or ""
    return bool(host) and "." in host or host in ("localhost",)


async def _probe_one(client: httpx.AsyncClient, base: str, path: str) -> dict:
    url = _join(base, path)
    started = perf_counter()
    try:
        resp = await client.get(url)
    except Exception as exc:  # noqa: BLE001 - 探测阶段忽略单点失败
        return {
            "path": path,
            "url": url,
            "ok": False,
            "status": None,
            "latency_ms": int((perf_counter() - started) * 1000),
            "error": str(exc)[:160],
        }
    return {
        "path": path,
        "url": url,
        "ok": resp.status_code < 400,
        "status": resp.status_code,
        "latency_ms": int((perf_counter() - started) * 1000),
        "error": "" if resp.status_code < 400 else f"HTTP {resp.status_code}",
    }


async def suggest_paths(base: str, timeout: float = 8.0) -> list[str]:
    """让大模型根据首页内容推测健康检查路径。"""
    db = SessionLocal()
    try:
        config = get_llm_config(db)
    finally:
        db.close()
    if not config.ready:
        return []
    snippet = ""
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False, follow_redirects=True) as client:
            resp = await client.get(base + "/")
            snippet = resp.text[:1500]
    except Exception:  # noqa: BLE001 - 抓不到首页就只用静态候选
        return []
    if not snippet.strip():
        return []
    try:
        raw = await chat(
            [
                {"role": "system", "content": PATH_PROMPT},
                {"role": "user", "content": snippet},
            ],
            config,
            timeout=60.0,
        )
    except LLMError:
        return []
    paths: list[str] = []
    for line in raw.splitlines():
        item = line.strip().strip("`\"' ")
        if not item.startswith("/"):
            continue
        item = item.split()[0]
        if item and item not in paths and len(item) < 120:
            paths.append(item)
    return paths[:6]


async def probe_health_paths(
    base_url: str,
    timeout: float = 8.0,
    use_llm: bool = True,
    extra_paths: list[str] | None = None,
) -> dict:
    """探测可用的健康检查路径：静态候选 + 大模型推测，并发试探后按可用性排序。"""
    base = _normalize_base(base_url)
    if not _is_valid_url(base):
        raise ValueError("地址无效，需形如 http://host:port 或 https://domain")

    candidates: list[str] = []
    for path in list(extra_paths or []) + CANDIDATE_PATHS:
        if path and path not in candidates:
            candidates.append(path)

    suggested: list[str] = []
    if use_llm:
        suggested = await suggest_paths(base, timeout=timeout)
        for path in suggested:
            if path not in candidates:
                candidates.insert(0, path)

    async with httpx.AsyncClient(
        timeout=timeout,
        verify=False,
        follow_redirects=True,
        headers={"User-Agent": "worklog-reporter-monitor/1.0"},
    ) as client:
        results = await asyncio.gather(*(_probe_one(client, base, path) for path in candidates))

    results.sort(key=lambda item: (0 if item["ok"] else 1, item["latency_ms"]))
    return {
        "base_url": base,
        "suggested": suggested,
        "results": results,
        "available": [item for item in results if item["ok"]],
    }


async def _request(monitor: Monitor) -> tuple[bool, int, int, str]:
    base = _normalize_base(monitor.url)
    target = _join(base, monitor.health_path or "/")
    started = perf_counter()
    try:
        async with httpx.AsyncClient(
            timeout=monitor.timeout,
            verify=False,
            follow_redirects=True,
            headers={"User-Agent": "worklog-reporter-monitor/1.0"},
        ) as client:
            if monitor.method.upper() == "HEAD":
                resp = await client.head(target)
            else:
                resp = await client.get(target)
        latency = int((perf_counter() - started) * 1000)
        if resp.status_code != monitor.expect_status:
            return False, resp.status_code, latency, f"HTTP {resp.status_code}，期望 {monitor.expect_status}"
        if monitor.keyword and monitor.keyword not in resp.text:
            return False, resp.status_code, latency, f"响应未包含「{monitor.keyword}」"
        return True, resp.status_code, latency, ""
    except Exception as exc:  # noqa: BLE001 - 任何异常都算不可用
        latency = int((perf_counter() - started) * 1000)
        return False, 0, latency, str(exc)[:300]


async def send_wechat(webhook: str, content: str) -> tuple[bool, str]:
    """推送企业微信群机器人消息。"""
    if not webhook:
        return False, "未配置企业微信 webhook"
    payload = {"msgtype": "text", "text": {"content": content}}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(webhook, json=payload)
        if resp.status_code >= 400:
            return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        if data.get("errcode"):
            return False, f"{data.get('errcode')}: {data.get('errmsg')}"
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:200]


async def perform_check(db: Session, monitor: Monitor) -> dict:
    """执行一次检查，写入结果并按状态变化触发告警。"""
    previous = monitor.last_status or ""
    ok, status_code, latency, error = await _request(monitor)
    status = "ok" if ok else "fail"

    monitor.last_status = status
    monitor.last_check_at = now_local()
    monitor.last_latency_ms = latency
    monitor.last_error = error
    monitor.total_checks += 1
    if ok:
        monitor.ok_checks += 1
        monitor.fail_count = 0
    else:
        monitor.fail_count += 1
    db.add(
        MonitorCheck(
            monitor_id=monitor.id,
            status=status,
            status_code=status_code,
            latency_ms=latency,
            error=error,
        )
    )
    db.commit()

    alert_note = ""
    if monitor.alert_enabled and previous and previous != status:
        webhook = get_wechat_webhook(db)
        if webhook:
            stamp = now_local().strftime("%Y-%m-%d %H:%M:%S")
            if status == "fail":
                content = (
                    f"【服务异常】{monitor.name}\n"
                    f"地址：{monitor.url}{monitor.health_path or '/'}\n"
                    f"错误：{error or '未知错误'}\n"
                    f"时间：{stamp}"
                )
            else:
                content = (
                    f"【服务恢复】{monitor.name}\n"
                    f"地址：{monitor.url}{monitor.health_path or '/'}\n"
                    f"响应：{status_code}，耗时 {latency} ms\n"
                    f"时间：{stamp}"
                )
            sent, fail_reason = await send_wechat(webhook, content)
            alert_note = "已通知" if sent else f"通知失败：{fail_reason}"
        else:
            alert_note = "未配置 webhook，未通知"

    return {
        "status": status,
        "status_code": status_code,
        "latency_ms": latency,
        "error": error,
        "alert": alert_note,
    }


async def run_check(monitor_id: int) -> None:
    """后台检查任务入口。"""
    db = SessionLocal()
    try:
        monitor = db.get(Monitor, monitor_id)
        if not monitor or not monitor.enabled:
            return
        await perform_check(db, monitor)
    finally:
        db.close()


def due_monitors(db: Session) -> list[Monitor]:
    """筛出到检查时间的监控目标。"""
    now = now_local()
    monitors = db.execute(select(Monitor).where(Monitor.enabled.is_(True))).scalars().all()
    due: list[Monitor] = []
    for monitor in monitors:
        if monitor.last_check_at is None:
            due.append(monitor)
            continue
        if now - monitor.last_check_at >= timedelta(minutes=max(1, monitor.interval_minutes)):
            due.append(monitor)
    return due