from __future__ import annotations

import logging
from typing import Any

from .client import BiliClient

logger = logging.getLogger(__name__)

FEED_ALL = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/all"


async def fetch_video_dynamics(
    client: BiliClient,
    cutoff_pubdate: int,
    max_pages: int = 20,
) -> list[dict[str, Any]]:
    """Iterate the polymer dynamic feed, return video items newer than cutoff_pubdate.

    Each item is a flat dict: bvid, aid, title, cover, duration, pubdate, owner_mid,
    owner_name, desc, raw (the original feed entry).
    """

    out: list[dict[str, Any]] = []
    offset = ""
    update_baseline = ""
    seen_ids: set[str] = set()

    for page_idx in range(max_pages):
        params: dict[str, Any] = {
            "type": "video",
            "platform": "web",
        }
        if offset:
            params["offset"] = offset
        if update_baseline:
            params["update_baseline"] = update_baseline

        payload = await client.get_json(FEED_ALL, params=params)
        data = client.check(payload)
        items = data.get("items") or []
        next_offset = data.get("offset") or ""
        has_more = bool(data.get("has_more"))

        if not items:
            break

        oldest_in_page = None
        for it in items:
            if it.get("type") != "DYNAMIC_TYPE_AV":
                continue
            try:
                modules = it.get("modules", {}) or {}
                major = (modules.get("module_dynamic", {}) or {}).get("major", {}) or {}
                archive = major.get("archive") or {}
                bvid = archive.get("bvid") or ""
                if not bvid or bvid in seen_ids:
                    continue
                seen_ids.add(bvid)
                author = modules.get("module_author", {}) or {}
                pub_ts = int(author.get("pub_ts") or 0)
                oldest_in_page = pub_ts if oldest_in_page is None else min(oldest_in_page, pub_ts)

                aid = archive.get("aid")
                try:
                    aid = int(aid) if aid is not None else None
                except (TypeError, ValueError):
                    aid = None

                # archive may give numeric `duration` (seconds) and/or `duration_text` ("12:34")
                raw_duration = archive.get("duration")
                if isinstance(raw_duration, (int, float)) and raw_duration > 0:
                    duration = int(raw_duration)
                else:
                    duration = _parse_duration_text(archive.get("duration_text") or "")

                stat = archive.get("stat") or {}

                video = {
                    "bvid": bvid,
                    "aid": aid,
                    "title": archive.get("title") or "",
                    "cover": archive.get("cover") or "",
                    "duration": duration,
                    "pubdate": pub_ts,
                    "desc": archive.get("desc") or "",
                    "owner_mid": int(author.get("mid") or 0) or None,
                    "owner_name": author.get("name") or "",
                    "stat_play": int(stat.get("play") or 0) if isinstance(stat, dict) else 0,
                    "raw": it,
                }
                out.append(video)
            except Exception as exc:  # don't let one bad card kill the run
                logger.warning("dropping malformed feed item: %s", exc)

        if oldest_in_page is not None and oldest_in_page < cutoff_pubdate:
            break
        if not has_more or not next_offset:
            break
        offset = next_offset

    return [v for v in out if v["pubdate"] >= cutoff_pubdate]


def _parse_duration_text(text: str) -> int:
    """Bilibili's duration_text is like '12:34' or '1:02:03'. Convert to seconds."""
    if not text:
        return 0
    parts = text.split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return 0
    if len(nums) == 1:
        return nums[0]
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    return 0
