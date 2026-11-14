from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from .config import settings

SESSION_COOKIE = "wlr_session"
SESSION_TTL_SECONDS = 7 * 24 * 3600
AUTH_SETTING_KEY = "auth"


def _persisted_key() -> bytes:
    raw = (settings.app_secret or "").strip()
    if raw:
        return hashlib.sha256(raw.encode("utf-8")).digest()
    key_file: Path = settings.data_path / "secret.key"
    if key_file.exists():
        stored = key_file.read_text(encoding="utf-8").strip()
        if stored:
            return base64.urlsafe_b64decode(stored)
    fernet_key = Fernet.generate_key()
    key_file.write_text(fernet_key.decode("utf-8"), encoding="utf-8")
    return base64.urlsafe_b64decode(fernet_key)


def _fernet() -> Fernet:
    """当前使用的密钥，主密钥变更后立即生效。"""
    return Fernet(base64.urlsafe_b64encode(_persisted_key()))


def adopt_secret(secret: str) -> bool:
    """采用外部主密钥（如数据导入），并把派生密钥写进数据目录。

    写入 secret.key 是为了重启后没有 .env 时仍然解开导入的令牌与大模型密钥。
    """
    value = (secret or "").strip()
    if not value:
        return False
    settings.app_secret = value
    key = hashlib.sha256(value.encode("utf-8")).digest()
    try:
        (settings.data_path / "secret.key").write_text(
            base64.urlsafe_b64encode(key).decode("utf-8"), encoding="utf-8"
        )
    except OSError:
        pass
    return True


def encrypt(plain: str) -> str:
    if not plain:
        return ""
    return _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt(cipher: str) -> str:
    if not cipher:
        return ""
    try:
        return _fernet().decrypt(cipher.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""


def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def get_stored_password(db: Session) -> tuple[str, str]:
    """Return (salt, hash) for the database-stored password."""
    from .models import AppSetting

    row = db.get(AppSetting, AUTH_SETTING_KEY)
    if not row or not row.value:
        return "", ""
    import json

    try:
        data = json.loads(row.value)
    except json.JSONDecodeError:
        return "", ""
    return str(data.get("salt") or ""), str(data.get("password_hash") or "")


def set_stored_password(db: Session, password: str) -> None:
    from .models import AppSetting
    import json

    salt = secrets.token_hex(16)
    payload = json.dumps({"salt": salt, "password_hash": hash_password(password, salt)}, ensure_ascii=False)
    row = db.get(AppSetting, AUTH_SETTING_KEY)
    if row:
        row.value = payload
    else:
        db.add(AppSetting(key=AUTH_SETTING_KEY, value=payload))
    db.commit()


def env_password() -> str:
    return (settings.app_password or "").strip()


def password_enabled(db: Session | None = None) -> bool:
    if env_password():
        return True
    if db is None:
        return False
    _, stored_hash = get_stored_password(db)
    return bool(stored_hash)


def verify_password(db: Session, password: str) -> bool:
    candidate = (password or "").strip()
    env_value = env_password()
    if env_value:
        return hmac.compare_digest(env_value, candidate)
    salt, stored_hash = get_stored_password(db)
    if not stored_hash:
        return True
    return hmac.compare_digest(stored_hash, hash_password(candidate, salt))


def issue_session(username: str = "admin") -> str:
    expires_at = int(time.time()) + SESSION_TTL_SECONDS
    payload = f"{username}|{expires_at}"
    signature = hmac.new(_persisted_key(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}|{signature}"


def verify_session(token: str | None) -> bool:
    if not token:
        return False
    parts = token.split("|")
    if len(parts) != 3:
        return False
    username, expires_raw, signature = parts
    payload = f"{username}|{expires_raw}"
    expected = hmac.new(_persisted_key(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return False
    try:
        return int(expires_raw) > time.time()
    except ValueError:
        return False