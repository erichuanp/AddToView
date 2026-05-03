from __future__ import annotations

import base64
import io
import logging
from typing import Any

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..bilibili.client import BiliClient
from ..bilibili.login import generate_qrcode, poll_qrcode
from ..db import get_db
from ..models import Cookie
from ..services.cookie import save_cookies_from_qrlogin

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/qrcode/start")
async def qrcode_start() -> dict[str, Any]:
    async with BiliClient() as client:
        data = await generate_qrcode(client)
    qr_url = data.get("url") or ""
    qrcode_key = data.get("qrcode_key") or ""
    if not qr_url or not qrcode_key:
        raise HTTPException(status_code=502, detail="bilibili didn't return a qrcode")

    img = qrcode.make(qr_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

    return {
        "qrcode_key": qrcode_key,
        "qr_data_uri": data_uri,
        "expires_in": 180,
    }


@router.get("/qrcode/poll")
async def qrcode_poll(
    qrcode_key: str = Query(..., min_length=8),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Poll bilibili. Map inner data.code → frontend-friendly status string."""
    async with BiliClient() as client:
        payload = await poll_qrcode(client, qrcode_key)
        data = payload.get("data") or {}
        inner_code = int(data.get("code", -1))
        message = data.get("message", "") or payload.get("message", "")

        if inner_code == 86101:
            return {"status": "pending", "message": "等待扫码…"}
        if inner_code == 86090:
            return {"status": "scanned", "message": "已扫码，请在手机上确认"}
        if inner_code == 86038:
            return {"status": "expired", "message": "二维码已失效"}
        if inner_code == 0:
            jar = client.jar_dict()
            try:
                row = await save_cookies_from_qrlogin(db, jar)
                db.commit()
            except ValueError as exc:
                logger.exception("qr-login persist failed")
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            return {
                "status": "ok",
                "message": "登录成功",
                "uname": row.uname,
                "mid": row.dede_user_id,
            }

        return {"status": "error", "message": message or f"unknown code {inner_code}"}


@router.post("/logout")
def logout(db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.execute(select(Cookie).where(Cookie.is_active.is_(True))).scalars().all()
    for r in rows:
        r.is_active = False
        r.is_logged_in = False
    db.commit()
    return {"ok": True, "deactivated": len(rows)}
