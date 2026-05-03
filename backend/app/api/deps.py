from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Cookie
from ..services.cookie import cookie_row_to_dict, get_active_cookie_row


def db_dep() -> Session:
    return Depends(get_db)  # type: ignore[return-value]


def require_cookie(db: Session = Depends(get_db)) -> Cookie:
    row = get_active_cookie_row(db)
    if row is None or not row.sessdata:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="no active cookie. login via /api/login/qrcode/start",
        )
    return row


def require_cookie_dict(row: Cookie = Depends(require_cookie)) -> dict[str, str]:
    return cookie_row_to_dict(row)
