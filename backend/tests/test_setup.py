from __future__ import annotations

import pytest

from app.services.config_store import get_llm_config, is_initialized


def test_setup_status_lists_steps(client):
    body = client.get("/api/setup/status").json()
    assert "initialized" in body
    assert body["database"]["driver"] in ("sqlite", "mysql")
    keys = [step["key"] for step in body["steps"]]
    assert keys == ["database", "llm", "password", "repo"]


def test_setup_complete_marks_initialized(client):
    body = client.post("/api/setup/complete").json()
    assert body["initialized"] is True


def test_setup_reset_clears_initialized(client):
    client.post("/api/setup/complete")
    body = client.post("/api/setup/reset").json()
    assert body["initialized"] is False


def test_setup_database_rejects_unreachable_url(client):
    response = client.post(
        "/api/setup/database",
        json={"database_url": "mysql+pymysql://nobody:nobody@127.0.0.1:1/none?charset=utf8mb4"},
    )
    assert response.status_code == 400
    assert "无法连接" in response.json()["detail"]


def test_setup_llm_does_not_save_when_unreachable(client):
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        get_llm_config(db).model == ""
    finally:
        db.close()

    response = client.post(
        "/api/setup/llm",
        json={
            "base_url": "http://127.0.0.1:1/v1",
            "api_key": "",
            "model": "no-such-model",
            "temperature": 0.3,
        },
    )
    assert response.status_code == 400
    db = SessionLocal()
    try:
        assert get_llm_config(db).model == ""
    finally:
        db.close()


def test_setup_password_sets_password_and_session(client):
    response = client.post("/api/setup/password", json={"password": "abc-123"})
    assert response.status_code == 200
    assert "set_cookie" in response.headers or response.cookies
    body = response.json()
    password_step = next(step for step in body["steps"] if step["key"] == "password")
    assert password_step["done"] is True
    # 设置密码后应能继续访问受保护接口
    assert client.get("/api/dashboard/overview").status_code == 200