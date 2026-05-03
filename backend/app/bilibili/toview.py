from __future__ import annotations

from typing import Any

from .client import BiliClient

LIST_URL = "https://api.bilibili.com/x/v2/history/toview"
ADD_URL = "https://api.bilibili.com/x/v2/history/toview/add"
DEL_URL = "https://api.bilibili.com/x/v2/history/toview/del"
CLEAR_URL = "https://api.bilibili.com/x/v2/history/toview/clear"


async def list_watchlater(client: BiliClient) -> list[dict[str, Any]]:
    payload = await client.get_json(LIST_URL)
    data = client.check(payload)
    return data.get("list") or []


async def add_to_watchlater(client: BiliClient, bvid: str) -> dict[str, Any]:
    return await client.post_form(ADD_URL, {"bvid": bvid, "csrf": client.csrf})


async def remove_from_watchlater(client: BiliClient, *, aid: int | None = None, viewed: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {"csrf": client.csrf}
    if aid is not None:
        data["aid"] = aid
    if viewed:
        data["viewed"] = "true"
    return await client.post_form(DEL_URL, data)


async def clear_watchlater(client: BiliClient) -> dict[str, Any]:
    return await client.post_form(CLEAR_URL, {"csrf": client.csrf})
