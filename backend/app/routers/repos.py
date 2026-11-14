from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_auth
from ..models import Repo
from ..schemas import RepoCreate, RepoOut, RepoUpdate
from ..security import encrypt
from ..services.gitplatform import PlatformError, build_client, detect_platform
from ..services.sync import sync_all, sync_repo

router = APIRouter(prefix="/api/repos", tags=["repos"], dependencies=[Depends(require_auth)])


def _to_out(repo: Repo) -> RepoOut:
    return RepoOut(
        id=repo.id,
        name=repo.name,
        project=repo.project or repo.name,
        platform=repo.platform,
        owner=repo.owner,
        repo=repo.repo,
        base_url=repo.base_url,
        token_set=bool(repo.token_enc),
        enabled=repo.enabled,
        include_keywords=repo.include_keywords,
        exclude_keywords=repo.exclude_keywords,
        last_sync_at=repo.last_sync_at,
        last_sync_status=repo.last_sync_status,
        last_sync_message=repo.last_sync_message,
        created_at=repo.created_at,
    )


@router.get("")
def list_repos(db: Session = Depends(get_db)) -> list[RepoOut]:
    repos = db.execute(select(Repo).order_by(Repo.id.desc())).scalars().all()
    return [_to_out(repo) for repo in repos]


@router.post("", status_code=201)
def create_repo(payload: RepoCreate, db: Session = Depends(get_db)) -> RepoOut:
    repo = Repo(
        name=payload.name,
        project=(payload.project or payload.name).strip(),
        platform=payload.platform,
        owner=payload.owner,
        repo=payload.repo,
        base_url=payload.base_url.strip(),
        token_enc=encrypt(payload.token),
        enabled=payload.enabled,
        include_keywords=payload.include_keywords,
        exclude_keywords=payload.exclude_keywords,
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return _to_out(repo)


@router.put("/{repo_id}")
def update_repo(repo_id: int, payload: RepoUpdate, db: Session = Depends(get_db)) -> RepoOut:
    repo = db.get(Repo, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="仓库不存在")
    data = payload.model_dump(exclude_unset=True)
    token = data.pop("token", None)
    clear_token = bool(data.pop("clear_token", False))
    for key, value in data.items():
        if value is not None:
            setattr(repo, key, value)
    if clear_token:
        repo.token_enc = ""
    elif token and token.strip():
        repo.token_enc = encrypt(token.strip())
    db.commit()
    db.refresh(repo)
    return _to_out(repo)


@router.delete("/{repo_id}")
def delete_repo(repo_id: int, db: Session = Depends(get_db)) -> dict:
    repo = db.get(Repo, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="仓库不存在")
    db.delete(repo)
    db.commit()
    return {"ok": True}


@router.post("/{repo_id}/sync")
async def sync_one(repo_id: int, db: Session = Depends(get_db)) -> dict:
    repo = db.get(Repo, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="仓库不存在")
    try:
        return await sync_repo(db, repo)
    except PlatformError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - 转换为可读提示，避免 500
        raise HTTPException(status_code=400, detail=f"同步失败：{exc}") from exc


@router.post("/sync")
async def sync_everything(db: Session = Depends(get_db)) -> dict:
    return await sync_all(db)


@router.post("/probe")
async def probe_repo(payload: RepoCreate) -> dict:
    """保存前探测服务地址与令牌，用于核对平台是否选对。"""
    detected = await detect_platform(payload.base_url)
    client = build_client(payload.platform, payload.base_url, payload.token)
    mismatch = bool(detected and detected != payload.platform)
    try:
        user = await client.whoami()
    except PlatformError as exc:
        return {"ok": False, "user": "", "detected_platform": detected, "message": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "user": "", "detected_platform": detected, "message": f"连接失败：{exc}"}
    if mismatch:
        return {
            "ok": False,
            "user": user,
            "detected_platform": detected,
            "message": f"服务地址是 {detected} 实例，当前平台选择为 {payload.platform}",
        }
    return {"ok": True, "user": user, "detected_platform": detected, "message": f"连接正常：{user}"}


@router.post("/{repo_id}/test")
async def test_repo(repo_id: int, db: Session = Depends(get_db)) -> dict:
    repo = db.get(Repo, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="仓库不存在")
    from ..security import decrypt

    client = build_client(repo.platform, repo.base_url, decrypt(repo.token_enc))
    try:
        user = await client.whoami()
    except PlatformError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"连接失败：{exc}") from exc
    detected = await detect_platform(repo.base_url)
    if detected and detected != repo.platform:
        return {
            "ok": False,
            "user": user,
            "base_url": client.base_url,
            "detected_platform": detected,
            "message": f"服务地址是 {detected} 实例，当前平台选择为 {repo.platform}",
        }
    return {
        "ok": True,
        "user": user,
        "base_url": client.base_url,
        "detected_platform": detected,
        "message": f"连接正常：{user}",
    }