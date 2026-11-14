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


@pytest.fixture()
def repo_with_authors():
    """一个仓库 + 三条提交：两条我的、一条同事的。"""
    from app.database import SessionLocal
    from app.models import Commit, Repo

    db = SessionLocal()
    repo = Repo(
        name="作者候选用例",
        platform="gitee",
        owner="demo",
        repo="authors",
        base_url="https://gitee.com",
        token_enc="",
        enabled=True,
    )
    db.add(repo)
    db.flush()
    db.add_all(
        [
            Commit(
                repo_id=repo.id,
                sha="a1",
                short_sha="a1",
                message="feat: 我的提交",
                author_name="hanqw",
                author_email="hanqw@ztt.cn",
                author_login="hanqw",
                committed_at=repo.created_at,
            ),
            Commit(
                repo_id=repo.id,
                sha="b2",
                short_sha="b2",
                message="feat: 同事提交",
                author_name="张三",
                author_email="zhangsan@ztt.cn",
                author_login="zhangsan",
                committed_at=repo.created_at,
            ),
        ]
    )
    db.commit()
    yield db, repo
    db.query(Commit).filter(Commit.repo_id == repo.id).delete()
    db.delete(repo)
    db.commit()
    db.close()


def test_record_authors_keeps_other_authors(repo_with_authors):
    """同步时没被汇总进来的作者也要进候选表。"""
    from app.models import RepoAuthor
    from app.services.gitplatform import FetchedCommit
    from app.services.sync import _record_authors

    db, repo = repo_with_authors
    fetched = [
        FetchedCommit(sha="c3", message="feat: 同事又提交", author_name="李四", author_email="lisi@ztt.cn", author_login="lisi"),
        FetchedCommit(sha="a1", message="feat: 我的提交", author_name="hanqw", author_email="hanqw@ztt.cn", author_login="hanqw"),
    ]
    _record_authors(db, repo, fetched)

    rows = db.query(RepoAuthor).filter(RepoAuthor.repo_id == repo.id).all()
    logins = {row.author_login: row.commit_count for row in rows}
    assert logins.get("lisi") == 1
    assert logins.get("hanqw") == 1

    # 再次同步同一批数据，计数按本次同步覆盖而不是累加
    _record_authors(db, repo, fetched)
    rows = db.query(RepoAuthor).filter(RepoAuthor.repo_id == repo.id).all()
    assert {row.author_login: row.commit_count for row in rows}["lisi"] == 1


def test_authors_api_merges_committed_and_seen(client, repo_with_authors):
    """候选接口同时返回已汇总与已见到但未汇总的作者。"""
    from app.models import RepoAuthor
    from app.services.sync import _record_authors

    db, repo = repo_with_authors
    db.add(
        RepoAuthor(
            repo_id=repo.id,
            identity="seed-lisi",
            author_name="李四",
            author_email="lisi@ztt.cn",
            author_login="lisi",
            commit_count=7,
        )
    )
    db.commit()

    resp = client.get("/api/commits/authors")
    assert resp.status_code == 200
    items = {item["author_login"]: item for item in resp.json()}
    assert items["hanqw"]["committed"] == 1
    assert items["zhangsan"]["committed"] == 1
    assert items["lisi"]["committed"] == 0
    assert items["lisi"]["seen"] == 7
    assert items["lisi"]["count"] == 7


def test_reset_sync_cursor_clears_last_sync_at(repo_with_authors):
    """作者标识变化后要重新扫一遍历史。"""
    from app.services.sync import reset_sync_cursor

    db, repo = repo_with_authors
    repo.last_sync_at = repo.created_at
    db.commit()
    reset_sync_cursor(db)
    db.refresh(repo)
    assert repo.last_sync_at is None


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
