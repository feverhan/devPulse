from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.services.review import _normalize_finding, build_issue_body, parse_findings


def test_parse_findings_plain_json_array():
    raw = json.dumps(
        [
            {
                "file": "src/a.py",
                "line": 12,
                "severity": "high",
                "category": "异常处理",
                "title": "未处理异常",
                "detail": "调用可能抛错。",
            }
        ],
        ensure_ascii=False,
    )
    findings = parse_findings(raw)
    assert len(findings) == 1
    assert findings[0]["file"] == "src/a.py"
    assert findings[0]["severity"] == "high"
    assert findings[0]["line"] == 12


def test_parse_findings_with_code_fence():
    raw = '```json\n[{"file": "a.py", "title": "问题一", "severity": "low"}]\n```'
    findings = parse_findings(raw)
    assert len(findings) == 1
    assert findings[0]["title"] == "问题一"


def test_parse_findings_with_wrapper_object():
    raw = json.dumps({"findings": [{"title": "问题", "severity": "medium"}]}, ensure_ascii=False)
    assert len(parse_findings(raw)) == 1


def test_parse_findings_empty_array():
    assert parse_findings("[]") == []
    assert parse_findings("") == []
    assert parse_findings("今天天气不错") == []


def test_normalize_finding_maps_severity_aliases():
    assert _normalize_finding({"title": "x", "severity": "critical"})["severity"] == "high"
    assert _normalize_finding({"title": "x", "severity": "警告"})["severity"] == "medium"
    assert _normalize_finding({"title": "x"})["severity"] == "medium"
    assert _normalize_finding({"title": "x", "line": "abc"})["line"] == 0
    assert _normalize_finding({"detail": "no title"}) is None


def test_build_issue_body_contains_location_and_source():
    class _Finding:
        file_path = "src/a.py"
        line = 12
        category = "安全"
        title = "硬编码密钥"
        detail = "密钥写死在代码里。"

    class _Review:
        commit_sha = "abc1234"
        commit_subject = "feat: 某功能"
        commit_url = "https://example.com/commit/abc1234"

    body = build_issue_body(_Finding(), _Review())
    assert "src/a.py" in body
    assert "12" in body
    assert "硬编码密钥" in body or "密钥写死" in body
    assert "abc1234" in body


class _IssueHandler(BaseHTTPRequestHandler):
    created: list = []

    def log_message(self, *_args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        type(self).created.append({"path": self.path, "body": body})
        payload = json.dumps({"number": 42, "html_url": "https://example.com/issues/42"}).encode()
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@pytest.fixture()
def issue_server():
    _IssueHandler.created = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _IssueHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[0], server.server_address[1]
    yield f"http://{host}:{port}"
    server.shutdown()
    server.server_close()


@pytest.mark.asyncio
async def test_gitea_create_issue(issue_server):
    from app.services.gitplatform import GiteaClient

    client = GiteaClient(issue_server, "token")
    result = await client.create_issue("demo", "repo", "标题", "正文")
    assert result["number"] == 42
    assert result["url"] == "https://example.com/issues/42"
    assert _IssueHandler.created[0]["body"]["title"] == "标题"


@pytest.mark.asyncio
async def test_gitee_create_issue(issue_server):
    from app.services.gitplatform import GiteeClient

    client = GiteeClient(issue_server, "token")
    result = await client.create_issue("demo", "repo", "标题", "正文")
    assert result["number"] == 42
    assert "access_token=token" in _IssueHandler.created[0]["path"]


def test_reviews_list_is_empty_by_default(client):
    assert client.get("/api/reviews").status_code == 200