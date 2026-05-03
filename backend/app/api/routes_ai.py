from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.doubao import DoubaoUnconfigured, chat
from ..bilibili.client import BiliClient, BilibiliError
from ..bilibili.summary import get_official_conclusion
from ..bilibili.video import get_view
from ..db import get_db
from ..models import Video
from .deps import require_cookie_dict

router = APIRouter()


@router.get("/summary/{bvid}")
async def video_summary(
    bvid: str,
    db: Session = Depends(get_db),
    cookies: dict[str, str] = Depends(require_cookie_dict),
) -> dict[str, Any]:
    """Best-effort video summary. Tries Bilibili's official conclusion, then
    falls back to Doubao on title + desc + uploader."""

    # 1. ensure we know the video metadata (title, desc, cid)
    async with BiliClient(cookies) as client:
        try:
            view = await get_view(client, bvid=bvid)
        except BilibiliError as exc:
            raise HTTPException(status_code=502, detail={"code": exc.code, "message": exc.message}) from exc
        title = view.get("title") or ""
        desc = view.get("desc") or ""
        cid = int(view.get("cid") or 0)
        owner = (view.get("owner") or {}).get("name") or ""
        duration = int(view.get("duration") or 0)

        # 2. try bilibili's official summary
        official = await get_official_conclusion(client, bvid=bvid, cid=cid) if cid else None

    if official and official.get("summary"):
        return {
            "source": "bilibili",
            "summary": official["summary"],
            "outline": official.get("outline") or [],
            "title": title,
        }

    # 3. fall back to Doubao using just title + desc (no transcript)
    if not desc and not title:
        raise HTTPException(status_code=404, detail="no metadata to summarize")

    try:
        prompt_user = (
            f"以下是一个B站视频的元信息，请用中文给一个 2~3 句话的摘要、抓住重点、不要复读标题。\n\n"
            f"UP主：{owner}\n标题：{title}\n时长：{duration} 秒\n简介：{desc[:1500]}"
        )
        try:
            text = await chat(
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个简洁的视频摘要助手，输出严格的 2~3 句中文摘要，不要标题党。",
                    },
                    {"role": "user", "content": prompt_user},
                ],
                max_tokens=300,
            )
        except DoubaoUnconfigured as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"AI summary failed: {exc}") from exc

    return {
        "source": "doubao",
        "summary": text,
        "outline": [],
        "title": title,
    }


@router.post("/triage")
async def triage_watchlater(
    db: Session = Depends(get_db),
    cookies: dict[str, str] = Depends(require_cookie_dict),
) -> dict[str, Any]:
    """Ask the AI to bucket each video in the user's watch later into one of
    {must_watch, maybe, skip} based on title + UP. Returns advisory only."""
    from ..bilibili import toview as toview_api

    async with BiliClient(cookies) as client:
        try:
            items = await toview_api.list_watchlater(client)
        except BilibiliError as exc:
            raise HTTPException(status_code=502, detail={"code": exc.code, "message": exc.message}) from exc

    bullets = []
    for it in items[:60]:  # token-budget cap
        owner = (it.get("owner") or {}).get("name") or ""
        bullets.append(
            f"- bvid={it.get('bvid')} | UP={owner} | dur={it.get('duration')}s | title={it.get('title','')[:80]}"
        )

    if not bullets:
        return {"buckets": {"must_watch": [], "maybe": [], "skip": []}, "note": "稍后再看是空的"}

    prompt = (
        "下面是 B 站某用户的稍后再看清单。请把每个视频按你对该 UP 主+标题的直觉分入三类：\n"
        "must_watch（强烈推荐看）、maybe（看心情）、skip（建议跳过）。\n"
        "输出严格 JSON，形如 {\"must_watch\":[\"BV...\", ...], \"maybe\":[...], \"skip\":[...]}。\n\n"
        "清单：\n" + "\n".join(bullets)
    )
    try:
        text = await chat(
            messages=[
                {"role": "system", "content": "你输出严格 JSON，不要任何解释或 markdown。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1200,
        )
    except DoubaoUnconfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"AI triage failed: {exc}") from exc

    import json

    parsed: dict[str, Any] = {}
    try:
        # tolerate fenced ```json ... ```
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return {"raw": text, "error": "AI 返回无法解析为 JSON", "buckets": {}}

    return {"buckets": parsed, "raw_truncated": text[:200]}
