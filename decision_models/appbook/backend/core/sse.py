"""Run a slow job in a thread and stream its progress as server-sent events.

Events: `progress` {done, total, ...}, then one `result` with the job's return value, or `error`.
"""
from __future__ import annotations

import asyncio
import json
import threading
from typing import Callable

from sse_starlette.sse import EventSourceResponse


def stream(work: Callable[[Callable[..., None]], dict]) -> EventSourceResponse:
    async def events():
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def put(item) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, item)

        def progress(done: int, total: int, **extra) -> None:
            put({"event": "progress", "data": json.dumps({"done": done, "total": total, **extra})})

        def run() -> None:
            try:
                put({"event": "result", "data": json.dumps(work(progress), default=str)})
            except Exception as exc:  # noqa: BLE001 — the page shows the message
                put({"event": "error", "data": json.dumps({"detail": f"{type(exc).__name__}: {exc}"[:300]})})
            finally:
                put(None)

        threading.Thread(target=run, daemon=True).start()
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item

    return EventSourceResponse(events())
