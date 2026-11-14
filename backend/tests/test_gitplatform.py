from __future__ import annotations

from app.services.gitplatform import _parse_commit, build_client


def test_parse_gitea_payload():
    raw = {
        "sha": "abc123",
        "html_url": "https://gitea.com/demo/repo/commit/abc123",
        "commit": {
            "message": "feat: 新增功能\n\n详细说明",
            "author": {"name": "张伟", "email": "dev@example.com", "date": "2026-11-10T03:04:05Z"},
        },
        "author": {"login": "zhangwei"},
        "stats": {"additions": 12, "deletions": 4, "total": 3},
        "files": [{"filename": "a.py"}],
    }
    item = _parse_commit(raw)
    assert item.sha == "abc123"
    assert item.message.startswith("feat: 新增功能")
    assert item.author_name == "张伟"
    assert item.author_login == "zhangwei"
    assert item.additions == 12
    assert item.deletions == 4
    assert item.changed_files == 3
    assert item.committed_at is not None
    assert item.committed_at.hour == 11


def test_parse_gitee_payload_with_total_only_stats():
    raw = {
        "sha": "def456",
        "html_url": "https://gitee.com/demo/repo/commit/def456",
        "commit": {
            "message": "fix: 修复分页",
            "author": {"name": "李娜", "email": "li@example.com", "date": "2026-11-11T08:00:00+08:00"},
        },
        "author": {"login": "lina"},
        "stats": {"total": 2},
    }
    item = _parse_commit(raw)
    assert item.sha == "def456"
    assert item.author_login == "lina"
    assert item.changed_files == 2
    assert item.committed_at.hour == 8


def test_build_client_selects_platform():
    assert build_client("gitea", "", "").base_url == "https://gitea.com"
    assert build_client("gitee", "https://gitee.com/", "").base_url == "https://gitee.com"
    assert build_client("gitea", "https://git.corp.cn/", "").base_url == "https://git.corp.cn"