from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.services.gitplatform import PlatformError, detect_platform


class _Handler(BaseHTTPRequestHandler):
    gitea_version = "1.19.0"
    commits_status = 200
    commits_body: list = []

    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.path == "/api/v1/version":
            payload = json.dumps({"version": self.gitea_version}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if "/api/v1/repos/" in self.path and self.path.endswith("/commits"):
            if type(self).commits_status == 404:
                payload = json.dumps({"message": "Not Found"}).encode()
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            payload = json.dumps(type(self).commits_body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()


@pytest.fixture()
def fake_gitea():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[0], server.server_address[1]
    yield f"http://{host}:{port}"
    server.shutdown()
    server.server_close()


@pytest.mark.asyncio
async def test_detect_platform_recognizes_gitea(fake_gitea):
    assert await detect_platform(fake_gitea) == "gitea"


@pytest.mark.asyncio
async def test_gitea_missing_repo_raises_readable_error(fake_gitea):
    from app.services.gitplatform import GiteaClient

    _Handler.commits_status = 404
    client = GiteaClient(fake_gitea, "token")
    with pytest.raises(PlatformError) as exc:
        await client.list_commits("owner", "missing")
    message = str(exc.value)
    assert "找不到该仓库" in message
    assert "令牌无权访问" in message


@pytest.mark.asyncio
async def test_gitee_client_on_gitea_server_reports_platform_mismatch(fake_gitea):
    from app.services.gitplatform import GiteeClient

    client = GiteeClient(fake_gitea, "token")
    with pytest.raises(PlatformError) as exc:
        await client.list_commits("owner", "repo")
    assert "不是 Gitee 服务" in str(exc.value)


class _GiteeHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        # Gitee 的提交详情：/commits/{sha}，包含 files 与 patch
        if "/commits/" in path:
            payload = json.dumps(
                {
                    "sha": path.rsplit("/", 1)[-1],
                    "stats": {"total": 1},
                    "files": [
                        {
                            "filename": "a.py",
                            "status": "modified",
                            "additions": 3,
                            "deletions": 1,
                            "patch": "@@ -1 +1 @@\n-old\n+new",
                        }
                    ],
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if path.endswith("/commits"):
            payload = json.dumps(
                [
                    {
                        "sha": "abc123",
                        "html_url": "https://gitee.com/demo/repo/commit/abc123",
                        "commit": {
                            "message": "feat: 新增访客登记",
                            "author": {
                                "name": "张三",
                                "email": "zhangsan@example.com",
                                "date": "2026-11-10T08:00:00+08:00",
                            },
                        },
                        "author": {"login": "zhangsan"},
                        "stats": {"total": 1},
                    }
                ]
            ).encode()
        elif path.endswith("/files"):
            payload = json.dumps(
                [{"filename": "a.py", "additions": 3, "deletions": 1, "status": "modified"}]
            ).encode()
        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@pytest.fixture()
def fake_gitee():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _GiteeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[0], server.server_address[1]
    yield f"http://{host}:{port}"
    server.shutdown()
    server.server_close()


@pytest.mark.asyncio
async def test_gitee_list_commits_fetches_files_before_client_closed(fake_gitee):
    """文件明细必须在 AsyncClient 关闭前拉取，否则会报 client has been closed。"""
    from app.services.gitplatform import GiteeClient

    client = GiteeClient(fake_gitee, "token")
    commits = await client.list_commits("demo", "repo")
    assert len(commits) == 1
    assert commits[0].sha == "abc123"
    assert commits[0].files[0]["filename"] == "a.py"
    assert commits[0].changed_files == 1
    assert commits[0].additions == 3
