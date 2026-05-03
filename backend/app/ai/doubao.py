"""Tiny Doubao (volcengine ark) chat client. OpenAI-compatible.

The full openai SDK is heavy; we only need chat.completions, so just hit the
endpoint with httpx. Same surface across feature branches so merges are clean.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..settings import settings

logger = logging.getLogger(__name__)


class DoubaoUnconfigured(RuntimeError):
    pass


async def chat(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.4,
    max_tokens: int = 600,
    timeout: float = 30.0,
) -> str:
    if not settings.doubao_api_key:
        raise DoubaoUnconfigured("DOUBAO_API_KEY is not set in backend/.env")

    payload = {
        "model": settings.doubao_model_id,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {settings.doubao_api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=timeout) as cli:
        r = await cli.post(settings.doubao_base_url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as exc:
        logger.error("doubao response shape unexpected: %s", data)
        raise RuntimeError(f"unexpected doubao response: {exc}") from exc
