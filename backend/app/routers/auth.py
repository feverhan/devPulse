from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import (
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
    issue_session,
    password_enabled,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    password: str = ""


@router.post("/login")
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)) -> dict:
    if not password_enabled(db):
        return {"ok": True, "password_required": False}
    if not verify_password(db, payload.password):
        raise HTTPException(status_code=401, detail="密码错误")
    token = issue_session()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_TTL_SECONDS,
        path="/",
    )
    return {"ok": True, "password_required": True}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(db: Session = Depends(get_db)) -> dict:
    return {"authenticated": True, "password_required": password_enabled(db)}