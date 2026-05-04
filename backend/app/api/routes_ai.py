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
from ..bilibili.video import get_subtitle_transcript, get_view
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

    - First call (or `?refresh=true`): hit Bilibili's official conclusion;
      fall back to the configured LLM on title+desc; persist to `video_summaries`.
    - Subsequent calls without `refresh`: return the cached row immediately
      (`source: 'cache'` so the UI can label it as "上次结果").
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

    if official and official.get("summary"):
        text = official["summary"]
        outline = official.get("outline") or []
        source = "bilibili"
    else:
        if not desc and not title:
            raise HTTPException(status_code=404, detail="no metadata to summarize")

        partition_name = view.get("tname") or ""
        desc_clipped = (desc or "").strip()[:500]
        desc_block = desc_clipped if desc_clipped else "（空——只能凭标题判断，不要编造细节）"

        prompt_user = (
            f"以下是一个B站视频的元信息，请用中文写一个 2~3 句的摘要、抓住重点、不要复读标题。\n\n"
            f"UP主：{owner}\n"
            f"分区：{partition_name}\n"
            f"标题：{title}\n"
            f"时长：{duration} 秒\n"
            f"简介：{desc_block}"
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
        outline = []
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


# 字幕全文 token 大头，但 reasoning 模型还要思考——给足 budget。10k 字符
# 中文 ≈ 5–6k tokens，留 2k 给摘要，剩下给思考链够用了。
_DEEP_SUMMARY_MAX_TOKENS = 12000
_TRANSCRIPT_MAX_CHARS = 12000  # 12k 字符 ≈ 7k tokens 输入；超过截断
_TRANSCRIPT_THIN_CHARS = 200    # 短于这个就视作"信息有限"
_THIN_WARN = "（由于该视频的字幕所提供的信息有限，视频总结的效果可能不尽如人愿）"


@router.post("/summary/{bvid}/deep")
async def video_summary_deep(
    bvid: str,
    db: Session = Depends(get_db),
    cookies: dict[str, str] = Depends(require_cookie_dict),
) -> dict[str, Any]:
    """深度摘要：拉视频字幕、按时长决定句量、覆盖缓存的摘要。

    没字幕或字幕太短就退回到元信息摘要 + 在末尾追加"信息有限"提示。
    成功的会同时更新 video_summaries 缓存（source = 'deep'），所以下次开
    AI 摘要弹窗能直接看到这次的深度版本。
    """
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
        partition_name = view.get("tname") or ""

        transcript, lan = await get_subtitle_transcript(client, bvid=bvid, cid=cid) if cid else ("", "")

    # 时长决定句量
    if duration < 300:        # < 5 分钟
        length_hint = "2~3 句"
    elif duration < 900:      # 5–15 分钟
        length_hint = "4~5 句"
    else:                      # 15 分钟以上
        length_hint = "6~8 句"

    transcript = transcript.strip()
    info_thin = len(transcript) < _TRANSCRIPT_THIN_CHARS
    truncated_transcript = transcript[:_TRANSCRIPT_MAX_CHARS]
    if len(transcript) > _TRANSCRIPT_MAX_CHARS:
        truncated_transcript += "\n…（字幕过长，已截断）"

    desc_clipped = desc.strip()[:500] or "（空）"
    transcript_block = truncated_transcript if truncated_transcript else "（该视频没有可获取的字幕）"

    prompt_user = (
        f"以下是一个B站视频的元信息和字幕全文，请用中文写一个 {length_hint} 的深度摘要、"
        f"覆盖视频核心内容、抓住重点、不要复读标题。\n\n"
        f"UP主：{owner}\n"
        f"分区：{partition_name}\n"
        f"标题：{title}\n"
        f"时长：{duration} 秒\n"
        f"简介：{desc_clipped}\n\n"
        f"字幕（{lan or '原始'}）：\n{transcript_block}\n\n"
        "在写摘要前，先判断字幕主题是否与标题/UP/简介相符。B站 AI 字幕系统偶发会"
        "返回该 UP 别的视频的字幕（明显跑题），如果你看到字幕讲的内容和标题完全无关，"
        "请忽略字幕、只用元信息总结，并在摘要末尾追加一行：（字幕错配，已忽略）"
    )

    try:
        text = await chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"你是一个深度视频摘要助手，输出严格 {length_hint} 中文摘要。"
                        "基于字幕原文总结视频核心内容、关键节点、明确观点。"
                        "不要标题党、不要复读标题、不要用『这个视频』『这部作品』『本片』等空话开头，直接进入内容。"
                        "如果字幕缺失或信息稀疏，只基于元信息做客观描述、不要编造。"
                        "如果字幕内容明显与标题/简介无关（B站 AI 字幕串扰 bug），忽略字幕只用元信息，"
                        "并在末尾追加『（字幕错配，已忽略）』。"
                    ),
                },
                {"role": "user", "content": prompt_user},
            ],
            max_tokens=_DEEP_SUMMARY_MAX_TOKENS,
            timeout=300.0,
            enable_thinking=True,
        )
    except LLMUnconfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"AI deep summary failed: {exc}") from exc

    text = text.strip()
    if info_thin and not text.endswith(_THIN_WARN) and "字幕错配" not in text:
        text = f"{text}\n\n{_THIN_WARN}"

    row = db.get(VideoSummary, bvid)
    if row is None:
        row = VideoSummary(bvid=bvid)
        db.add(row)
    row.source = "deep"
    row.title = title or row.title
    row.summary = text
    row.outline_json = []
    db.commit()
    db.refresh(row)

    return {
        **_to_payload(row),
        "has_subtitle": bool(transcript),
        "subtitle_thin": info_thin,
    }
