from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import (
    routes_ai,
    routes_blacklist,
    routes_blacklist_ai,
    routes_export,
    routes_login,
    routes_predict,
    routes_settings,
    routes_status,
    routes_videos,
    routes_watchlater,
)
from .db import SessionLocal, init_db
from .services.cookie import bootstrap_cookie_from_files
from .settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        await bootstrap_cookie_from_files(db)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("cookie bootstrap failed: %s", exc)
    finally:
        db.close()
    yield


app = FastAPI(
    title="AddToView",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_status.router, prefix="/api", tags=["status"])
app.include_router(routes_login.router, prefix="/api/login", tags=["login"])
app.include_router(routes_watchlater.router, prefix="/api/watchlater", tags=["watchlater"])
app.include_router(routes_videos.router, prefix="/api/videos", tags=["videos"])
app.include_router(routes_blacklist.router, prefix="/api/blacklist", tags=["blacklist"])
app.include_router(routes_settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(routes_export.router, prefix="/api/export", tags=["export"])
app.include_router(routes_predict.router, prefix="/api/predict", tags=["predict"])
app.include_router(routes_ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(routes_blacklist_ai.router, prefix="/api/ai", tags=["ai"])


if settings.serve_static and settings.resolved_static_dir.exists():
    static_dir = settings.resolved_static_dir
    # mount under /assets so it doesn't shadow /api routes
    if (static_dir / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        # let /api and /docs and /openapi.json continue to be handled by their routes
        if full_path.startswith("api") or full_path in ("docs", "openapi.json", "redoc"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404)
        target = static_dir / full_path
        if full_path and target.exists() and target.is_file():
            return FileResponse(target)
        return FileResponse(static_dir / "index.html")

else:

    @app.get("/")
    def root() -> dict[str, str]:
        return {"name": "AddToView", "version": __version__, "docs": "/docs"}
