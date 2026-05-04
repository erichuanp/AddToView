from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..ai.llm import (
    LLMConfig,
    LLMSlot,
    LLMUnconfigured,
    SLOT_COUNT,
    chat,
    get_active_config,
    normalize_base_url,
    read_slots,
    save_slot,
    set_active_slot,
)
from ..bilibili.client import BiliClient, BilibiliError
from ..bilibili.summary import get_official_conclusion
from ..bilibili.video import get_view
from ..db import get_db
from ..models import VideoSummary
from .deps import require_cookie_dict

router = APIRouter()


class LLMTestPayload(BaseModel):
    base_url: str
    model_id: str
    api_key: str


class LLMSlotPayload(BaseModel):
    base_url: str = ""
    model_id: str = ""
    api_key: str | None = None  # None means "leave existing key untouched"


def _slot_view(slot: LLMSlot) -> dict[str, Any]:
    # api_key returned in plaintext — single-user local app; UI does the masking
    return {
        "base_url": slot.base_url,
        "model_id": slot.model_id,
        "api_key": slot.api_key,
        "api_key_set": bool(slot.api_key),
    }


@router.get("/llm/status")
def llm_status() -> dict[str, Any]:
    """Tells the frontend whether AI features are usable, plus all slots.
    api_key is optional (local LLMs don't need one)."""
    slots, active = read_slots()
    cfg = get_active_config()
    return {
        "configured": bool(cfg.base_url and cfg.model_id),
        "active_slot": active,
        "slots": [_slot_view(s) for s in slots],
    }


@router.post("/llm/slots/{idx}/activate")
def llm_activate_slot(idx: int) -> dict[str, Any]:
    if idx < 0 or idx >= SLOT_COUNT:
        raise HTTPException(status_code=400, detail=f"slot index out of range (0..{SLOT_COUNT - 1})")
    set_active_slot(idx)
    cfg = get_active_config()
    return {
        "active_slot": idx,
        "configured": bool(cfg.api_key and cfg.base_url and cfg.model_id),
    }


@router.put("/llm/slots/{idx}")
def llm_save_slot(idx: int, payload: LLMSlotPayload) -> dict[str, Any]:
    """Save form values into the given slot WITHOUT changing which slot is
    active. Use POST /activate separately to switch what AI features use.

    If api_key is None or empty, the slot's existing saved key is kept.
    """
    if idx < 0 or idx >= SLOT_COUNT:
        raise HTTPException(status_code=400, detail=f"slot index out of range (0..{SLOT_COUNT - 1})")

    # always overwrite — frontend now loads the saved key into the form on
    # slot select, so an empty value is an intentional clear, not "preserve"
    slot = save_slot(
        idx,
        base_url=payload.base_url,
        model_id=payload.model_id,
        api_key=(payload.api_key or "").strip(),
    )
    _, active = read_slots()
    return {
        "active_slot": active,
        "slot": _slot_view(slot),
    }


@router.post("/llm/test")
async def llm_test(payload: LLMTestPayload) -> dict[str, Any]:
    """One-shot ping with arbitrary config — does NOT save.
    api_key may be empty for local LLMs."""
    normalized_url = normalize_base_url(payload.base_url)
    cfg = LLMConfig(
        base_url=normalized_url,
        model_id=payload.model_id.strip(),
        api_key=payload.api_key.strip(),
    )
    try:
        reply = await chat(
            messages=[{"role": "user", "content": "回复一个字：好"}],
            config=cfg,
            max_tokens=1000,
            timeout=120.0,
        )
        return {"ok": True, "reply": reply[:100], "normalized_base_url": normalized_url}
    except LLMUnconfigured as exc:
        return {"ok": False, "error": str(exc), "normalized_base_url": normalized_url}
    except httpx.HTTPStatusError as exc:
        return {
            "ok": False,
            "error": f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            "normalized_base_url": normalized_url,
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "normalized_base_url": normalized_url}


def _to_payload(row: VideoSummary, source_override: str | None = None) -> dict[str, Any]:
    return {
        "source": source_override or row.source,
        "summary": row.summary,
        "outline": row.outline_json or [],
        "title": row.title,
        "cached_at": int(row.updated_at.timestamp()) if row.updated_at else None,
    }


@router.get("/summary/{bvid}")
async def video_summary(
    bvid: str,
    refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
    cookies: dict[str, str] = Depends(require_cookie_dict),
) -> dict[str, Any]:
    """Best-effort video summary with persistent cache.

    AI 摘要永远走 LLM；如果 B站官方看点（含字幕生成的 summary + 章节
    outline）能拿到，把它当作辅助资料拼进 prompt，让 LLM 综合元信息和看点
    做最终 2~3 句的总结。看点缺失/不支持就忽略那部分。
    `source: 'cache'` 用来标识"上次结果"。
    """

    if not refresh:
        cached = db.get(VideoSummary, bvid)
        if cached is not None and cached.summary:
            return _to_payload(cached, source_override="cache")

    async with BiliClient(cookies) as client:
        try:
            view = await get_view(client, bvid=bvid)
        except BilibiliError as exc:
            raise HTTPException(
                status_code=502, detail={"code": exc.code, "message": exc.message}
            ) from exc

        title = view.get("title") or ""
        desc = view.get("desc") or ""
        cid = int(view.get("cid") or 0)
        owner = (view.get("owner") or {}).get("name") or ""
        duration = int(view.get("duration") or 0)

        official = await get_official_conclusion(client, bvid=bvid, cid=cid) if cid else None

    if not desc and not title:
        raise HTTPException(status_code=404, detail="no metadata to summarize")

    partition_name = view.get("tname") or ""
    desc_clipped = (desc or "").strip()[:500]
    desc_block = desc_clipped if desc_clipped else "（空——只能凭标题判断，不要编造细节）"

    # 如果 B站官方看点能拿到，把 summary + 章节大纲拼进来当辅助资料。
    # 没拿到就完全省略这一段，prompt 不出现"参考"字眼。
    official_block = ""
    outline = official.get("outline") if official else []
    if official and official.get("summary"):
        lines = [
            "B站官方看点（基于视频字幕由B站AI生成，仅作辅助参考；偶有错配，请按标题/简介核对）:",
            official["summary"].strip(),
        ]
        if outline:
            lines.append("章节大纲:")
            for sec in outline[:12]:
                ts = int(sec.get("timestamp") or 0)
                t_str = f"{ts//60:02d}:{ts%60:02d}"
                sec_title = (sec.get("title") or "").strip()
                if sec_title:
                    lines.append(f"  · {t_str} {sec_title}")
        official_block = "\n\n" + "\n".join(lines)

    prompt_user = (
        "以下是一个B站视频的元信息，请用中文写一个 2~3 句的摘要、抓住重点、不要复读标题。\n\n"
        f"UP主：{owner}\n"
        f"分区：{partition_name}\n"
        f"标题：{title}\n"
        f"时长：{duration} 秒\n"
        f"简介：{desc_block}"
        f"{official_block}"
    )
    try:
        text = await chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个简洁的视频摘要助手，输出严格 2~3 句中文摘要。"
                        "不要标题党、不要复读标题、不要用『这个视频』『这部作品』『本片』等空话开头，"
                        "直接进入内容。如果简介为空，只对标题做客观描述，不要编造细节。"
                        "如果提供了B站官方看点，可以参考它的核心内容，但不要原样复述；"
                        "若看点内容明显跟标题/简介冲突（B站AI字幕串扰），忽略看点只用元信息。"
                    ),
                },
                {"role": "user", "content": prompt_user},
            ],
            max_tokens=6000,
        )
    except LLMUnconfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"AI summary failed: {exc}") from exc
    source = "llm"

    row = db.get(VideoSummary, bvid)
    if row is None:
        row = VideoSummary(bvid=bvid)
        db.add(row)
    row.source = source
    row.title = title or row.title
    row.summary = text
    row.outline_json = outline
    db.commit()
    db.refresh(row)

    return _to_payload(row)
