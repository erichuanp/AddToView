from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import BlacklistRule, RuleKind, Setting

router = APIRouter()


@router.get("/blacklist.json")
def export_blacklist(db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = list(db.execute(select(BlacklistRule).order_by(BlacklistRule.id)).scalars())
    return {
        "version": 1,
        "kind": "blacklist",
        "rules": [
            {
                "kind": r.kind.value,
                "value": r.value,
                "note": r.note,
                "enabled": r.enabled,
                "hit_count": r.hit_count,
            }
            for r in rows
        ],
    }


@router.get("/settings.json")
def export_settings(db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = list(db.execute(select(Setting)).scalars())
    return {
        "version": 1,
        "kind": "settings",
        "items": {r.key: r.value for r in rows},
    }


class BlacklistImportItem(BaseModel):
    kind: str
    value: str
    note: str = ""
    enabled: bool = True


class BlacklistImportPayload(BaseModel):
    rules: list[BlacklistImportItem]
    mode: str = "merge"  # 'merge' | 'replace'


@router.post("/blacklist/import")
def import_blacklist(
    payload: BlacklistImportPayload, db: Session = Depends(get_db)
) -> dict[str, Any]:
    valid_kinds = {k.value for k in RuleKind}
    if payload.mode not in ("merge", "replace"):
        raise HTTPException(status_code=400, detail="mode must be 'merge' or 'replace'")

    if payload.mode == "replace":
        db.query(BlacklistRule).delete()
        db.flush()

    inserted = 0
    skipped = 0
    for item in payload.rules:
        if item.kind not in valid_kinds:
            skipped += 1
            continue
        try:
            db.add(
                BlacklistRule(
                    kind=RuleKind(item.kind),
                    value=item.value.strip(),
                    note=item.note,
                    enabled=item.enabled,
                )
            )
            db.flush()
            inserted += 1
        except IntegrityError:
            db.rollback()
            skipped += 1

    db.commit()
    return {"inserted": inserted, "skipped": skipped, "mode": payload.mode}
