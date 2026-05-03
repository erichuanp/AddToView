from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..bilibili.client import BilibiliError
from ..db import get_db
from ..models import Action, ActionKind, Video
from ..services.ingest import (
    add_unfiltered_to_watchlater,
    ingest_dynamic_feed,
)
from .deps import require_cookie_dict

router = APIRouter()


@router.post("/sync")
async def sync(
    days: int = Query(default=7, ge=1, le=60),
    max_pages: int = Query(default=20, ge=1, le=60),
    cookies: dict[str, str] = Depends(require_cookie_dict),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return await ingest_dynamic_feed(db, cookies, days=days, max_pages=max_pages)
    except BilibiliError as exc:
        raise HTTPException(status_code=502, detail={"code": exc.code, "message": exc.message}) from exc


@router.post("/auto-add")
async def auto_add(
    days: int = Query(default=7, ge=1, le=60),
    cookies: dict[str, str] = Depends(require_cookie_dict),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    import time

    cutoff = int(time.time()) - days * 86400
    return await add_unfiltered_to_watchlater(db, cookies, since_pubdate=cutoff)


@router.get("/recent")
def recent(
    days: int = Query(default=7, ge=1, le=60),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    import time

    cutoff = int(time.time()) - days * 86400
    rows = list(
        db.execute(
            select(Video).where(Video.pubdate >= cutoff).order_by(Video.pubdate.desc())
        ).scalars()
    )
    return {
        "count": len(rows),
        "items": [
            {
                "bvid": r.bvid,
                "aid": r.aid,
                "title": r.title,
                "cover": r.cover,
                "duration": r.duration,
                "pubdate": r.pubdate,
                "owner_mid": r.owner_mid,
                "owner_name": r.owner_name,
                "partition_name": r.partition_name,
                "desc": r.desc,
            }
            for r in rows
        ],
    }


@router.get("/filtered")
def filtered(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    import time
    from datetime import datetime, timezone

    cutoff_dt = datetime.fromtimestamp(time.time() - days * 86400, tz=timezone.utc)
    q = (
        select(Action, Video)
        .join(Video, Video.id == Action.video_id)
        .where(Action.kind == ActionKind.filtered, Action.created_at >= cutoff_dt)
        .order_by(desc(Action.created_at))
        .limit(500)
    )
    out = []
    for action, video in db.execute(q).all():
        out.append(
            {
                "bvid": video.bvid,
                "aid": video.aid,
                "title": video.title,
                "cover": video.cover,
                "duration": video.duration,
                "pubdate": video.pubdate,
                "owner_mid": video.owner_mid,
                "owner_name": video.owner_name,
                "reason": action.reason,
                "filtered_at": action.created_at.isoformat(),
            }
        )
    return {"count": len(out), "items": out}
