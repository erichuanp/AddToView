"""Bilibili's official AI conclusion endpoint.

Requires Wbi signing — but the conclusion endpoint accepts unsigned requests
when called with a valid SESSDATA cookie + Referer; failure modes are graceful
(we just fall back to our own AI). For a robust impl, sign with Wbi.

This module avoids implementing wbi for now — it tries the call unsigned and
returns None if it fails.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .client import BiliClient

CONCLUSION_URL = "https://api.bilibili.com/x/web-interface/view/conclusion/get"

logger = logging.getLogger(__name__)


async def get_official_conclusion(client: BiliClient, *, bvid: str, cid: int) -> dict[str, Any] | None:
    """Returns the model_result dict or None if not available."""
    params = {
        "bvid": bvid,
        "cid": cid,
        "wts": int(time.time()),
    }
    try:
        payload = await client.get_json(CONCLUSION_URL, params=params)
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
