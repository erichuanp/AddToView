from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..bilibili.client import BiliClient, BilibiliError
from ..bilibili.dynamic import fetch_video_dynamics
from ..bilibili.toview import add_to_watchlater, remove_from_watchlater
from ..bilibili.video import get_tags, get_view
from ..models import Action, ActionKind, BlacklistRule, RuleKind, Video
from . import blacklist as blacklist_service

logger = logging.getLogger(__name__)

_ENRICH_KINDS = {
    RuleKind.tag_keyword,
    RuleKind.partition_tid,
    RuleKind.partition_name,
    RuleKind.duration_lt,
    RuleKind.duration_gt,
}


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _needs_enrichment(rules: list[BlacklistRule]) -> bool:
    return any(r.kind in _ENRICH_KINDS for r in rules)


async def enrich_video(client: BiliClient, vid: dict[str, Any], *, fetch_tags: bool) -> None:
    """Best-effort: fill in partition info, full duration, and (optionally) tags."""
    bvid = vid.get("bvid")
    if not bvid:
        return
    try:
        view = await get_view(client, bvid=bvid)
        if not vid.get("duration") and view.get("duration"):
            vid["duration"] = int(view.get("duration") or 0)
        vid["partition_tid"] = view.get("tid") or vid.get("partition_tid")
        vid["partition_name"] = view.get("tname") or vid.get("partition_name") or ""
        if not vid.get("desc"):
            vid["desc"] = view.get("desc") or ""
        if not vid.get("cid"):
            vid["cid"] = view.get("cid")
    except BilibiliError as exc:
        logger.warning("view enrich failed for %s: %s", bvid, exc.message)
    except Exception as exc:  # noqa: BLE001
        logger.warning("view enrich error for %s: %s", bvid, exc)

    if fetch_tags:
        try:
            tags = await get_tags(client, bvid=bvid)
            vid["tags_csv"] = ",".join(tags)
        except Exception as exc:  # noqa: BLE001
            logger.warning("tag fetch error for %s: %s", bvid, exc)


def upsert_video(db: Session, vid: dict[str, Any]) -> tuple[Video, bool]:
    row = db.execute(select(Video).where(Video.bvid == vid["bvid"])).scalar_one_or_none()
    created = row is None
    if row is None:
        row = Video(bvid=vid["bvid"])
        db.add(row)
    row.aid = vid.get("aid")
    if vid.get("cid"):
        row.cid = vid.get("cid")
    row.title = vid.get("title") or row.title
    row.cover = vid.get("cover") or row.cover
    row.duration = int(vid.get("duration") or row.duration or 0)
    row.pubdate = int(vid.get("pubdate") or row.pubdate or 0)
    row.owner_mid = vid.get("owner_mid") or row.owner_mid
    row.owner_name = vid.get("owner_name") or row.owner_name
    row.partition_tid = vid.get("partition_tid") or row.partition_tid
    row.partition_name = vid.get("partition_name") or row.partition_name
    if vid.get("desc"):
        row.desc = vid["desc"]
    if vid.get("tags_csv"):
        row.tags_csv = vid["tags_csv"]
    if vid.get("raw") is not None:
        row.raw_json = vid["raw"]
    return row, created


def already_added(db: Session, video_id: int) -> bool:
    q = (
        select(Action.id)
        .where(Action.video_id == video_id, Action.kind == ActionKind.added)
        .limit(1)
    )
    return db.execute(q).first() is not None


async def ingest_dynamic_feed(
    db: Session,
    cookies: dict[str, str],
    *,
    cutoff_pubdate: int,
    max_pages: int = 20,
) -> dict[str, Any]:
    async with BiliClient(cookies) as client:
        items = await fetch_video_dynamics(client, cutoff_pubdate, max_pages=max_pages)

        rules = blacklist_service.load_rules(db)
        fetched = len(items)
        new_count = 0
        filtered_count = 0
        enrich = _needs_enrichment(rules)
        fetch_tags = any(r.kind == RuleKind.tag_keyword for r in rules)

        terminal_kinds = [ActionKind.filtered, ActionKind.added, ActionKind.error]

        for vid in items:
            if enrich:
                await enrich_video(client, vid, fetch_tags=fetch_tags)

            row, created = upsert_video(db, vid)
            db.flush()
            if created:
                new_count += 1
                db.add(Action(video_id=row.id, kind=ActionKind.ingested, reason=""))
            else:
                # 已有终态 action 的老视频不再重新 evaluate：cutoff 窗口扩到 6h
                # 后会反复扫到它们，否则每次同步都重复打一条 filtered Action、
                # 把规则的 hit_count 也无限累加。
                already_acted = db.execute(
                    select(Action.id)
                    .where(Action.video_id == row.id, Action.kind.in_(terminal_kinds))
                    .limit(1)
                ).first()
                if already_acted is not None:
                    continue

            hit = blacklist_service.evaluate(vid, rules)
            if hit:
                filtered_count += 1
                # bump hit counter (works with reloaded ORM object since rule list was loaded in this session)
                rule_obj = db.get(BlacklistRule, hit.rule_id)
                if rule_obj is not None:
                    rule_obj.hit_count = (rule_obj.hit_count or 0) + 1
                db.add(
                    Action(
                        video_id=row.id,
                        kind=ActionKind.filtered,
                        reason=f"{hit.kind.value}: {hit.reason}",
                    )
                )

    db.commit()
    return {
        "fetched": fetched,
        "new": new_count,
        "filtered": filtered_count,
        "pages": 1,
        "cutoff_pubdate": cutoff_pubdate,
    }


async def add_unfiltered_to_watchlater(
    db: Session,
    cookies: dict[str, str],
    *,
    lookback_days: int = 30,
) -> dict[str, Any]:
    """Push every "pending" Video to watch later — pending = no prior
    filtered/added/error action. The pubdate floor (lookback_days) just bounds
    the scan; it does NOT cap based on last sync time, so a user can press
    同步 then 一键添加 a few seconds later and still have the queue pushed.
    """
    cutoff = int(time.time()) - lookback_days * 86400
    acted_subq = (
        select(Action.video_id)
        .where(Action.kind.in_([ActionKind.filtered, ActionKind.added, ActionKind.error]))
        .distinct()
    )
    candidates_q = (
        select(Video)
        .where(Video.pubdate >= cutoff, ~Video.id.in_(acted_subq))
        .order_by(Video.pubdate.desc())
    )
    candidates = list(db.execute(candidates_q).scalars())

    added: list[str] = []
    skipped: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    async with BiliClient(cookies) as client:
        for v in candidates:
            try:
                payload = await add_to_watchlater(client, v.bvid)
                code = int(payload.get("code", -1))
            except Exception as exc:  # noqa: BLE001
                errors.append({"bvid": v.bvid, "reason": str(exc)})
                db.add(Action(video_id=v.id, kind=ActionKind.error, reason=str(exc)))
                continue

            if code == 0:
                added.append(v.bvid)
                db.add(Action(video_id=v.id, kind=ActionKind.added, reason=""))
            elif code == 90001:
                errors.append({"bvid": v.bvid, "reason": "watchlater full (90001)"})
                db.add(Action(video_id=v.id, kind=ActionKind.error, reason="full"))
                break
            elif code in (90005, 90002):
                added.append(v.bvid)
                db.add(Action(video_id=v.id, kind=ActionKind.added, reason=f"code={code}"))
            else:
                errors.append({"bvid": v.bvid, "reason": f"code={code} {payload.get('message', '')}"})
                db.add(Action(video_id=v.id, kind=ActionKind.error, reason=f"code={code}"))

    db.commit()
    return {"added": added, "skipped": skipped, "errors": errors}


async def clear_viewed_from_watchlater(cookies: dict[str, str]) -> dict[str, Any]:
    """调 B 站 /toview/del?viewed=true 让它按自己标准删已观看的视频。

    软失败：异常或非 0 code 都不抛，调用方根据返回字段决定怎么显示。
    """
    try:
        async with BiliClient(cookies) as client:
            payload = await remove_from_watchlater(client, viewed=True)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
    code = int(payload.get("code", -1))
    return {
        "ok": code == 0,
        "code": code,
        "message": payload.get("message", "") or "",
    }


async def run_auto_add_pipeline(
    db: Session,
    cookies: dict[str, str],
    *,
    cutoff_pubdate: int,
    max_pages: int = 20,
) -> dict[str, Any]:
    """一键添加完整流水：sync → 推入稍后再看 → 清理已观看。

    UI 一键添加按钮（POST /api/videos/auto-add）和 CLI（GET /addtoview/）共用
    这一个函数，行为完全一致——之前两条路径各自实现一遍是 bug 来源。

    - sync 失败抛 BilibiliError，由调用方处理
    - 清理已观看是软失败，结果在 `cleared_viewed` 字段
    """
    sync_result = await ingest_dynamic_feed(
        db, cookies, cutoff_pubdate=cutoff_pubdate, max_pages=max_pages
    )
    add_result = await add_unfiltered_to_watchlater(db, cookies)
    cleared = await clear_viewed_from_watchlater(cookies)
    return {"sync": sync_result, "add": add_result, "cleared_viewed": cleared}


def dry_run_blacklist(db: Session, *, days: int) -> dict[str, Any]:
    """Re-evaluate every Video newer than `days` against the *current* rule set."""
    import time

    cutoff = int(time.time()) - days * 86400
    rules = blacklist_service.load_rules(db)
    rule_map = {r.id: r for r in rules}

    rows = list(
        db.execute(select(Video).where(Video.pubdate >= cutoff).order_by(Video.pubdate.desc())).scalars()
    )

    items: list[dict[str, Any]] = []
    would_filter = 0
    for v in rows:
        vid = {
            "bvid": v.bvid,
            "title": v.title,
            "owner_name": v.owner_name,
            "owner_mid": v.owner_mid,
            "duration": v.duration,
            "partition_tid": v.partition_tid,
            "partition_name": v.partition_name,
            "tags_csv": v.tags_csv,
        }
        hit = blacklist_service.evaluate(vid, rules)
        if hit:
            would_filter += 1
            rule = rule_map.get(hit.rule_id)
            items.append(
                {
                    "bvid": v.bvid,
                    "title": v.title,
                    "cover": v.cover,
                    "duration": v.duration,
                    "pubdate": v.pubdate,
                    "owner_mid": v.owner_mid,
                    "owner_name": v.owner_name,
                    "matched_rule": {
                        "id": rule.id if rule else hit.rule_id,
                        "kind": hit.kind.value,
                        "value": hit.value,
                        "reason": hit.reason,
                    },
                }
            )
    return {"tested": len(rows), "would_filter": would_filter, "items": items}
