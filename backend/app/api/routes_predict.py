from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..bilibili.client import BiliClient, BilibiliError
from ..bilibili import toview as toview_api
from .deps import require_cookie_dict

router = APIRouter()


@router.get("/watchlater")
async def predict_watchlater(
    cookies: dict[str, str] = Depends(require_cookie_dict),
) -> dict[str, Any]:
    """Estimate time to clear the watch later list under several assumptions."""
    async with BiliClient(cookies) as client:
        try:
            items = await toview_api.list_watchlater(client)
        except BilibiliError as exc:
            raise HTTPException(status_code=502, detail={"code": exc.code, "message": exc.message}) from exc

    raw_total = 0
    remaining_total = 0
    short_count = 0
    long_count = 0
    by_owner_dur: dict[str, int] = {}
    by_partition_dur: dict[str, int] = {}

    for it in items:
        dur = int(it.get("duration") or 0)
        progress = int(it.get("progress") or 0)
        if progress < 0:  # already watched
            continue
        raw_total += dur
        remaining = max(0, dur - progress) if progress > 0 else dur
        remaining_total += remaining
        if dur < 300:
            short_count += 1
        if dur > 1800:
            long_count += 1
        owner = (it.get("owner") or {}).get("name") or "(?)"
        by_owner_dur[owner] = by_owner_dur.get(owner, 0) + remaining

    top_owners = sorted(by_owner_dur.items(), key=lambda kv: kv[1], reverse=True)[:5]

    return {
        "count": len(items),
        "raw_total_seconds": raw_total,
        "remaining_total_seconds": remaining_total,
        "raw_total_pretty": _pretty(raw_total),
        "remaining_total_pretty": _pretty(remaining_total),
        "short_videos": short_count,
        "long_videos": long_count,
        "top_owners_by_time": [{"name": name, "seconds": secs, "pretty": _pretty(secs)} for name, secs in top_owners],
    }


def _pretty(secs: int) -> str:
    if secs < 60:
        return f"{secs}s"
    m = secs // 60
    if m < 60:
        return f"{m}min"
    h = m // 60
    mr = m % 60
    if h < 24:
        return f"{h}h{mr:02d}min" if mr else f"{h}h"
    d = h // 24
    hr = h % 24
    return f"{d}天{hr}h" if hr else f"{d}天"
