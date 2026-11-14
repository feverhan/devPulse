"""数据导出、导入与库间迁移。

导出为 JSON，字段与数据表一一对应；导入会先清空目标表再写入。
库间迁移用于把 MySQL 的数据整体搬到 SQLite（或反之），避免重新配置。
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from ..config import settings

EXPORT_TABLES = [
    "app_settings",
    "projects",
    "repos",
    "commits",
    "work_entries",
    "reports",
    "review_tasks",
    "code_reviews",
    "review_findings",
    "monitors",
    "monitor_checks",
]


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _decode_value(column_type: Any, raw: Any) -> Any:
    """把 JSON 里的字符串还原成列类型需要的时间/日期/布尔/JSON。"""
    if raw is None:
        return None
    type_name = str(column_type).upper()
    if "DATETIME" in type_name and isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return raw
    if type_name.startswith("DATE") and isinstance(raw, str):
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return raw
    if "BOOLEAN" in type_name and isinstance(raw, str):
        return raw.strip().lower() in ("1", "true", "yes")
    if "JSON" in type_name and isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return raw


def _engine(url: str) -> Engine:
    kwargs: dict[str, object] = {"pool_pre_ping": True, "future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)  # type: ignore[arg-type]


def target_sqlite_url() -> str:
    """本地 SQLite 的连接串。"""
    path = Path(settings.data_path) / "worklog.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.as_posix()}"


def export_data(url: str | None = None) -> dict:
    """导出全部业务数据为可 JSON 化的字典。"""
    source = _engine(url or settings.sqlalchemy_url)
    payload: dict[str, Any] = {"exported_at": datetime.now().isoformat(timespec="seconds")}
    try:
        with source.connect() as conn:
            for table in EXPORT_TABLES:
                rows = conn.execute(text(f"SELECT * FROM {table}")).mappings().all()
                payload[table] = [dict(row) for row in rows]
    finally:
        source.dispose()
    return payload


def import_data(payload: dict, url: str | None = None, replace: bool = True) -> dict[str, int]:
    """把导出的数据写入目标库。目标库不存在时自动建表。

    走 ORM 的 Table 插入，由 SQLAlchemy 负责给保留字列名（如 limit）加引号。
    """
    from ..models import Base

    target = _engine(url or settings.sqlalchemy_url)
    tables = Base.metadata.tables
    counts: dict[str, int] = {}
    try:
        Base.metadata.create_all(bind=target)
        with target.begin() as conn:
            for name in EXPORT_TABLES:
                table = tables[name]
                rows = payload.get(name) or []
                if replace:
                    conn.execute(table.delete())
                if not rows:
                    counts[name] = 0
                    continue
                records = []
                for row in rows:
                    record = {}
                    for column in table.columns:
                        record[column.name] = _decode_value(column.type, row.get(column.name))
                    records.append(record)
                conn.execute(table.insert(), records)
                counts[name] = len(records)
    finally:
        target.dispose()
    return counts


def copy_database(source_url: str, target_url: str) -> dict[str, int]:
    """把源库的数据整体复制到目标库。"""
    payload = export_data(source_url)
    return import_data(payload, target_url, replace=True)


def write_export_file(path: str, payload: dict) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    return str(target)


def read_export_file(path: str) -> dict:
    data = Path(path).read_text(encoding="utf-8")
    payload = json.loads(data)
    if not isinstance(payload, dict):
        raise ValueError("导入文件格式不正确")
    return payload