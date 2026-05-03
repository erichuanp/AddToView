"""Run the FastAPI app on multiple ports in one process.

The container exposes both 2232 and 2233 so existing CLI scripts that
hit `localhost:2232/addtoview/` keep working while the browser hits
:2233 like before. Same FastAPI app, same DB, just two listeners.
"""

from __future__ import annotations

import asyncio
import os
import signal

import uvicorn

from app.main import app


def _ports() -> list[int]:
    raw = os.getenv("ADDTOVIEW_PORTS", "2232,2233")
    return [int(p) for p in raw.split(",") if p.strip()]


HOST = os.getenv("ADDTOVIEW_HOST", "0.0.0.0")


async def _serve() -> None:
    servers = [
        uvicorn.Server(uvicorn.Config(app, host=HOST, port=p, log_config=None))
        for p in _ports()
    ]

    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    def _shutdown(*_: object) -> None:
        stop.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            pass

    async def _watch_stop() -> None:
        await stop.wait()
        for s in servers:
            s.should_exit = True

    asyncio.create_task(_watch_stop())
    await asyncio.gather(*(s.serve() for s in servers))


if __name__ == "__main__":
    asyncio.run(_serve())
