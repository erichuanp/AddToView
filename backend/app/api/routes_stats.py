from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Action, ActionKind, BlacklistRule, Video

router = APIRouter()


@router.get("/summary")
def summary(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)

    # by_kind aggregate
    by_kind_rows = db.execute(
        select(Action.kind, func.count(Action.id))
        .where(Action.created_at >= cutoff)
        .group_by(Action.kind)
    ).all()
    by_kind = {row[0].value if hasattr(row[0], "value") else str(row[0]): int(row[1]) for row in by_kind_rows}

    # daily series — group by date
    daily_rows = db.execute(
        select(
            func.date(Action.created_at).label("d"),
            Action.kind,
            func.count(Action.id),
        )
        .where(Action.created_at >= cutoff)
        .group_by("d", Action.kind)
        .order_by("d")
    ).all()

    daily_map: dict[str, dict[str, int]] = {}
    for d, kind, n in daily_rows:
        ds = str(d)
        kind_str = kind.value if hasattr(kind, "value") else str(kind)
        daily_map.setdefault(ds, {})
        daily_map[ds][kind_str] = int(n)

    # fill empty days so the chart doesn't have gaps
    today = datetime.now(tz=timezone.utc).date()
    daily: list[dict[str, Any]] = []
    for i in range(days):
        date_str = (today - timedelta(days=days - 1 - i)).isoformat()
        bucket = daily_map.get(date_str, {})
        daily.append(
            {
                "date": date_str,
                "ingested": bucket.get("ingested", 0),
                "filtered": bucket.get("filtered", 0),
                "added": bucket.get("added", 0),
                "removed": bucket.get("removed", 0),
                "error": bucket.get("error", 0),
            }
        )

    # top filtered owners
    top_owners_rows = db.execute(
        select(Video.owner_name, Video.owner_mid, func.count(Action.id).label("c"))
        .join(Action, Action.video_id == Video.id)
        .where(Action.kind == ActionKind.filtered, Action.created_at >= cutoff)
        .group_by(Video.owner_name, Video.owner_mid)
        .order_by(desc("c"))
        .limit(10)
    ).all()
    top_filtered_owners = [
        {"name": row[0] or "(unknown)", "mid": row[1], "count": int(row[2])}
        for row in top_owners_rows
    ]

    # top active rules — by hit_count overall (cheap proxy)
    top_rules_rows = db.execute(
        select(BlacklistRule).order_by(desc(BlacklistRule.hit_count)).limit(10)
    ).scalars().all()
    top_active_rules = [
        {
            "id": r.id,
            "kind": r.kind.value,
            "value": r.value,
            "hits": int(r.hit_count or 0),
            "enabled": r.enabled,
        }
        for r in top_rules_rows
        if (r.hit_count or 0) > 0
    ]

    total_videos = db.execute(select(func.count(Video.id))).scalar_one() or 0

    return {
        "window_days": days,
        "total_videos_known": int(total_videos),
        "by_kind": by_kind,
        "daily": daily,
        "top_filtered_owners": top_filtered_owners,
        "top_active_rules": top_active_rules,
    }
