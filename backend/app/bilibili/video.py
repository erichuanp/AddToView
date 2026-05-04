from __future__ import annotations

from typing import Any

from .client import BiliClient

from .wbi import signed_get_json

VIEW_URL = "https://api.bilibili.com/x/web-interface/view"
TAG_URL = "https://api.bilibili.com/x/tag/archive/tags"
PLAYER_V2_URL = "https://api.bilibili.com/x/player/v2"
PLAYER_WBI_V2_URL = "https://api.bilibili.com/x/player/wbi/v2"


async def get_view(client: BiliClient, *, bvid: str | None = None, aid: int | None = None) -> dict[str, Any]:
    if not bvid and not aid:
        raise ValueError("either bvid or aid is required")
    params: dict[str, Any] = {}
    if bvid:
        params["bvid"] = bvid
    elif aid:
        params["aid"] = aid
    payload = await client.get_json(VIEW_URL, params=params)
    return client.check(payload)


async def get_subtitle_transcript(
    client: BiliClient, *, bvid: str, cid: int
) -> tuple[str, str]:
    """拉视频字幕并拼成纯文本，返回 (transcript, source_lang)。

    流程：
      1. /x/player/wbi/v2（WBI 签名）拿 subtitle.subtitles 列表
         —— 关键：不签名时 B站会返回 stale/错配字幕（指向别的视频）
      2. 优先选简体中文（lan_doc 含「中文」/「Chinese」），否则取第一条
      3. GET subtitle_url（B站 CDN，HTTPS JSON），把 body[*].content 拼起来
      4. 没字幕、字幕列表 401/不可访问、body 太短都视为失败，返回 ('', '')

    任何 HTTP/JSON 错误都吞掉返回空 —— 调用方负责显示"信息有限"提示。
    """
    try:
        payload = await signed_get_json(
            client, PLAYER_WBI_V2_URL, {"bvid": bvid, "cid": cid}
        )
        data = client.check(payload)
        subtitles = ((data.get("subtitle") or {}).get("subtitles")) or []
    except Exception:  # noqa: BLE001
        return "", ""

    if not subtitles:
        return "", ""

    def _lan_label(s: dict[str, Any]) -> str:
        return (s.get("lan_doc") or "") + " " + (s.get("lan") or "")

    def _is_chinese(s: dict[str, Any]) -> bool:
        d = _lan_label(s).lower()
        return "中" in d or "zh" in d or "chinese" in d

    def _is_english(s: dict[str, Any]) -> bool:
        d = _lan_label(s).lower()
        return d.strip().startswith("en") or "ai-en" in d or "english" in d or "英" in d

    # 优先级：中文 > 英文 > 没字幕。其他语言（日/西/阿/葡等）当没字幕处理——
    # 即使能拉到，翻译成中文摘要质量不可控。
    chosen = next((s for s in subtitles if _is_chinese(s)), None)
    if chosen is None:
        chosen = next((s for s in subtitles if _is_english(s)), None)
    if chosen is None:
        return "", ""
    url = (chosen.get("subtitle_url") or "").strip()
    if not url:
        return "", ""
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    # 域名白名单：B站字幕 CDN 必须是 aisubtitle.hdslb.com / s1.hdslb.com，
    # 其他域名一律拒绝（实测 B站对短视频/祝福视频字幕系统偶发返回错乱
    # 内容，URL 看着对但内容是别的视频的——配合 prompt 端判断兜底）
    allowed_hosts = ("//aisubtitle.hdslb.com/", "//s1.hdslb.com/", "//i0.hdslb.com/")
    if not any(h in url for h in allowed_hosts):
        return "", ""
    try:
        resp = await client.get_json(url)
        body = resp.get("body") or []
    except Exception:  # noqa: BLE001
        return "", ""

    parts: list[str] = []
    for item in body:
        if not isinstance(item, dict):
            continue
        c = (item.get("content") or "").strip()
        if c:
            parts.append(c)
    transcript = "\n".join(parts)
    return transcript, str(chosen.get("lan_doc") or chosen.get("lan") or "")


async def get_tags(client: BiliClient, *, bvid: str | None = None, aid: int | None = None) -> list[str]:
    params: dict[str, Any] = {}
    if bvid:
        params["bvid"] = bvid
    elif aid:
        params["aid"] = aid
    payload = await client.get_json(TAG_URL, params=params)
    data = payload.get("data") or []
    return [t.get("tag_name") or "" for t in data if t.get("tag_name")]
