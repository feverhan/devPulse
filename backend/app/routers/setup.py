from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import describe_database, get_db, switch_database, test_connection
from ..deps import require_auth
from ..models import Repo, Report
from ..security import (
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
    env_password,
    get_stored_password,
    issue_session,
    set_stored_password,
)
from ..services.config_store import (
    ensure_defaults,
    get_llm_config,
    get_setup_flag,
    is_initialized,
    mark_initialized,
    save_llm_config,
)
from ..services.llm import LLMConfig, LLMError, test_connection as llm_test

router = APIRouter(prefix="/api/setup", tags=["setup"], dependencies=[Depends(require_auth)])


class DatabaseIn(BaseModel):
    database_url: str = ""


class LLMIn(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    temperature: float = 0.3


class PasswordIn(BaseModel):
    password: str = Field(default="", max_length=128)


class MigrateIn(BaseModel):
    from_url: str = ""
    to_url: str = ""


class ExportIn(BaseModel):
    database_url: str = ""


class ImportIn(BaseModel):
    payload: dict


def _status(db: Session) -> dict:
    llm = get_llm_config(db)
    repo_count = db.execute(select(func.count()).select_from(Repo)).scalar_one()
    report_count = db.execute(select(func.count()).select_from(Report)).scalar_one()
    password_set = bool(env_password()) or bool(get_stored_password(db)[1])
    # 标记存在则按用户的选择；从未设置过（历史库）且有数据时视为已初始化
    flag = get_setup_flag(db)
    if flag is None:
        initialized = int(repo_count) > 0 or int(report_count) > 0
    else:
        initialized = flag
    return {
        "initialized": initialized,
        "database": describe_database(),
        "steps": [
            {
                "key": "database",
                "title": "数据库",
                "done": True,
                "detail": (
                    "已使用本地 SQLite，开箱即用"
                    if describe_database()["driver"] == "sqlite"
                    else "已连接 MySQL"
                ),
            },
            {
                "key": "llm",
                "title": "大模型",
                "done": llm.ready,
                "detail": llm.model if llm.ready else "未配置，报告与审查将使用本地模板",
            },
            {
                "key": "password",
                "title": "访问密码",
                "done": password_set,
                "detail": "已设置" if password_set else "未设置，任何人可访问",
            },
            {
                "key": "repo",
                "title": "代码仓库",
                "done": int(repo_count) > 0,
                "detail": f"已接入 {int(repo_count)} 个",
            },
        ],
    }


@router.get("/status")
def status(db: Session = Depends(get_db)) -> dict:
    return _status(db)


@router.post("/database")
def setup_database(payload: DatabaseIn, db: Session = Depends(get_db)) -> dict:
    """切换数据库地址；留空则回到默认的本地 SQLite。"""
    url = (payload.database_url or "").strip()
    if url:
        ok, reason = test_connection(url)
        if not ok:
            raise HTTPException(status_code=400, detail=f"无法连接：{reason}")
        switch_database(url)
    else:
        switch_database("")
    ensure_defaults(db)
    return _status(db)


@router.post("/llm")
async def setup_llm(payload: LLMIn, db: Session = Depends(get_db)) -> dict:
    """先连通性测试，通过后再落库，失败不写入半成品配置。"""
    probe = LLMConfig(
        base_url=(payload.base_url or "").strip(),
        api_key=(payload.api_key or "").strip(),
        model=(payload.model or "").strip(),
        temperature=payload.temperature,
    )
    if probe.ready:
        try:
            await llm_test(probe)
        except LLMError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    save_llm_config(
        db,
        base_url=payload.base_url,
        api_key=payload.api_key,
        model=payload.model,
        temperature=payload.temperature,
    )
    return _status(db)


@router.post("/password")
def setup_password(
    payload: PasswordIn,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    """设置访问密码，并直接下发会话，避免后续步骤被挡在登录门外。"""
    if payload.password.strip():
        set_stored_password(db, payload.password.strip())
        response.set_cookie(
            SESSION_COOKIE,
            issue_session(),
            httponly=True,
            samesite="lax",
            max_age=SESSION_TTL_SECONDS,
            path="/",
        )
    else:
        from ..models import AppSetting

        row = db.get(AppSetting, "auth")
        if row:
            row.value = ""
            db.commit()
    return _status(db)


@router.post("/migrate")
def migrate(payload: MigrateIn, db: Session = Depends(get_db)) -> dict:
    """把数据整体复制到另一个库（默认本地 SQLite），并切换过去。"""
    from ..database import SessionLocal
    from ..services.migrate import copy_database, target_sqlite_url

    source = (payload.from_url or "").strip() or settings.sqlalchemy_url
    target = (payload.to_url or "").strip() or target_sqlite_url()
    if source == target:
        raise HTTPException(status_code=400, detail="源库与目标库相同")

    ok, reason = test_connection(source)
    if not ok:
        raise HTTPException(status_code=400, detail=f"源库无法连接：{reason}")
    ok, reason = test_connection(target)
    if not ok:
        raise HTTPException(status_code=400, detail=f"目标库无法连接：{reason}")

    counts = copy_database(source, target)
    switch_database(target)

    fresh = SessionLocal()
    try:
        result = _status(fresh)
    finally:
        fresh.close()
    result["migrated"] = counts
    return result


@router.post("/export")
def export_data(payload: ExportIn) -> dict:
    """导出全部数据为 JSON 文本。"""
    from ..services.migrate import export_data as do_export

    data = do_export(payload.database_url or settings.sqlalchemy_url)
    return {"payload": data, "counts": {key: len(value) for key, value in data.items() if isinstance(value, list)}}


@router.get("/export")
def export_file() -> Response:
    """以附件形式导出全部数据。"""
    import json

    from ..services.migrate import _json_default, export_data as do_export

    payload = do_export()
    body = json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default)
    stamp = payload.get("exported_at", "").replace(":", "").replace("-", "").replace("T", "-")[:13]
    filename = f"worklog-export-{stamp}.json"
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import")
def import_data(payload: ImportIn, db: Session = Depends(get_db)) -> dict:
    """从导出的 JSON 恢复数据。"""
    from ..security import adopt_secret
    from ..services.migrate import import_data as do_import

    # 导入到新机器时采用导出方的主密钥，否则令牌与大模型密钥会解开失败
    adopted = False
    if not (settings.app_secret or "").strip():
        adopted = adopt_secret(str(payload.payload.get("secret") or ""))
        if not adopted and payload.payload.get("secret_key"):
            # 导出方用的是自动生成的密钥文件，直接放回数据目录
            try:
                (settings.data_path / "secret.key").write_text(
                    str(payload.payload["secret_key"]), encoding="utf-8"
                )
                adopted = True
            except OSError:
                pass

    counts = do_import(payload.payload, settings.sqlalchemy_url)
    return {"counts": counts, "secret_adopted": adopted, "status": _status(db)}


@router.post("/reset-database-source")
def reset_database_source(db: Session = Depends(get_db)) -> dict:
    """清除界面里选定的数据库地址，恢复使用环境变量。"""
    from ..config import settings
    from ..database import SessionLocal

    try:
        settings.database_file.unlink(missing_ok=True)
    except OSError:
        pass
    switch_database(settings.database_url or "")
    fresh = SessionLocal()
    try:
        return _status(fresh)
    finally:
        fresh.close()


@router.post("/complete")
def complete(db: Session = Depends(get_db)) -> dict:
    mark_initialized(db, True)
    return _status(db)


@router.post("/reset")
def reset(db: Session = Depends(get_db)) -> dict:
    """重新进入初始化流程。"""
    mark_initialized(db, False)
    return _status(db)