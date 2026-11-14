from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger("worklog.tasks")

# 每个事件循环一套队列与 worker，避免跨 loop 复用
_states: dict[int, dict] = {}


def _current_state() -> dict:
    loop = asyncio.get_running_loop()
    key = id(loop)
    state = _states.get(key)
    if state is None:
        state = {"queue": asyncio.Queue(), "worker": None}
        _states[key] = state
    return state


async def start_worker() -> None:
    state = _current_state()
    worker = state.get("worker")
    if worker and not worker.done():
        return
    state["worker"] = asyncio.create_task(_loop(state["queue"]))
    logger.info("后台任务队列已启动")


async def stop_worker() -> None:
    state = _current_state()
    worker = state.get("worker")
    if worker:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass
        state["worker"] = None


def submit(handler: Callable[[], Awaitable[None]]) -> None:
    state = _current_state()
    state["queue"].put_nowait(handler)


async def _loop(queue: asyncio.Queue) -> None:
    while True:
        handler = await queue.get()
        try:
            await handler()
        except asyncio.CancelledError:
            queue.task_done()
            raise
        except Exception:  # noqa: BLE001 - 单个任务失败不影响队列
            logger.exception("后台任务执行失败")
            queue.task_done()
        else:
            queue.task_done()