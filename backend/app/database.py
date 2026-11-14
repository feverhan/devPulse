from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


def _engine_kwargs(url: str) -> dict[str, object]:
    kwargs: dict[str, object] = {"pool_pre_ping": True, "future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_recycle"] = 3600
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20
    return kwargs


def _create_engine(url: str | None = None) -> Engine:
    target = url or settings.sqlalchemy_url
    return create_engine(target, **_engine_kwargs(target))  # type: ignore[arg-type]


engine = _create_engine()


if settings.is_sqlite:

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _rebuild_engine(url: str) -> None:
    global engine
    engine.dispose()
    engine = _create_engine(url)
    SessionLocal.configure(bind=engine)


def init_schema() -> None:
    """建表并补齐新增字段。

    记录的数据库地址若已失效（如从容器里搬出来的路径），自动回退到默认配置，
    避免因为一个失效地址起不来。
    """
    from .migrations import ensure_schema
    from .models import Base  # noqa: F401  确保模型已注册

    logger = logging.getLogger("worklog")
    try:
        Base.metadata.create_all(bind=engine)
    except OperationalError as exc:
        if settings.database_source != "file":
            raise
        logger.warning("记录的数据库地址不可用（%s），回退到默认配置", exc)
        try:
            settings.database_file.unlink(missing_ok=True)
        except OSError:
            pass
        settings.database_url = ""
        _rebuild_engine(settings.sqlalchemy_url)
        Base.metadata.create_all(bind=engine)

    applied = ensure_schema(engine)
    if applied:
        logger.info("已补齐字段：%s", ", ".join(applied))


def switch_database(url: str, persist: bool = True) -> None:
    """运行时切换数据库连接。旧引擎先释放，sessionmaker 重新绑定。

    persist=True 时把地址写入 data/database.url，重启后依然生效。
    """
    global engine
    engine.dispose()
    engine = _create_engine(url)
    SessionLocal.configure(bind=engine)
    settings.database_url = url
    if persist:
        try:
            settings.database_file.write_text(url, encoding="utf-8")
        except OSError:
            logging.getLogger("worklog").warning("数据库地址写入失败")
    init_schema()


def test_connection(url: str) -> tuple[bool, str]:
    """试连一个数据库地址，不改当前连接。"""
    target = (url or "").strip()
    if not target:
        return False, "数据库地址为空"
    probe = None
    try:
        probe = create_engine(target, **_engine_kwargs(target))
        with probe.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:300]
    finally:
        if probe is not None:
            probe.dispose()
    return True, ""


def describe_database() -> dict:
    """当前数据库的对外描述，不暴露口令。"""
    url = settings.sqlalchemy_url
    driver = "sqlite" if url.startswith("sqlite") else "mysql"
    if driver == "sqlite":
        target = Path(settings.data_path) / "worklog.db"
    else:
        target = re.sub(r"//[^@/]+@", "//***@", url)
    return {"driver": driver, "target": str(target), "source": settings.database_source}