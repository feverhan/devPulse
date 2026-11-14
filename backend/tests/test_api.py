from __future__ import annotations


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_auth_not_required_without_password(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["password_required"] is False


def test_repo_crud(client):
    created = client.post(
        "/api/repos",
        json={
            "name": "示例仓库",
            "platform": "gitea",
            "owner": "demo",
            "repo": "sample",
            "base_url": "https://gitea.com",
            "token": "secret-token",
            "enabled": True,
            "include_keywords": "",
            "exclude_keywords": "merge",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["token_set"] is True
    repo_id = body["id"]

    listed = client.get("/api/repos").json()
    assert any(item["id"] == repo_id for item in listed)

    updated = client.put(f"/api/repos/{repo_id}", json={"name": "示例仓库2"}).json()
    assert updated["name"] == "示例仓库2"

    assert client.delete(f"/api/repos/{repo_id}").status_code == 200
    assert all(item["id"] != repo_id for item in client.get("/api/repos").json())


def test_repo_update_keeps_token_when_not_provided(client):
    """编辑仓库时未填写令牌，不应清空已保存的令牌。"""
    created = client.post(
        "/api/repos",
        json={
            "name": "令牌仓库",
            "platform": "gitea",
            "owner": "demo",
            "repo": "token-repo",
            "base_url": "https://gitea.com",
            "token": "secret-token",
            "enabled": True,
            "include_keywords": "",
            "exclude_keywords": "",
        },
    )
    repo_id = created.json()["id"]
    assert created.json()["token_set"] is True

    renamed = client.put(f"/api/repos/{repo_id}", json={"name": "令牌仓库2"}).json()
    assert renamed["token_set"] is True

    blank = client.put(f"/api/repos/{repo_id}", json={"token": ""}).json()
    assert blank["token_set"] is True

    cleared = client.put(f"/api/repos/{repo_id}", json={"clear_token": True}).json()
    assert cleared["token_set"] is False

    client.delete(f"/api/repos/{repo_id}")


def test_repo_probe_reports_platform_mismatch(client):
    result = client.post(
        "/api/repos/probe",
        json={
            "name": "探测",
            "platform": "gitee",
            "owner": "demo",
            "repo": "x",
            "base_url": "https://gitea.com",
            "token": "",
            "enabled": True,
            "include_keywords": "",
            "exclude_keywords": "",
        },
    )
    assert result.status_code == 200
    body = result.json()
    assert body["detected_platform"] == "gitea"
    assert body["ok"] is False


def test_work_entry_crud(client):
    created = client.post(
        "/api/works",
        json={
            "work_date": "2026-11-10",
            "title": "完成联调",
            "content": "对接报告接口",
            "category": "研发",
            "project": "工时周报",
            "tags": "",
            "hours": 6,
        },
    )
    assert created.status_code == 201
    work_id = created.json()["id"]

    listed = client.get("/api/works", params={"keyword": "联调"}).json()
    assert listed["total"] >= 1

    updated = client.put(f"/api/works/{work_id}", json={"hours": 8}).json()
    assert updated["hours"] == 8

    assert client.delete(f"/api/works/{work_id}").status_code == 200


def test_report_generation_without_llm(client):
    client.post(
        "/api/works",
        json={
            "work_date": "2026-11-11",
            "title": "短临预警系统MCP服务开发",
            "content": "完成接口联调",
            "category": "研发",
            "project": "南通海事短临预警系统",
            "tags": "",
            "hours": 6,
        },
    )
    response = client.post(
        "/api/reports/generate",
        json={"period_type": "weekly", "reference_date": "2026-11-13", "use_llm": False},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["start_date"] == "2026-11-09"
    assert body["end_date"] == "2026-11-15"
    assert body["model"] == "本地模板"
    # 报告正文按项目分组：中文序号 + 编号事项
    assert "一、南通海事短临预警系统" in body["content"]
    assert "1.短临预警系统MCP服务开发" in body["content"]
    assert "数据概览" not in body["content"]
    assert body["stats"]["project_count"] >= 0


def test_dashboard_overview(client):
    body = client.get("/api/dashboard/overview").json()
    assert body["repo_count"] >= 0
    assert len(body["trend"]) == 14

def test_work_entry_requires_project(client):
    """工作记录的项目为必填。"""
    response = client.post(
        "/api/works",
        json={
            "work_date": "2026-11-10",
            "title": "缺少项目的记录",
            "content": "",
            "category": "研发",
            "project": "",
            "tags": "",
            "hours": 2,
        },
    )
    assert response.status_code == 422


def test_work_entry_update_rejects_blank_project(client):
    created = client.post(
        "/api/works",
        json={
            "work_date": "2026-11-10",
            "title": "带项目的记录",
            "content": "",
            "category": "研发",
            "project": "集团访客系统",
            "tags": "",
            "hours": 2,
        },
    )
    assert created.status_code == 201
    work_id = created.json()["id"]

    assert client.put(f"/api/works/{work_id}", json={"project": ""}).status_code == 422
    assert client.delete(f"/api/works/{work_id}").status_code == 200


def test_projects_are_extracted_from_commits(client):
    """项目清单从已同步提交所属的仓库中抽取。"""
    repo = client.post(
        "/api/repos",
        json={
            "name": "某仓库",
            "project": "集团访客系统",
            "platform": "gitea",
            "owner": "demo",
            "repo": "visitor",
            "base_url": "https://gitea.com",
            "token": "",
            "enabled": True,
            "include_keywords": "",
            "exclude_keywords": "",
        },
    )
    repo_id = repo.json()["id"]

    projects = client.get("/api/projects").json()
    names = [item["name"] for item in projects]
    assert "集团访客系统" in names

    client.delete(f"/api/repos/{repo_id}")


def test_project_can_be_created_without_repo(client):
    """没有仓库的项目可以手工登记。"""
    response = client.post("/api/projects", json={"name": "无仓库项目", "note": "线下对接"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "无仓库项目"
    assert body["source"] == "manual"
    assert body["repos"] == 0

    names = [item["name"] for item in client.get("/api/projects").json()]
    assert "无仓库项目" in names

    duplicate = client.post("/api/projects", json={"name": "无仓库项目"})
    assert duplicate.status_code == 409

    projects = client.get("/api/projects").json()
    target = next(item for item in projects if item["name"] == "无仓库项目")
    assert client.delete(f"/api/projects/{target['id']}").status_code == 200


def test_work_entry_registers_new_project(client):
    """工作记录填的新项目会自动登记到项目清单。"""
    client.post(
        "/api/works",
        json={
            "work_date": "2026-11-10",
            "title": "线下项目工作",
            "content": "",
            "category": "研发",
            "project": "线下临时项目",
            "tags": "",
            "hours": 3,
        },
    )
    projects = client.get("/api/projects").json()
    names = [item["name"] for item in projects]
    assert "线下临时项目" in names
    item = next(entry for entry in projects if entry["name"] == "线下临时项目")
    assert item["works"] == 1

    assert client.delete(f"/api/projects/{item['id']}").status_code == 200
    remaining = client.get("/api/works", params={"project": "线下临时项目"}).json()
    assert remaining["total"] == 0


def test_projects_merge_repo_and_work_sources(client):
    repo = client.post(
        "/api/repos",
        json={
            "name": "仓库甲",
            "project": "项目甲",
            "platform": "gitea",
            "owner": "demo",
            "repo": "jia",
            "base_url": "https://gitea.com",
            "token": "",
            "enabled": True,
            "include_keywords": "",
            "exclude_keywords": "",
        },
    ).json()

    projects = client.get("/api/projects").json()
    item = next(entry for entry in projects if entry["name"] == "项目甲")
    assert item["repos"] == 1
    assert item["source"] == "auto"

    client.delete(f"/api/repos/{repo['id']}")
