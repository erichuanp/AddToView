from __future__ import annotations

from typing import Any

from .client import BiliClient

VIEW_URL = "https://api.bilibili.com/x/web-interface/view"
TAG_URL = "https://api.bilibili.com/x/tag/archive/tags"


async def get_view(client: BiliClient, *, bvid: str | None = None, aid: int | None = None) -> dict[str, Any]:
    if not bvid and not aid:
        raise ValueError("either bvid or aid is required")
    params: dict[str, Any] = {}
    if bvid:
        params["bvid"] = bvid
    elif aid:
        params["aid"] = aid
    payload = await client.get_json(VIEW_URL, params=params)
    return client.check(payload)


async def get_tags(client: BiliClient, *, bvid: str | None = None, aid: int | None = None) -> list[str]:
    params: dict[str, Any] = {}
    if bvid:
        params["bvid"] = bvid
    elif aid:
        params["aid"] = aid
    payload = await client.get_json(TAG_URL, params=params)
    data = payload.get("data") or []
    return [t.get("tag_name") or "" for t in data if t.get("tag_name")]
