from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..bilibili.client import BiliClient
from ..bilibili.login import get_nav
from ..models import Cookie
from ..settings import settings

logger = logging.getLogger(__name__)


def find_cookie_files() -> list[Path]:
    return sorted(settings.resolved_data_dir.glob("*_cookie.json"))


def load_cookie_file(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_cookie_file(uid: str, cookies: dict[str, str]) -> Path:
    path = settings.resolved_data_dir / f"{uid}_cookie.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    return path


def upsert_cookie_row(db: Session, cookies: dict[str, str]) -> Cookie:
    uid = cookies.get("DedeUserID", "")
    if not uid:
        raise ValueError("cookie missing DedeUserID")
    row = db.execute(select(Cookie).where(Cookie.dede_user_id == uid)).scalar_one_or_none()
    if row is None:
        row = Cookie(dede_user_id=uid)
        db.add(row)
    row.dede_user_id_ckmd5 = cookies.get("DedeUserID__ckMd5", "")
    row.sessdata = cookies.get("SESSDATA", "")
    row.bili_jct = cookies.get("bili_jct", "")
    row.expires_raw = str(cookies.get("Expires", "") or "")
    row.refresh_token = cookies.get("refresh_token", "") or ""
    row.is_active = True
    return row


def cookie_row_to_dict(row: Cookie) -> dict[str, str]:
    return {
        "DedeUserID": row.dede_user_id,
        "DedeUserID__ckMd5": row.dede_user_id_ckmd5,
        "SESSDATA": row.sessdata,
        "bili_jct": row.bili_jct,
    }


def get_active_cookie_row(db: Session) -> Cookie | None:
    return db.execute(
        select(Cookie).where(Cookie.is_active.is_(True)).order_by(Cookie.updated_at.desc())
    ).scalar_one_or_none()


async def validate_and_persist(db: Session, row: Cookie) -> bool:
    """Hit /nav, populate is_logged_in + uname. Returns True if logged in."""
    cookies = cookie_row_to_dict(row)
    async with BiliClient(cookies) as client:
        try:
            info = await get_nav(client)
        except Exception as exc:  # noqa: BLE001
            logger.warning("nav check failed: %s", exc)
            row.is_logged_in = False
            row.last_validated_at = datetime.now(tz=timezone.utc)
            return False
    row.is_logged_in = bool(info["logged_in"])
    row.uname = info["uname"] or row.uname
    row.last_validated_at = datetime.now(tz=timezone.utc)
    return row.is_logged_in


async def save_cookies_from_qrlogin(db: Session, jar: dict[str, str]) -> Cookie:
    """Persist a fresh cookie jar from QR-login: upsert DB row, write file, validate."""
    needed = {"SESSDATA", "bili_jct", "DedeUserID", "DedeUserID__ckMd5"}
    missing = needed - set(jar.keys())
    if missing:
        raise ValueError(f"qr-login response missing cookies: {sorted(missing)}")

    cookies = {k: jar[k] for k in needed}
    cookies["Expires"] = jar.get("Expires", "")  # not always present

    row = upsert_cookie_row(db, cookies)
    db.flush()
    save_cookie_file(row.dede_user_id, cookies)

    # single-active invariant: deactivate the others
    others = db.execute(select(Cookie).where(Cookie.id != row.id)).scalars().all()
    for o in others:
        o.is_active = False

    await validate_and_persist(db, row)
    return row


async def bootstrap_cookie_from_files(db: Session) -> Cookie | None:
    files = sorted(find_cookie_files(), key=lambda p: p.stat().st_mtime)
    if not files:
        return None
    latest_row: Cookie | None = None
    for path in files:
        try:
            cookies = load_cookie_file(path)
            row = upsert_cookie_row(db, cookies)
            latest_row = row  # last iteration wins; files sorted by mtime ASC
        except Exception as exc:  # noqa: BLE001
            logger.warning("skip cookie file %s: %s", path, exc)
    db.flush()
    if latest_row is not None:
        # single-active invariant: only the most-recent file's row stays active
        others = db.execute(select(Cookie).where(Cookie.id != latest_row.id)).scalars().all()
        for o in others:
            o.is_active = False
        await validate_and_persist(db, latest_row)
    return latest_row
