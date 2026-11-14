from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.services.monitor import (
    _join,
    _normalize_base,
    probe_health_paths,
    send_wechat,
)


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.path == "/health":
            payload = b'{"status":"UP"}'
            self.send_response(200)
        elif self.path == "/api/status":
            payload = b'ok'
            self.send_response(200)
        else:
            payload = b'{"status":"UP"}'
            self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class _WebhookHandler(BaseHTTPRequestHandler):
    received: list = []

    def log_message(self, *_args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        type(self).received.append(body)
        payload = json.dumps({"errcode": 0, "errmsg": "ok"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@pytest.fixture()
def service():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[0], server.server_address[1]
    yield f"http://{host}:{port}"
    server.shutdown()
    server.server_close()


@pytest.fixture()
def webhook():
    _WebhookHandler.received = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _WebhookHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[0], server.server_address[1]
    yield f"http://{host}:{port}/webhook"
    server.shutdown()
    server.server_close()


def test_normalize_base_adds_scheme_and_strips_slash():
    assert _normalize_base("10.0.0.1:8080") == "http://10.0.0.1:8080"
    assert _normalize_base("http://a.com/") == "http://a.com"


def test_join_keeps_path():
    assert _join("http://a.com", "/health") == "http://a.com/health"
    assert _join("http://a.com", "/") == "http://a.com/"


@pytest.mark.asyncio
async def test_probe_finds_available_paths(service):
    result = await probe_health_paths(service, timeout=5, use_llm=False)
    paths = {item["path"] for item in result["available"]}
    assert "/health" in paths
    assert "/api/status" in paths


@pytest.mark.asyncio
async def test_probe_rejects_invalid_url():
    with pytest.raises(ValueError):
        await probe_health_paths("not a url", use_llm=False)


@pytest.mark.asyncio
async def test_send_wechat_posts_text_message(webhook):
    ok, reason = await send_wechat(webhook, "测试告警")
    assert ok is True
    assert reason == ""
    body = _WebhookHandler.received[0]
    assert body["msgtype"] == "text"
    assert body["text"]["content"] == "测试告警"


@pytest.mark.asyncio
async def test_send_wechat_without_webhook():
    ok, reason = await send_wechat("", "x")
    assert ok is False
    assert "webhook" in reason


@pytest.mark.asyncio
async def test_check_updates_monitor_and_alerts_on_state_change(service, webhook):
    """状态由正常转为异常时推送企业微信，恢复时再推一次。"""
    from sqlalchemy import delete

    from app.database import SessionLocal
    from app.models import Monitor, MonitorCheck
    from app.services.config_store import save_wechat_webhook
    from app.services.monitor import perform_check

    db = SessionLocal()
    try:
        save_wechat_webhook(db, webhook)
        monitor = Monitor(
            name="测试服务",
            url=service,
            health_path="/health",
            expect_status=200,
            interval_minutes=5,
            timeout=5,
            enabled=True,
            alert_enabled=True,
        )
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        first = await perform_check(db, monitor)
        assert first["status"] == "ok"
        assert first["error"] == ""
        assert monitor.fail_count == 0
        assert monitor.total_checks == 1
        # 首次检查没有前序状态，不触发告警
        assert _WebhookHandler.received == []

        monitor.last_status = "fail"
        monitor.fail_count = 1
        db.commit()
        second = await perform_check(db, monitor)
        assert second["status"] == "ok"
        # 状态由 fail 变为 ok，触发恢复通知
        assert len(_WebhookHandler.received) == 1
        assert "服务恢复" in _WebhookHandler.received[0]["text"]["content"]

        history = db.query(MonitorCheck).filter(MonitorCheck.monitor_id == monitor.id).count()
        assert history == 2

        db.execute(delete(MonitorCheck).where(MonitorCheck.monitor_id == monitor.id))
        db.delete(monitor)
        db.commit()
    finally:
        db.close()


@pytest.fixture()
def MonitorCheckRow():
    from app.models import MonitorCheck

    return MonitorCheck