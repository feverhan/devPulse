from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .database import get_db
from .security import SESSION_COOKIE, password_enabled, verify_session


def require_auth(request: Request, db: Session = Depends(get_db)) -> None:
    if not password_enabled(db):
        return
    if not verify_session(request.cookies.get(SESSION_COOKIE)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或登录已过期")