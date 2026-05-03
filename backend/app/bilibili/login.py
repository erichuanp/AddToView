from __future__ import annotations

from typing import Any

from .client import BiliClient

NAV_URL = "https://api.bilibili.com/x/web-interface/nav"
QR_GENERATE_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
QR_POLL_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"


async def get_nav(client: BiliClient) -> dict[str, Any]:
    payload = await client.get_json(NAV_URL)
    code = int(payload.get("code", -1))
    data = payload.get("data") or {}
    is_logged_in = code == 0 and bool(data.get("isLogin"))
    return {
        "code": code,
        "logged_in": is_logged_in,
        "mid": int(data.get("mid")) if data.get("mid") else None,
        "uname": data.get("uname") or "",
        "vip_status": int(data.get("vipStatus") or 0),
        "raw": data,
    }


async def generate_qrcode(client: BiliClient) -> dict[str, Any]:
    payload = await client.get_json(QR_GENERATE_URL)
    return client.check(payload)


async def poll_qrcode(client: BiliClient, qrcode_key: str) -> dict[str, Any]:
    """Poll endpoint. Outer code is always 0; the meaningful status is in data.code.

    data.code values:
        0     login successful (cookies set on the response)
        86038 QR expired
        86090 scanned, not confirmed
        86101 not yet scanned
    """
    payload = await client.get_json(QR_POLL_URL, params={"qrcode_key": qrcode_key})
    return payload  # caller looks at data.code
