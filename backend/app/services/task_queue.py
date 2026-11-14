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
        state = {"queues": {}, "workers": {}}
        _states[key] = state
    return state


def _queue_of(state: dict, name: str) -> asyncio.Queue:
    queues = state["queues"]
    if name not in queues:
        queues[name] = asyncio.Queue()
    return queues[name]


async def start_worker(name: str = "default") -> None:
    state = _current_state()
    workers = state["workers"]
    worker = workers.get(name)
    if worker and not worker.done():
        return
    queue = _queue_of(state, name)
    workers[name] = asyncio.create_task(_loop(queue))
    logger.info("后台任务队列已启动：%s", name)


async def stop_worker(name: str = "") -> None:
    """停止指定队列；不指定则全部停掉。"""
    state = _current_state()
    workers = state["workers"]
    names = [name] if name else list(workers)
    for item in names:
        worker = workers.get(item)
        if not worker:
            continue
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass
        workers.pop(item, None)


def submit(handler: Callable[[], Awaitable[None]], name: str = "default") -> None:
    state = _current_state()
    _queue_of(state, name).put_nowait(handler)


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