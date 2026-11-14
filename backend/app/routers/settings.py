from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_auth
from ..schemas import AppSettingsIn, AppSettingsOut, LLMConfigOut
from ..security import env_password, set_stored_password
from ..services.config_store import (
    get_author_filter,
    get_llm_config,
    get_sync_settings,
    get_wechat_webhook,
    save_author_filter,
    save_wechat_webhook,
    save_llm_config,
    save_sync_settings,
)
from ..services.llm import LLMError, test_connection
from ..services.scheduler import reschedule_sync

router = APIRouter(prefix="/api/settings", tags=["settings"], dependencies=[Depends(require_auth)])


@router.get("")
def read_settings(db: Session = Depends(get_db)) -> AppSettingsOut:
    llm = get_llm_config(db)
    sync = get_sync_settings(db)
    return AppSettingsOut(
        llm=LLMConfigOut(
            base_url=llm.base_url,
            api_key_set=bool(llm.api_key),
            model=llm.model,
            temperature=llm.temperature,
        ),
        sync_interval_minutes=sync["sync_interval_minutes"],
        fetch_commit_files=sync["fetch_commit_files"],
        max_pages_per_sync=sync["max_pages_per_sync"],
        my_authors=get_author_filter(db),
        wechat_webhook=get_wechat_webhook(db),
        app_password_set=bool(env_password()),
    )


@router.put("")
def update_settings(payload: AppSettingsIn, db: Session = Depends(get_db)) -> AppSettingsOut:
    if payload.llm is not None:
        save_llm_config(
            db,
            base_url=payload.llm.base_url,
            api_key=payload.llm.api_key,
            model=payload.llm.model,
            temperature=payload.llm.temperature,
        )
    if payload.sync_interval_minutes is not None:
        save_sync_settings(db, sync_interval_minutes=payload.sync_interval_minutes)
    if payload.fetch_commit_files is not None:
        save_sync_settings(db, fetch_commit_files=payload.fetch_commit_files)
    if payload.max_pages_per_sync is not None:
        save_sync_settings(db, max_pages_per_sync=payload.max_pages_per_sync)
    if payload.my_authors is not None:
        save_author_filter(db, payload.my_authors)
    if payload.wechat_webhook is not None:
        save_wechat_webhook(db, payload.wechat_webhook)
    if payload.app_password:
        set_stored_password(db, payload.app_password)
    if payload.sync_interval_minutes:
        reschedule_sync(payload.sync_interval_minutes)
    return read_settings(db)


@router.post("/llm/test")
async def test_llm(db: Session = Depends(get_db)) -> dict:
    config = get_llm_config(db)
    if not config.ready:
        raise HTTPException(status_code=400, detail="请先填写大模型地址与模型名称")
    try:
        reply = await test_connection(config)
    except LLMError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "reply": reply, "model": config.model}