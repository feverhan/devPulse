from __future__ import annotations

import pytest

from app.services.sync import _author_matches, _keywords, _matches


def test_keywords_split_on_chinese_comma():
    assert _keywords("feat, fix，docs") == ["feat", "fix", "docs"]


def test_matches_with_include_filter():
    assert _matches("feat: 新增接口", "feat,refactor", "")
    assert not _matches("fix: 修复问题", "feat,refactor", "")


def test_matches_with_exclude_filter():
    assert not _matches("Merge branch 'main'", "", "merge")
    assert _matches("feat: 新增接口", "", "merge")


def test_matches_empty_filters_accepts_everything():
    assert _matches("任意提交信息", "", "")


def test_merge_and_revert_commits_are_excluded_by_default():
    assert not _matches("Merge remote-tracking branch 'gitea/master'", "", "")
    assert not _matches("Merge branch 'main' into dev", "", "")
    assert not _matches("Revert \"feat: 某功能\"", "", "")
    assert _matches("feat: 某功能", "", "")

def test_author_matches_empty_filter_accepts_everyone():
    assert _author_matches("张三", "z@x.cn", "zhangsan", [])


def test_author_matches_by_login_name_and_email():
    filters = ["hanqw"]
    assert _author_matches("hanqw", "hanqw@ztt.cn", "hanqw", filters)
    assert _author_matches("韩启文", "hanqw@ztt.cn", "hanqw", filters)
    assert not _author_matches("hjs", "2285563864@qq.com", "hjs", filters)


def test_author_matches_by_email_only():
    filters = ["2285563864@qq.com"]
    assert _author_matches("hjs", "2285563864@qq.com", "", filters)
    assert not _author_matches("hanqw", "hanqw@ztt.cn", "hanqw", filters)


def test_author_matches_by_email_local_part():
    filters = ["hanqw"]
    assert _author_matches("", "hanqw@ztt.cn", "", filters)


@pytest.mark.asyncio
async def test_failed_sync_keeps_last_sync_at(failing_gitee):
    """同步失败时不推进 last_sync_at，否则重试会漏掉历史提交。"""
    from app.database import SessionLocal
    from app.models import Repo
    from app.services.sync import sync_repo

    db = SessionLocal()
    repo = Repo(
        name="失败用例",
        platform="gitee",
        owner="demo",
        repo="repo",
        base_url=failing_gitee,
        token_enc="",
        enabled=True,
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)

    with pytest.raises(Exception):
        await sync_repo(db, repo)

    db.refresh(repo)
    assert repo.last_sync_status == "failed"
    assert repo.last_sync_at is None

    db.delete(repo)
    db.commit()
    db.close()
