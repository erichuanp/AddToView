from __future__ import annotations

from typing import Any

from .client import BiliClient

VIEW_URL = "https://api.bilibili.com/x/web-interface/view"
TAG_URL = "https://api.bilibili.com/x/tag/archive/tags"
PLAYER_V2_URL = "https://api.bilibili.com/x/player/v2"


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
      1. /x/player/v2 拿 subtitle.subtitles 列表（可能为空）
      2. 优先选简体中文（lan_doc 含「中文」/「Chinese」），否则取第一条
      3. GET subtitle_url（B站 CDN，HTTPS JSON），把 body[*].content 拼起来
      4. 没字幕、字幕列表 401/不可访问、body 太短都视为失败，返回 ('', '')

    任何 HTTP/JSON 错误都吞掉返回空 —— 调用方负责显示"信息有限"提示。
    """
    try:
        params: dict[str, Any] = {"bvid": bvid, "cid": cid}
        payload = await client.get_json(PLAYER_V2_URL, params=params)
        data = client.check(payload)
        subtitles = ((data.get("subtitle") or {}).get("subtitles")) or []
    except Exception:  # noqa: BLE001
        return "", ""

    if not subtitles:
        return "", ""

    def _is_chinese(s: dict[str, Any]) -> bool:
        doc = (s.get("lan_doc") or "") + " " + (s.get("lan") or "")
        return "中" in doc or "zh" in doc.lower() or "chinese" in doc.lower()

    chosen = next((s for s in subtitles if _is_chinese(s)), subtitles[0])
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
