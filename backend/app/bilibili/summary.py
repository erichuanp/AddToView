"""Bilibili's official AI conclusion endpoint."""

from __future__ import annotations

import logging
from typing import Any

from .client import BiliClient
from .wbi import signed_get_json

CONCLUSION_URL = "https://api.bilibili.com/x/web-interface/view/conclusion/get"

logger = logging.getLogger(__name__)


async def get_official_conclusion(client: BiliClient, *, bvid: str, cid: int) -> dict[str, Any] | None:
    """Returns the model_result dict or None if not available.

    用 WBI 签名调用 —— 不签名虽然不会报错，但偶尔返回 stale 数据（和字幕
    错配是同一类问题）。
    """
    try:
        payload = await signed_get_json(client, CONCLUSION_URL, {"bvid": bvid, "cid": cid})
    except Exception as exc:  # noqa: BLE001
        logger.info("conclusion fetch failed for %s: %s", bvid, exc)
        return None
    code = int(payload.get("code", -1))
    if code != 0:
        return None
    data = payload.get("data") or {}
    model_result = data.get("model_result") or {}
    code_inner = int(data.get("code", -1))
    # 0=success, 1=no summary detected, -1=unsupported
    if code_inner != 0:
        return None
    return {
        "summary": model_result.get("summary") or "",
        "outline": model_result.get("outline") or [],
    }
