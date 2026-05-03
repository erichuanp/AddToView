from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..bilibili.client import BilibiliError
from ..db import get_db
from ..models import Action, ActionKind, Setting, Video
from ..services.ingest import (
    add_unfiltered_to_watchlater,
    ingest_dynamic_feed,
)
from .deps import require_cookie_dict

router = APIRouter()


# ---- last_sync_at helpers ------------------------------------------------

def _get_last_sync_at(db: Session) -> int | None:
    row = db.get(Setting, "last_sync_at")
    if row and row.value:
        try:
            return int(row.value)
        except ValueError:
            return None
    return None


def _set_last_sync_at(db: Session, ts: int) -> None:
    row = db.get(Setting, "last_sync_at")
    if row is None:
        db.add(Setting(key="last_sync_at", value=str(ts)))
    else:
        row.value = str(ts)
    db.commit()


def _resolve_cutoff(db: Session, days: int | None) -> int:
    """Return the pubdate cutoff for the next sync.

    - If `last_sync_at` is set, use it (incremental sync).
    - Else require `days`. Raises HTTP 400 with `first_sync` marker so the
      frontend can prompt the user.
    """
    last_sync = _get_last_sync_at(db)
    if last_sync is not None:
        return last_sync
    if days is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "first_sync",
                "message": "首次同步，请指定回溯天数",
            },
        )
    return int(time.time()) - days * 86400


# ---- routes --------------------------------------------------------------


@router.get("/sync-status")
def sync_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    last_sync = _get_last_sync_at(db)
    return {
        "has_last_sync": last_sync is not None,
        "last_sync_at": last_sync,
    }


@router.post("/sync")
async def sync(
    days: int | None = Query(default=None, ge=1, le=60),
    max_pages: int = Query(default=20, ge=1, le=60),
    cookies: dict[str, str] = Depends(require_cookie_dict),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    cutoff = _resolve_cutoff(db, days)
    started = int(time.time())
    try:
        result = await ingest_dynamic_feed(
            db, cookies, cutoff_pubdate=cutoff, max_pages=max_pages
        )
    except BilibiliError as exc:
        raise HTTPException(
            status_code=502, detail={"code": exc.code, "message": exc.message}
        ) from exc
    _set_last_sync_at(db, started)
    return result


@router.post("/auto-add")
async def auto_add(
    days: int | None = Query(default=None, ge=1, le=60),
    cookies: dict[str, str] = Depends(require_cookie_dict),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    cutoff = _resolve_cutoff(db, days)
    started = int(time.time())

    try:
        sync_result = await ingest_dynamic_feed(db, cookies, cutoff_pubdate=cutoff)
    except BilibiliError as exc:
        raise HTTPException(
            status_code=502, detail={"code": exc.code, "message": exc.message}
        ) from exc
    _set_last_sync_at(db, started)

    add_result = await add_unfiltered_to_watchlater(db, cookies, since_pubdate=cutoff)
    return {"sync": sync_result, "add": add_result}


@router.get("/pending")
def pending(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Videos seen during sync that have NOT been filtered, added, or errored.

    These are the queue of videos that 一键添加 would push to watch later.
    """
    cutoff = int(time.time()) - days * 86400

    acted_subq = (
        select(Action.video_id)
        .where(Action.kind.in_([ActionKind.filtered, ActionKind.added, ActionKind.error]))
        .distinct()
    )

    rows = list(
        db.execute(
            select(Video)
            .where(Video.pubdate >= cutoff, ~Video.id.in_(acted_subq))
            .order_by(Video.pubdate.desc())
            .limit(500)
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
                "desc": r.desc,
                "owner_mid": r.owner_mid,
                "owner_name": r.owner_name,
                "partition_name": r.partition_name,
            }
            for r in rows
        ],
    }


@router.get("/recent")
def recent(
    days: int = Query(default=7, ge=1, le=60),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
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
    cutoff_dt = datetime.fromtimestamp(time.time() - days * 86400, tz=timezone.utc)
    # one row per filtered action — but we want one entry per *video*; ordered
    # newest-first so the first occurrence is the most-recent filter event.
    q = (
        select(Action, Video)
        .join(Video, Video.id == Action.video_id)
        .where(Action.kind == ActionKind.filtered, Action.created_at >= cutoff_dt)
        .order_by(desc(Action.created_at))
        .limit(2000)
    )
    seen: set[int] = set()
    out: list[dict[str, Any]] = []
    for action, video in db.execute(q).all():
        if video.id in seen:
            continue
        seen.add(video.id)
        out.append(
            {
                "bvid": video.bvid,
                "aid": video.aid,
                "title": video.title,
                "cover": video.cover,
                "duration": video.duration,
                "pubdate": video.pubdate,
                "desc": video.desc,
                "owner_mid": video.owner_mid,
                "owner_name": video.owner_name,
                "partition_name": video.partition_name,
                "reason": action.reason,
                "filtered_at": action.created_at.isoformat(),
            }
        )
        if len(out) >= 500:
            break
    return {"count": len(out), "items": out}
