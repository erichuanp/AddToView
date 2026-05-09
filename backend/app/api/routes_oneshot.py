"""One-shot CLI endpoint: GET /addtoview/ runs sync + auto-add for the
active cookie user with no parameters, returning a human-readable text
message. Designed to be hit with `curl localhost:5173/addtoview/` or
`curl localhost:8788/addtoview/`.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from ..bilibili.client import BiliClient, BilibiliError
from ..db import get_db
from ..models import Cookie, Setting
from ..services.cookie import cookie_row_to_dict, get_active_cookie_row
from ..services.ingest import run_auto_add_pipeline

router = APIRouter()

# fallback window when there's no `last_sync_at` saved yet
DEFAULT_FIRST_RUN_DAYS = 3


def _get_last_sync_at(db: Session) -> int | None:
    row = db.get(Setting, "last_sync_at")
    if row and row.value:
        try:
            return int(row.value)
        except ValueError:
            return None
    return None


def _set_last_sync_at(db: Session, ts: int) -> None:
    row = db.get(Setting, "last_sync_at")
    if row is None:
        db.add(Setting(key="last_sync_at", value=str(ts)))
    else:
        row.value = str(ts)
    db.commit()


@router.get("/", response_class=PlainTextResponse)
@router.get("", response_class=PlainTextResponse)
async def addtoview_oneshot(request: Request, db: Session = Depends(get_db)) -> PlainTextResponse:
    cookie_row: Cookie | None = get_active_cookie_row(db)
    if cookie_row is None or not cookie_row.sessdata:
        return PlainTextResponse(
            "AddToView: 未找到可用的 cookie，请先在网页扫码登录。\n",
            status_code=401,
        )

    cookies = cookie_row_to_dict(cookie_row)

    last_sync = _get_last_sync_at(db)
    if last_sync is not None:
        cutoff = last_sync
    else:
        cutoff = int(time.time()) - DEFAULT_FIRST_RUN_DAYS * 86400

    started = int(time.time())
    try:
        result = await run_auto_add_pipeline(db, cookies, cutoff_pubdate=cutoff)
    except BilibiliError as exc:
        return PlainTextResponse(
            f"AddToView: 同步失败 (code {exc.code}: {exc.message})\n",
            status_code=502,
        )
    _set_last_sync_at(db, started)

    sync_result = result["sync"]
    add_result = result["add"]
    cleared = result["cleared_viewed"]

    # try to get a friendly username; fall back to mid only
    uname = cookie_row.uname or "(未知)"
    mid = cookie_row.dede_user_id

    added_n = len(add_result["added"])
    skipped_n = len(add_result["skipped"])
    error_n = len(add_result["errors"])
    filtered_n = sync_result.get("filtered", 0)

    msg = (
        f"AddToView: 已添加 {added_n} 个视频到 {uname}(UID: {mid}) 的稍后再看列表"
    )
    extras: list[str] = []
    if filtered_n:
        extras.append(f"{filtered_n} 个被黑名单过滤")
    if skipped_n:
        extras.append(f"{skipped_n} 个跳过")
    if error_n:
        extras.append(f"{error_n} 个出错")
    if cleared.get("ok"):
        extras.append("已清理已观看")
    elif cleared.get("error") or (cleared.get("code") not in (0, None)):
        reason = cleared.get("error") or f"code {cleared.get('code')}"
        extras.append(f"清理已观看失败({reason})")
    if extras:
        msg += "（" + "；".join(extras) + "）"
    msg += "\n"
    return PlainTextResponse(msg)
