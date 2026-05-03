from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

WEB_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
)


class BilibiliError(Exception):
    def __init__(self, code: int, message: str, payload: Any = None) -> None:
        super().__init__(f"bilibili error {code}: {message}")
        self.code = code
        self.message = message
        self.payload = payload


def cookie_dict(c: dict[str, str]) -> dict[str, str]:
    return {
        "DedeUserID": c.get("DedeUserID", ""),
        "DedeUserID__ckMd5": c.get("DedeUserID__ckMd5", ""),
        "SESSDATA": c.get("SESSDATA", ""),
        "bili_jct": c.get("bili_jct", ""),
    }


class BiliClient:
    """Tiny async wrapper around httpx that injects cookies + UA + Referer."""

    def __init__(self, cookies: dict[str, str] | None = None, timeout: float = 15.0) -> None:
        self._cookies = cookie_dict(cookies or {})
        self._timeout = timeout
        self._headers = {
            "User-Agent": WEB_UA,
            "Referer": "https://www.bilibili.com/",
            "Origin": "https://www.bilibili.com",
        }

    @property
    def csrf(self) -> str:
        return self._cookies.get("bili_jct", "")

    def update_cookies(self, cookies: dict[str, str]) -> None:
        self._cookies = cookie_dict(cookies)

    async def __aenter__(self) -> "BiliClient":
        self._client = httpx.AsyncClient(
            headers=self._headers,
            cookies=self._cookies,
            timeout=self._timeout,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self._client.aclose()

    async def get_json(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        r = await self._client.get(url, params=params)
        r.raise_for_status()
        return r.json()

    async def post_form(self, url: str, data: dict[str, Any]) -> dict[str, Any]:
        r = await self._client.post(url, data=data)
        r.raise_for_status()
        return r.json()

    def jar_dict(self) -> dict[str, str]:
        """Live cookie jar after the most recent request — captures Set-Cookie."""
        return {k: v for k, v in self._client.cookies.items()}

    @staticmethod
    def check(payload: dict[str, Any]) -> dict[str, Any]:
        code = int(payload.get("code", -1))
        if code != 0:
            raise BilibiliError(code, payload.get("message", ""), payload)
        return payload.get("data", {}) or {}
