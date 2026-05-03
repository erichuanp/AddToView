from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import BlacklistRule, RuleKind
from ..services.ingest import dry_run_blacklist

router = APIRouter()


class RuleIn(BaseModel):
    kind: RuleKind
    value: str
    note: str = ""
    enabled: bool = True


class RulePatch(BaseModel):
    value: str | None = None
    note: str | None = None
    enabled: bool | None = None


def _serialize(r: BlacklistRule) -> dict[str, Any]:
    return {
        "id": r.id,
        "kind": r.kind.value,
        "value": r.value,
        "note": r.note,
        "enabled": r.enabled,
        "hit_count": r.hit_count,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("")
def list_rules(db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = list(db.execute(select(BlacklistRule).order_by(BlacklistRule.id.desc())).scalars())
    return {"count": len(rows), "items": [_serialize(r) for r in rows]}


@router.post("")
def create_rule(payload: RuleIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    rule = BlacklistRule(
        kind=payload.kind,
        value=payload.value.strip(),
        note=payload.note,
        enabled=payload.enabled,
    )
    db.add(rule)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="rule with same kind+value already exists")
    db.refresh(rule)
    return _serialize(rule)


@router.patch("/{rule_id}")
def update_rule(
    rule_id: int, patch: RulePatch, db: Session = Depends(get_db)
) -> dict[str, Any]:
    rule = db.get(BlacklistRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="rule not found")
    if patch.value is not None:
        rule.value = patch.value.strip()
    if patch.note is not None:
        rule.note = patch.note
    if patch.enabled is not None:
        rule.enabled = patch.enabled
    db.commit()
    db.refresh(rule)
    return _serialize(rule)


@router.delete("/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    rule = db.get(BlacklistRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="rule not found")
    db.delete(rule)
    db.commit()
    return {"ok": True}


@router.get("/kinds")
def list_kinds() -> dict[str, Any]:
    return {
        "kinds": [
            {"value": k.value, "label": _human_label(k), "hint": _kind_hint(k)}
            for k in RuleKind
        ]
    }


@router.post("/dry-run")
def dry_run(days: int = Query(default=7, ge=1, le=60), db: Session = Depends(get_db)) -> dict[str, Any]:
    return dry_run_blacklist(db, days=days)


def _kind_hint(k: RuleKind) -> str:
    return {
        RuleKind.title_keyword: "标题中包含此字符串则命中（不区分大小写）",
        RuleKind.title_regex: "Python 正则；标题匹配则命中（不区分大小写）",
        RuleKind.owner_name: "UP 主名称完全相等则命中",
        RuleKind.owner_mid: "UP 主 UID（数字）",
        RuleKind.duration_lt: "短于 N 秒（用于过滤 Shorts）",
        RuleKind.duration_gt: "长于 N 秒（用于过滤超长直播录像）",
        RuleKind.partition_tid: "分区 ID（数字）",
        RuleKind.partition_name: "分区名包含字符串",
        RuleKind.tag_keyword: "视频标签包含字符串（同步会变慢）",
    }[k]


def _human_label(k: RuleKind) -> str:
    return {
        RuleKind.title_keyword: "标题包含关键词",
        RuleKind.title_regex: "标题匹配正则",
        RuleKind.owner_name: "UP主名称（精确）",
        RuleKind.owner_mid: "UP主UID",
        RuleKind.duration_lt: "时长小于（秒）",
        RuleKind.duration_gt: "时长大于（秒）",
        RuleKind.partition_tid: "分区TID",
        RuleKind.partition_name: "分区名包含",
        RuleKind.tag_keyword: "标签包含",
    }[k]
