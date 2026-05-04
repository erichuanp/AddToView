"""B站 WBI 签名。

很多 B站 web API（看点 conclusion/get、player/wbi/v2 等）需要 WBI 签名
才能正常返回数据。不签名时 -403「访问权限不足」。

签名流程（B站 web 客户端公开实现）：
  1. /x/web-interface/nav 返回 wbi_img.{img_url, sub_url}
  2. 取 URL 文件名（去 path、去扩展名）得到 imgKey 和 subKey
  3. imgKey + subKey 拼起来按 MIXIN_KEY_ENC_TAB 重排，取前 32 字符 = mixin_key
  4. 给参数加 wts（unix 时间戳），按 key 字典序排序，URL-encode 拼接
  5. 拼上 mixin_key 求 md5 = w_rid

img_key/sub_key 一天换一次。我们做了 6h 缓存避免每次都打 nav。
"""

from __future__ import annotations

import hashlib
import time
import urllib.parse
from typing import Any

from .client import BiliClient

NAV_URL = "https://api.bilibili.com/x/web-interface/nav"

MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]

# 进程内缓存：(img_key, sub_key, fetched_at)。6h TTL。
_cache: tuple[str, str, float] | None = None
_TTL = 6 * 3600


async def get_wbi_keys(client: BiliClient) -> tuple[str, str]:
    global _cache
    now = time.time()
    if _cache is not None and now - _cache[2] < _TTL:
        return _cache[0], _cache[1]
    payload = await client.get_json(NAV_URL)
    data = payload.get("data") or {}
    wbi = data.get("wbi_img") or {}
    img_url = wbi.get("img_url") or ""
    sub_url = wbi.get("sub_url") or ""
    img_key = img_url.split("/")[-1].split(".")[0] if img_url else ""
    sub_key = sub_url.split("/")[-1].split(".")[0] if sub_url else ""
    if not img_key or not sub_key:
        raise RuntimeError("WBI keys missing from nav response")
    _cache = (img_key, sub_key, now)
    return img_key, sub_key


def _mixin_key(img_key: str, sub_key: str) -> str:
    raw = img_key + sub_key
    return "".join(raw[i] for i in MIXIN_KEY_ENC_TAB if i < len(raw))[:32]


def sign_params(params: dict[str, Any], img_key: str, sub_key: str) -> dict[str, Any]:
    """按 WBI 规则给 params 加 wts + w_rid，返回新 dict（不改原 dict）。"""
    mixin = _mixin_key(img_key, sub_key)
    signed = {**params, "wts": int(time.time())}
    sorted_keys = sorted(signed)
    query = "&".join(
        f"{k}={urllib.parse.quote(str(signed[k]), safe='')}" for k in sorted_keys
    )
    signed["w_rid"] = hashlib.md5((query + mixin).encode("utf-8")).hexdigest()
    return signed


async def signed_get_json(
    client: BiliClient, url: str, params: dict[str, Any]
) -> dict[str, Any]:
    """便捷：自动拿 keys 并签名后 GET。"""
    img_key, sub_key = await get_wbi_keys(client)
    return await client.get_json(url, params=sign_params(params, img_key, sub_key))
