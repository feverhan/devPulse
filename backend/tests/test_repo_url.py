from __future__ import annotations

from app.services.repo_url import parse_repo_url


def test_parse_https_gitee_url():
    result = parse_repo_url("https://gitee.com/jszthl/ztt-vistoraccesssystem")
    assert result["ok"] is True
    assert result["platform"] == "gitee"
    assert result["owner"] == "jszthl"
    assert result["repo"] == "ztt-vistoraccesssystem"
    assert result["base_url"] == "https://gitee.com"


def test_parse_strips_git_suffix():
    result = parse_repo_url("https://gitee.com/jszthl/repo.git")
    assert result["repo"] == "repo"
    assert result["base_url"] == "https://gitee.com"


def test_parse_scp_style_url():
    result = parse_repo_url("git@gitee.com:jszthl/repo.git")
    assert result["platform"] == "gitee"
    assert result["owner"] == "jszthl"
    assert result["repo"] == "repo"
    assert result["base_url"] == "https://gitee.com"


def test_parse_self_hosted_gitea_with_port():
    result = parse_repo_url("http://10.88.192.10:3000/root/ntms")
    assert result["platform"] == "gitea"
    assert result["owner"] == "root"
    assert result["repo"] == "ntms"
    assert result["base_url"] == "http://10.88.192.10:3000"


def test_parse_scp_style_with_port():
    result = parse_repo_url("git@10.88.192.10:3000/root/ntms.git")
    assert result["base_url"] == "https://10.88.192.10:3000"
    assert result["owner"] == "root"
    assert result["repo"] == "ntms"


def test_parse_keeps_sub_path_prefix():
    result = parse_repo_url("https://example.com/gitea/root/ntms")
    assert result["base_url"] == "https://example.com/gitea"
    assert result["owner"] == "root"
    assert result["repo"] == "ntms"


def test_parse_host_without_scheme():
    result = parse_repo_url("gitee.com/jszthl/repo")
    assert result["platform"] == "gitee"
    assert result["base_url"] == "https://gitee.com"


def test_parse_rejects_incomplete_url():
    assert parse_repo_url("")["ok"] is False
    assert parse_repo_url("https://gitee.com/jszthl")["ok"] is False
    assert parse_repo_url("随便写点什么")["ok"] is False


def test_parse_endpoint_returns_fields(client):
    resp = client.post("/api/repos/parse", json={"url": "https://gitee.com/jszthl/repo"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["platform"] == "gitee"
    assert data["owner"] == "jszthl"
    assert data["repo"] == "repo"
    assert data["base_url"] == "https://gitee.com"


def test_parse_endpoint_reports_bad_url(client):
    resp = client.post("/api/repos/parse", json={"url": "不是地址"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is False


def test_create_repo_fills_fields_from_url(client):
    """只给仓库地址也能建，服务端负责解析。"""
    resp = client.post(
        "/api/repos",
        json={
            "name": "微服务组织",
            "repo_url": "https://gitee.com/jszthl/asun-micro-svc-org-ztt.git",
            "token": "",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["owner"] == "jszthl"
    assert data["repo"] == "asun-micro-svc-org-ztt"
    assert data["base_url"] == "https://gitee.com"
    assert data["platform"] == "gitee"

    client.delete(f"/api/repos/{data['id']}")


def test_create_repo_without_any_address_is_rejected(client):
    resp = client.post("/api/repos", json={"name": "缺地址", "repo_url": "", "token": ""})
    assert resp.status_code == 400
