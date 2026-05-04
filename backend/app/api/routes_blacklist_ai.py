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
        select(
            Video.bvid, Video.title, Video.owner_name, Video.owner_mid,
            Video.duration, Video.partition_name, Video.pubdate, Video.desc,
        )
        .join(Action, Action.video_id == Video.id)
        .where(Action.kind == ActionKind.removed, Action.created_at >= cutoff)
        .limit(40)
    )
    removed_rows = list(db.execute(removed_q).all())

    # signals: 反复命中黑名单的 UP（命中 ≥3 次才算稳定信号，过滤掉偶发噪音）
    top_owners = list(
        db.execute(
            select(Video.owner_name, Video.owner_mid, func.count(Action.id).label("c"))
            .join(Action, Action.video_id == Video.id)
            .where(Action.kind == ActionKind.filtered, Action.created_at >= cutoff)
            .group_by(Video.owner_name, Video.owner_mid)
            .having(func.count(Action.id) >= 3)
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

    def _year(ts: int) -> str:
        if not ts:
            return "?"
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y")

    bullets: list[str] = []
    for v in removed_rows:
        long_tag = "（长视频）" if v.duration >= 1800 else ("（短视频）" if v.duration <= 60 else "")
        desc_clip = (v.desc or "").strip().replace("\n", " ")[:60]
        bullets.append(
            f"- 已移除：UP={v.owner_name}(mid={v.owner_mid}) | 分区={v.partition_name} | "
            f"时长={v.duration}s{long_tag} | 年份={_year(v.pubdate)} | "
            f"标题={v.title[:80]} | 简介={desc_clip}"
        )
    for o in top_owners:
        bullets.append(f"- 反复被规则命中（≥3 次）：UP={o[0]}(mid={o[1]}) × {o[2]}")

    sys_msg = (
        "你是一个B站观看习惯分析助手。基于用户的过滤/移除信号，提出 3~6 条新黑名单规则。"
        "每条规则的 kind 必须是以下之一：title_keyword | title_regex | owner_name | owner_mid | "
        "duration_lt | duration_gt | partition_name | tag_keyword。"
        "（不要使用 partition_tid，直接用 partition_name 中文分区名更可读）。"
        "value 必须严格符合 kind 的格式：duration_lt/duration_gt 用秒数字符串（如 \"60\"），"
        "owner_mid 用 UID 数字字符串。"
        "每条配一个 reason 字段（中文，30 字以内，说明为什么这条规则能减少不喜欢的视频）。"
        "不要建议已经存在的规则。\n\n"
        "好的规则示例（精准、可解释）：\n"
        "  {\"kind\":\"title_keyword\",\"value\":\"零基础速成\",\"reason\":\"教程营销话术，用户多次移除\"}\n"
        "  {\"kind\":\"owner_mid\",\"value\":\"123456\",\"reason\":\"该 UP 已被规则反复命中 8 次\"}\n"
        "坏的规则示例（太宽，会误伤）：\n"
        "  {\"kind\":\"title_keyword\",\"value\":\"教程\"}  ← 太常见、会过滤大量正常视频\n"
        "  {\"kind\":\"duration_lt\",\"value\":\"600\"}  ← 阈值过宽、几乎所有短视频都中招"
    )

    user_msg = (
        "已有规则:\n" + ("\n".join(current_summary) or "（空）") + "\n\n" +
        "近期信号（用户加进稍后再看后又移除的视频 + 反复被规则命中的 UP）:\n" +
        "\n".join(bullets[:60])
    )

    try:
        text = await chat(
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=8000,
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
