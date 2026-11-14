from __future__ import annotations

import json

from sqlalchemy.orm import Session

from ..config import settings
from ..models import AppSetting
from ..security import decrypt, encrypt
from .llm import LLMConfig

KEY_LLM = "llm"
KEY_SYNC = "sync"
KEY_AUTHOR = "author"
KEY_WECHAT = "wechat"
KEY_SETUP = "setup"

DEFAULT_SYNC = {
    "sync_interval_minutes": 30,
    "fetch_commit_files": True,
    "max_pages_per_sync": 20,
}


def _read(db: Session, key: str) -> dict:
    row = db.get(AppSetting, key)
    if not row or not row.value:
        return {}
    try:
        data = json.loads(row.value)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _write(db: Session, key: str, data: dict) -> None:
    row = db.get(AppSetting, key)
    payload = json.dumps(data, ensure_ascii=False)
    if row:
        row.value = payload
    else:
        db.add(AppSetting(key=key, value=payload))
    db.commit()


def get_llm_config(db: Session) -> LLMConfig:
    data = _read(db, KEY_LLM)
    api_key = decrypt(data.get("api_key_enc") or "")
    return LLMConfig(
        base_url=(data.get("base_url") or settings.llm_base_url or "").strip(),
        api_key=api_key or (settings.llm_api_key or "").strip(),
        model=(data.get("model") or settings.llm_model or "").strip(),
        temperature=float(data.get("temperature", settings.llm_temperature)),
        timeout=float(settings.llm_timeout or 300.0),
    )


def save_llm_config(
    db: Session,
    base_url: str,
    api_key: str | None,
    model: str,
    temperature: float,
) -> LLMConfig:
    data = _read(db, KEY_LLM)
    data["base_url"] = (base_url or "").strip()
    data["model"] = (model or "").strip()
    data["temperature"] = float(temperature)
    if api_key is not None and api_key.strip():
        data["api_key_enc"] = encrypt(api_key.strip())
    _write(db, KEY_LLM, data)
    return get_llm_config(db)


def get_author_filter(db: Session) -> list[str]:
    """我的作者标识，留空表示不按作者过滤。"""
    data = _read(db, KEY_AUTHOR)
    raw = data.get("identifiers") or []
    if isinstance(raw, str):
        raw = raw.replace("，", ",").split(",")
    return [str(item).strip() for item in raw if str(item).strip()]


def save_author_filter(db: Session, identifiers: list[str]) -> list[str]:
    values = [str(item).strip() for item in identifiers if str(item).strip()]
    _write(db, KEY_AUTHOR, {"identifiers": values})
    return values


def get_wechat_webhook(db: Session) -> str:
    """企业微信群机器人 webhook 地址。"""
    return str(_read(db, KEY_WECHAT).get("url") or "").strip()


def save_wechat_webhook(db: Session, url: str) -> str:
    value = (url or "").strip()
    _write(db, KEY_WECHAT, {"url": value})
    return value


def ensure_defaults(db: Session) -> None:
    """写入默认配置，保证后续读取有值。"""
    for key, payload in (
        (KEY_SYNC, dict(DEFAULT_SYNC)),
        (KEY_AUTHOR, {"identifiers": []}),
        (KEY_WECHAT, {"url": ""}),
    ):
        if not db.get(AppSetting, key):
            _write(db, key, payload)


def get_setup_flag(db: Session) -> bool | None:
    """初始化标记；从未设置过时返回 None，表示交由调用方按存量数据推断。"""
    row = db.get(AppSetting, KEY_SETUP)
    if not row or not row.value:
        return None
    try:
        return bool(json.loads(row.value).get("initialized"))
    except json.JSONDecodeError:
        return None


def is_initialized(db: Session) -> bool:
    """是否已完成首次初始化。"""
    flag = get_setup_flag(db)
    return bool(flag)


def mark_initialized(db: Session, value: bool = True) -> None:
    from ..timeutil import now_local

    _write(db, KEY_SETUP, {"initialized": value, "at": now_local().isoformat()})


def get_sync_settings(db: Session) -> dict:
    data = _read(db, KEY_SYNC)
    return {
        "sync_interval_minutes": int(data.get("sync_interval_minutes", settings.sync_interval_minutes)),
        "fetch_commit_files": bool(data.get("fetch_commit_files", settings.fetch_commit_files)),
        "max_pages_per_sync": int(data.get("max_pages_per_sync", settings.max_pages_per_sync)),
    }


def save_sync_settings(db: Session, **values: object) -> dict:
    data = _read(db, KEY_SYNC)
    data.update({k: v for k, v in values.items() if v is not None})
    _write(db, KEY_SYNC, data)
    return get_sync_settings(db)