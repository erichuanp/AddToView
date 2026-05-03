from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import BlacklistRule, RuleKind

logger = logging.getLogger(__name__)


@dataclass
class FilterHit:
    rule_id: int
    kind: RuleKind
    value: str
    reason: str


def load_rules(db: Session) -> list[BlacklistRule]:
    return list(db.execute(select(BlacklistRule).where(BlacklistRule.enabled.is_(True))).scalars())


def evaluate(video: dict, rules: Iterable[BlacklistRule]) -> FilterHit | None:
    """Return the first matching rule, or None."""
    title = (video.get("title") or "").lower()
    owner_name = (video.get("owner_name") or "").lower()
    owner_mid = video.get("owner_mid")
    duration = int(video.get("duration") or 0)
    partition_tid = video.get("partition_tid")
    partition_name = (video.get("partition_name") or "").lower()
    tags_csv = (video.get("tags_csv") or "").lower()

    for rule in rules:
        v_raw = rule.value or ""
        v = v_raw.lower()
        try:
            match rule.kind:
                case RuleKind.title_keyword:
                    if v and v in title:
                        return _hit(rule, f"title contains '{v_raw}'")
                case RuleKind.title_regex:
                    if v_raw and re.search(v_raw, video.get("title") or "", flags=re.IGNORECASE):
                        return _hit(rule, f"title matches /{v_raw}/i")
                case RuleKind.owner_name:
                    if v and v == owner_name:
                        return _hit(rule, f"owner is '{v_raw}'")
                case RuleKind.owner_mid:
                    try:
                        if owner_mid is not None and int(v_raw) == int(owner_mid):
                            return _hit(rule, f"owner_mid={owner_mid}")
                    except ValueError:
                        continue
                case RuleKind.duration_lt:
                    try:
                        if duration and duration < int(v_raw):
                            return _hit(rule, f"duration {duration}s < {v_raw}s")
                    except ValueError:
                        continue
                case RuleKind.duration_gt:
                    try:
                        if duration and duration > int(v_raw):
                            return _hit(rule, f"duration {duration}s > {v_raw}s")
                    except ValueError:
                        continue
                case RuleKind.partition_tid:
                    try:
                        if partition_tid is not None and int(v_raw) == int(partition_tid):
                            return _hit(rule, f"partition tid={partition_tid}")
                    except ValueError:
                        continue
                case RuleKind.partition_name:
                    if v and v in partition_name:
                        return _hit(rule, f"partition name contains '{v_raw}'")
                case RuleKind.tag_keyword:
                    if v and v in tags_csv:
                        return _hit(rule, f"tag contains '{v_raw}'")
        except re.error as exc:
            logger.warning("rule %s has bad regex %r: %s", rule.id, rule.value, exc)
            continue
    return None


def _hit(rule: BlacklistRule, reason: str) -> FilterHit:
    return FilterHit(rule_id=rule.id, kind=rule.kind, value=rule.value, reason=reason)
