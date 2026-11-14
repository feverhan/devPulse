from __future__ import annotations

import json
from pathlib import Path

from app.database import SessionLocal, init_schema
from app.models import Repo, WorkEntry
from app.services.migrate import (
    copy_database,
    export_data,
    import_data,
    read_export_file,
    write_export_file,
)


def _seed(client):
    client.post(
        "/api/repos",
        json={
            "name": "迁移仓库",
            "project": "迁移项目",
            "platform": "gitea",
            "owner": "demo",
            "repo": "migrate",
            "base_url": "https://gitea.com",
            "token": "",
            "enabled": True,
            "include_keywords": "",
            "exclude_keywords": "",
        },
    )
    client.post(
        "/api/works",
        json={
            "work_date": "2026-11-12",
            "title": "迁移用例记录",
            "content": "",
            "category": "研发",
            "project": "迁移项目",
            "tags": "",
            "hours": 3,
        },
    )


def test_export_is_json_serializable(client):
    _seed(client)
    payload = export_data()
    text = json.dumps(payload, ensure_ascii=False, default=str)
    assert "迁移仓库" in text
    assert isinstance(payload["repos"], list)
    assert isinstance(payload["work_entries"], list)


def test_import_round_trip(tmp_path: Path, client):
    _seed(client)
    payload = export_data()
    path = write_export_file(str(tmp_path / "backup.json"), payload)
    assert Path(path).exists()

    reloaded = read_export_file(path)
    assert reloaded["repos"] == payload["repos"]

    target = f"sqlite:///{(tmp_path / 'target.db').as_posix()}"
    init_schema()
    counts = import_data(reloaded, target)
    assert counts["repos"] >= 1
    assert counts["work_entries"] >= 1


def test_copy_database_moves_rows(tmp_path: Path, client):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    _seed(client)
    source = f"sqlite:///{(tmp_path / 'src.db').as_posix()}"
    target = f"sqlite:///{(tmp_path / 'dst.db').as_posix()}"
    init_schema()
    import_data(export_data(), source)

    counts = copy_database(source, target)
    assert counts["repos"] >= 1

    engine = create_engine(target)
    session = sessionmaker(bind=engine)()
    try:
        names = [row.name for row in session.query(Repo).all()]
    finally:
        session.close()
        engine.dispose()
    assert "迁移仓库" in names


def test_work_entry_round_trip_preserves_fields(tmp_path: Path, client):
    _seed(client)
    payload = export_data()
    target = f"sqlite:///{(tmp_path / 'rt.db').as_posix()}"
    import_data(payload, target)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(target)
    session = sessionmaker(bind=engine)()
    try:
        entry = session.query(WorkEntry).filter(WorkEntry.project == "迁移项目").first()
        assert entry is not None
        assert entry.title == "迁移用例记录"
        assert entry.hours == 3
        assert str(entry.work_date) == "2026-11-12"
    finally:
        session.close()
        engine.dispose()