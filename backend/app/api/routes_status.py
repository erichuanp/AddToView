from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import __version__
from ..bilibili.client import BiliClient
from ..bilibili.login import get_nav
from ..db import get_db
from ..schemas import HealthOut, StatusOut
from ..services.cookie import cookie_row_to_dict, get_active_cookie_row

router = APIRouter()


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(ok=True, version=__version__)


@router.get("/status", response_model=StatusOut)
async def status(db: Session = Depends(get_db)) -> StatusOut:
    row = get_active_cookie_row(db)
    if row is None or not row.sessdata:
        return StatusOut(logged_in=False, cookie_present=False)

    cookies = cookie_row_to_dict(row)
    async with BiliClient(cookies) as client:
        try:
            info = await get_nav(client)
        except Exception:  # noqa: BLE001
            info = {"logged_in": False, "mid": None, "uname": "", "vip_status": 0}

    row.is_logged_in = bool(info.get("logged_in"))
    if info.get("uname"):
        row.uname = info["uname"]
    db.commit()

    return StatusOut(
        logged_in=row.is_logged_in,
        mid=info.get("mid"),
        uname=row.uname,
        vip_status=int(info.get("vip_status") or 0),
        cookie_present=True,
    )
