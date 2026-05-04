"""AI-powered blacklist suggestions: scan recently-added videos that the user
removed, plus the most-filtered recent UP cluster, and propose new rules.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from ..ai.llm import LLMUnconfigured, chat
from ..db import get_db
from ..models import Action, ActionKind, BlacklistRule, Video, RuleKind

router = APIRouter()


# 给 LLM 的硬性结构：服务端用它约束输出 token，模型只能填空、形状错不了
_VALID_KINDS = [k.value for k in RuleKind]
_SUGGEST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": _VALID_KINDS},
                    "value": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["kind", "value", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["suggestions"],
    "additionalProperties": False,
}


@router.post("/blacklist/suggest")
async def suggest_rules(
    days: int = 30,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)

    # signals: videos that were 'added' then 'removed' (you regretted them)
    removed_q = (
        select(Video.bvid, Video.title, Video.owner_name, Video.owner_mid, Video.duration, Video.partition_name)
        .join(Action, Action.video_id == Video.id)
        .where(Action.kind == ActionKind.removed, Action.created_at >= cutoff)
        .limit(40)
    )
    removed_rows = list(db.execute(removed_q).all())

    # signals: most-filtered owners (the rules already work, just calibrate)
    top_owners = list(
        db.execute(
            select(Video.owner_name, Video.owner_mid, func.count(Action.id).label("c"))
            .join(Action, Action.video_id == Video.id)
            .where(Action.kind == ActionKind.filtered, Action.created_at >= cutoff)
            .group_by(Video.owner_name, Video.owner_mid)
            .order_by(desc("c"))
            .limit(10)
        ).all()
    )

    # current rules — so the AI doesn't propose dupes
    current_rules = list(db.execute(select(BlacklistRule)).scalars())
    current_summary = [
        f"{r.kind.value}={r.value!r}{' (disabled)' if not r.enabled else ''}"
        for r in current_rules
    ]

    if not removed_rows and not top_owners:
        return {"suggestions": [], "note": "尚无足够信号数据；先用一阵子再回来"}

    bullets: list[str] = []
    for v in removed_rows:
        bullets.append(
            f"- 已移除：bvid={v.bvid} | UP={v.owner_name}({v.owner_mid}) | dur={v.duration}s | tag={v.partition_name} | title={v.title[:80]}"
        )
    for o in top_owners:
        bullets.append(f"- 已过滤多次：UP={o[0]}(mid={o[1]}) × {o[2]}")

    sys_msg = (
        "你是一个B站观看习惯分析助手。基于用户的过滤/移除信号，提出 3~6 条新黑名单规则。"
        "每条规则的 kind 必须是以下之一：title_keyword | title_regex | owner_name | owner_mid | "
        "duration_lt | duration_gt | partition_tid | partition_name | tag_keyword。"
        "value 必须严格符合 kind 的格式（数字就用数字字符串）。每条配一个 reason 字段（中文，30 字以内）。"
        "不要建议已经存在的规则。严格输出 JSON：{\"suggestions\":[{\"kind\":...,\"value\":...,\"reason\":...}, ...]}。"
    )

    user_msg = (
        "已有规则:\n" + ("\n".join(current_summary) or "（空）") + "\n\n" +
        "近期信号:\n" + "\n".join(bullets[:60]) + "\n\n" +
        "请输出 JSON。"
    )

    try:
        text = await chat(
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=4000,
            json_schema=_SUGGEST_SCHEMA,
            schema_name="blacklist_suggestions",
        )
    except LLMUnconfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"AI suggest failed: {exc}") from exc

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return {"suggestions": [], "raw": text, "error": "AI 输出无法解析为 JSON"}

    valid: list[dict[str, Any]] = []
    valid_kinds = {k.value for k in RuleKind}
    seen_pairs: set[tuple[str, str]] = {(r.kind.value, r.value) for r in current_rules}

    for s in parsed.get("suggestions", []):
        kind = s.get("kind")
        value = str(s.get("value", "")).strip()
        if kind not in valid_kinds or not value:
            continue
        if (kind, value) in seen_pairs:
            continue
        valid.append(
            {
                "kind": kind,
                "value": value,
                "reason": s.get("reason", "")[:80],
            }
        )

    return {"suggestions": valid}
