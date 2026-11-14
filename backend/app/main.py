from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import describe_database, init_schema
from .routers import auth, commits, dashboard, monitors, projects, reports, repos, reviews, setup, works
from .routers import settings as settings_router
from .services import task_queue
from .services.scheduler import shutdown_scheduler, start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("worklog")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_schema()
    _bootstrap_defaults()
    _reset_stale_tasks()
    logger.info("数据库：%s", describe_database()["target"])
    logger.info("数据目录：%s", settings.data_path)
    start_scheduler()
    await task_queue.start_worker()
    yield
    await task_queue.stop_worker()
    shutdown_scheduler()


def _bootstrap_defaults() -> None:
    """写入默认配置，让空库也能直接用。"""
    from .database import SessionLocal
    from .services.config_store import ensure_defaults

    db = SessionLocal()
    try:
        ensure_defaults(db)
    finally:
        db.close()


def _reset_stale_tasks() -> None:
    """进程重启后，把上次未完成的任务标记为失败。"""
    from .database import SessionLocal
    from .models import ReviewTask
    from .timeutil import now_local

    db = SessionLocal()
    try:
        stale = db.query(ReviewTask).filter(ReviewTask.status.in_(["pending", "running"])).all()
        for task in stale:
            task.status = "failed"
            task.message = "服务重启，任务已中断"
            task.finished_at = now_local()
        if stale:
            db.commit()
            logger.info("已重置 %s 个中断的审查任务", len(stale))
    finally:
        db.close()


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(repos.router)
app.include_router(commits.router)
app.include_router(works.router)
app.include_router(reports.router)
app.include_router(settings_router.router)
app.include_router(dashboard.router)
app.include_router(projects.router)
app.include_router(reviews.router)
app.include_router(monitors.router)
app.include_router(setup.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "version": "1.0.0"}


def _static_dir() -> Path | None:
    candidates: list[Path] = []
    # 打包成单文件程序时，静态资源随包解到临时目录
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        candidates.append(Path(bundle_dir) / "static")
    here = Path(__file__).resolve()
    candidates.append(here.parents[2] / "static")
    candidates.append(here.parents[1] / "static")
    candidates.append(Path.cwd() / "static")
    for candidate in candidates:
        if (candidate / "index.html").is_file():
            return candidate
    return None


static_dir = _static_dir()
if static_dir is not None:
    assets_dir = static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="接口不存在")
        if full_path:
            candidate = (static_dir / full_path).resolve()
            try:
                candidate.relative_to(static_dir.resolve())
            except ValueError:
                return FileResponse(static_dir / "index.html")
            if candidate.is_file():
                return FileResponse(candidate)
        return FileResponse(static_dir / "index.html")