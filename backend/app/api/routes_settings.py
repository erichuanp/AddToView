from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Setting

router = APIRouter()

DEFAULTS: dict[str, str] = {
    "last_sync_at": "",
    # legacy single-config keys — kept for backward read; new writes use slots
    "llm_base_url": "",
    "llm_model_id": "",
    "llm_api_key": "",
    # multi-slot LLM config — written via /api/ai/llm/slots, not via PUT settings
    "llm_slots": "",
    "llm_active_slot": "0",
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
    value = body.value.strip()
    # normalize the LLM base url so /chat/completions is always appended
    if key == "llm_base_url" and value:
        from ..ai.llm import normalize_base_url
        value = normalize_base_url(value)
    _put(db, key, value)
    return {"key": key, "value": _get(db, key)}
