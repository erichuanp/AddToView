from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Setting

router = APIRouter()

DEFAULTS: dict[str, str] = {
    "default_sync_days": "7",
    "stats_window_days": "30",
}


class SettingPut(BaseModel):
    value: str


def _get(db: Session, key: str) -> str:
    row = db.get(Setting, key)
    if row is not None:
        return row.value
    return DEFAULTS.get(key, "")


def _put(db: Session, key: str, value: str) -> None:
    row = db.get(Setting, key)
    if row is None:
        row = Setting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
    db.commit()


@router.get("/all")
def list_all(db: Session = Depends(get_db)) -> dict[str, Any]:
    out: dict[str, str] = {}
    for k in DEFAULTS:
        out[k] = _get(db, k)
    return {"items": out}


@router.get("/{key}")
def get_one(key: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    if key not in DEFAULTS:
        raise HTTPException(status_code=404, detail=f"unknown setting key: {key}")
    return {"key": key, "value": _get(db, key)}


@router.put("/{key}")
def put_one(key: str, body: SettingPut, db: Session = Depends(get_db)) -> dict[str, Any]:
    if key not in DEFAULTS:
        raise HTTPException(status_code=404, detail=f"unknown setting key: {key}")
    _put(db, key, body.value.strip())
    return {"key": key, "value": _get(db, key)}
