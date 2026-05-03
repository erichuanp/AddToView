from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..bilibili.client import BiliClient, BilibiliError
from ..bilibili import toview as toview_api
from ..db import get_db
from ..models import Action, ActionKind, Video
from .deps import require_cookie_dict

router = APIRouter()


@router.get("")
async def get_list(cookies: dict[str, str] = Depends(require_cookie_dict)) -> dict[str, Any]:
    async with BiliClient(cookies) as client:
        try:
            items = await toview_api.list_watchlater(client)
        except BilibiliError as exc:
            raise HTTPException(status_code=502, detail={"code": exc.code, "message": exc.message}) from exc

    out = []
    for it in items:
        owner = it.get("owner") or {}
        stat = it.get("stat") or {}
        out.append(
            {
                "bvid": it.get("bvid") or "",
                "aid": int(it.get("aid") or 0) or None,
                "title": it.get("title") or "",
                "cover": it.get("pic") or "",
                "duration": int(it.get("duration") or 0),
                "pubdate": int(it.get("pubdate") or 0),
                "desc": it.get("desc") or "",
                "owner_mid": int(owner.get("mid") or 0) or None,
                "owner_name": owner.get("name") or "",
                "progress": int(it.get("progress") or 0),
                "add_at": int(it.get("add_at") or 0),
                "stat_play": int(stat.get("view") or 0),
                "stat_like": int(stat.get("like") or 0),
                "stat_coin": int(stat.get("coin") or 0),
                "stat_favorite": int(stat.get("favorite") or 0),
                "stat_share": int(stat.get("share") or 0),
                "stat_danmaku": int(stat.get("danmaku") or 0),
                "stat_reply": int(stat.get("reply") or 0),
            }
        )
    return {"count": len(out), "items": out}


@router.post("/add")
async def add(
    bvid: str = Query(..., min_length=2),
    cookies: dict[str, str] = Depends(require_cookie_dict),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    async with BiliClient(cookies) as client:
        payload = await toview_api.add_to_watchlater(client, bvid)
    code = int(payload.get("code", -1))
    # don't fail the user-facing request on log error
    try:
        v = db.execute(select(Video).where(Video.bvid == bvid)).scalar_one_or_none()
        if v and code in (0, 90002, 90005):
            db.add(Action(video_id=v.id, kind=ActionKind.added, reason="manual"))
            db.commit()
    except Exception:
        db.rollback()
    return payload


@router.post("/remove")
async def remove(
    aid: int | None = Query(default=None),
    bvid: str | None = Query(default=None),
    viewed: bool = Query(default=False),
    cookies: dict[str, str] = Depends(require_cookie_dict),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    async with BiliClient(cookies) as client:
        payload = await toview_api.remove_from_watchlater(client, aid=aid, viewed=viewed)
    try:
        if int(payload.get("code", -1)) == 0:
            if viewed:
                # bulk-remove watched: log a single placeholder action
                pass
            else:
                v = None
                if bvid:
                    v = db.execute(select(Video).where(Video.bvid == bvid)).scalar_one_or_none()
                elif aid:
                    v = db.execute(select(Video).where(Video.aid == aid)).scalar_one_or_none()
                if v:
                    db.add(Action(video_id=v.id, kind=ActionKind.removed, reason="manual"))
                    db.commit()
    except Exception:
        db.rollback()
    return payload


@router.post("/clear")
async def clear(cookies: dict[str, str] = Depends(require_cookie_dict)) -> dict[str, Any]:
    async with BiliClient(cookies) as client:
        return await toview_api.clear_watchlater(client)
