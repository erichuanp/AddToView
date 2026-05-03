"""Thin OpenAI-compatible chat client.

Three slots persisted as JSON in `settings.llm_slots`, plus a pointer
`llm_active_slot`. Each slot has base_url, model_id, api_key — all
stored in plaintext (single-user local app; visual masking is handled
in the UI).
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, dataclass

import httpx

from ..settings import settings as env_settings


def _in_container() -> bool:
    """True if running inside a Docker container."""
    if os.environ.get("ADDTOVIEW_IN_CONTAINER") == "1":
        return True
    return os.path.exists("/.dockerenv")


_HOST_LOOPBACK_RE = re.compile(r"//(localhost|127\.0\.0\.1|\[::1\])(?=[:/]|$)")

logger = logging.getLogger(__name__)

SLOT_COUNT = 3


class LLMUnconfigured(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    model_id: str
    api_key: str


@dataclass
class LLMSlot:
    base_url: str = ""
    model_id: str = ""
    api_key: str = ""

    def is_empty(self) -> bool:
        return not (self.base_url or self.model_id or self.api_key)


_CHAT_SUFFIX = "/chat/completions"


def normalize_base_url(raw: str) -> str:
    """Idempotent: strip whitespace, collapse `//`, ensure /chat/completions tail.

    Also: when running inside a container, rewrite localhost / 127.0.0.1
    in the host portion to host.docker.internal — saves users from
    having to know the Docker hostname trick when their LLM runs on
    the host (LM Studio, Ollama, llama.cpp, etc.).
    """
    if not raw:
        return ""
    s = raw.strip()
    if not s:
        return ""

    if "://" in s:
        scheme, rest = s.split("://", 1)
    else:
        scheme, rest = "", s

    while "//" in rest:
        rest = rest.replace("//", "/")
    rest = rest.rstrip("/")

    full = f"{scheme}://{rest}" if scheme else rest
    if _in_container():
        full = _HOST_LOOPBACK_RE.sub("//host.docker.internal", full)
    if full.endswith(_CHAT_SUFFIX):
        return full
    if full.endswith("/chat"):
        return full + "/completions"
    return full + _CHAT_SUFFIX


def _read_setting(key: str) -> str:
    from ..db import SessionLocal
    from ..models import Setting

    with SessionLocal() as db:
        row = db.get(Setting, key)
        return row.value if row and row.value else ""


def _write_setting(key: str, value: str) -> None:
    from ..db import SessionLocal
    from ..models import Setting

    with SessionLocal() as db:
        row = db.get(Setting, key)
        if row is None:
            db.add(Setting(key=key, value=value))
        else:
            row.value = value
        db.commit()


def _serialize_slots(slots: list[LLMSlot]) -> str:
    return json.dumps([asdict(s) for s in slots[:SLOT_COUNT]], ensure_ascii=False)


def read_slots() -> tuple[list[LLMSlot], int]:
    """Returns (slots, active_index). Always exactly SLOT_COUNT.
    Migrates legacy single-config keys into slot 0 on first read.
    """
    raw = _read_setting("llm_slots")
    slots: list[LLMSlot] = []
    if raw:
        try:
            decoded = json.loads(raw)
            for s in decoded[:SLOT_COUNT]:
                if not isinstance(s, dict):
                    slots.append(LLMSlot())
                    continue
                slots.append(
                    LLMSlot(
                        base_url=str(s.get("base_url", "")),
                        model_id=str(s.get("model_id", "")),
                        api_key=str(s.get("api_key", "") or s.get("api_key_tail", "")),
                    )
                )
        except (json.JSONDecodeError, TypeError, AttributeError) as exc:
            logger.warning("llm_slots invalid JSON, resetting: %s", exc)
            slots = []

    # legacy single-config row migration
    if not slots or all(s.is_empty() for s in slots):
        legacy = LLMSlot(
            base_url=_read_setting("llm_base_url"),
            model_id=_read_setting("llm_model_id"),
            api_key=_read_setting("llm_api_key"),
        )
        if not legacy.is_empty():
            slots = [legacy]

    while len(slots) < SLOT_COUNT:
        slots.append(LLMSlot())
    slots = slots[:SLOT_COUNT]

    active_raw = _read_setting("llm_active_slot")
    try:
        active = max(0, min(SLOT_COUNT - 1, int(active_raw))) if active_raw else 0
    except ValueError:
        active = 0

    return slots, active


def save_slot(idx: int, *, base_url: str, model_id: str, api_key: str | None) -> LLMSlot:
    """Persist one slot. `api_key=None` means leave existing key untouched."""
    if idx < 0 or idx >= SLOT_COUNT:
        raise ValueError(f"slot index out of range: {idx}")
    slots, _ = read_slots()
    new_url = normalize_base_url(base_url) if base_url else ""
    new_model = model_id.strip()
    new_key = slots[idx].api_key if api_key is None else api_key.strip()
    slots[idx] = LLMSlot(base_url=new_url, model_id=new_model, api_key=new_key)
    _write_setting("llm_slots", _serialize_slots(slots))
    return slots[idx]


def set_active_slot(idx: int) -> None:
    if idx < 0 or idx >= SLOT_COUNT:
        raise ValueError(f"slot index out of range: {idx}")
    _write_setting("llm_active_slot", str(idx))


def get_active_config() -> LLMConfig:
    slots, active = read_slots()
    slot = slots[active]
    return LLMConfig(
        base_url=slot.base_url or env_settings.llm_base_url,
        model_id=slot.model_id or env_settings.llm_model_id,
        api_key=slot.api_key or env_settings.llm_api_key,
    )


async def chat(
    messages: list[dict[str, str]],
    *,
    config: LLMConfig | None = None,
    temperature: float = 0.4,
    max_tokens: int = 600,
    timeout: float = 30.0,
    json_schema: dict | None = None,
    schema_name: str = "structured_output",
) -> str:
    """OpenAI-compatible chat completion.

    `json_schema` 触发 OpenAI structured outputs：服务端用 grammar / token
    constraint 强制模型只能吐合规 JSON，省掉一大堆兜底解析。LM Studio /
    OpenAI / 豆包 / vLLM 等都支持；旧 backend 可能直接忽略此字段（行为退
    化为普通生成，依然能跑）。
    """
    cfg = config or get_active_config()
    if not cfg.base_url or not cfg.model_id:
        raise LLMUnconfigured("AI 未配置：base_url / model_id 缺失")

    payload: dict[str, Any] = {
        "model": cfg.model_id,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_schema is not None:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "schema": json_schema,
                "strict": True,
            },
        }
    headers = {"Content-Type": "application/json"}
    # api_key is optional — local LLMs (Ollama, LM Studio, llama.cpp) don't
    # require auth. Only send the Authorization header if we actually have one.
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"

    async with httpx.AsyncClient(timeout=timeout) as cli:
        r = await cli.post(cfg.base_url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as exc:
        logger.error("LLM response shape unexpected: %s", data)
        raise RuntimeError(f"unexpected LLM response: {exc}") from exc
