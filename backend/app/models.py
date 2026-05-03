from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class ActionKind(str, enum.Enum):
    ingested = "ingested"
    added = "added"
    removed = "removed"
    filtered = "filtered"
    viewed = "viewed"
    error = "error"


class RuleKind(str, enum.Enum):
    title_keyword = "title_keyword"
    title_regex = "title_regex"
    owner_name = "owner_name"
    owner_mid = "owner_mid"
    duration_lt = "duration_lt"
    duration_gt = "duration_gt"
    partition_tid = "partition_tid"
    partition_name = "partition_name"
    tag_keyword = "tag_keyword"


class Cookie(Base):
    __tablename__ = "cookies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dede_user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    dede_user_id_ckmd5: Mapped[str] = mapped_column(String(128))
    sessdata: Mapped[str] = mapped_column(Text)
    bili_jct: Mapped[str] = mapped_column(String(128))
    expires_raw: Mapped[str] = mapped_column(String(64), default="")
    refresh_token: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_logged_in: Mapped[bool] = mapped_column(Boolean, default=False)
    uname: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bvid: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    aid: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    cid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(Text, default="")
    cover: Mapped[str] = mapped_column(Text, default="")
    duration: Mapped[int] = mapped_column(Integer, default=0)
    pubdate: Mapped[int] = mapped_column(Integer, default=0)
    desc: Mapped[str] = mapped_column(Text, default="")
    owner_mid: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    owner_name: Mapped[str] = mapped_column(String(256), default="", index=True)
    partition_tid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    partition_name: Mapped[str] = mapped_column(String(128), default="")
    tags_csv: Mapped[str] = mapped_column(Text, default="")
    raw_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    actions: Mapped[list[Action]] = relationship(back_populates="video", cascade="all, delete-orphan")


class Action(Base):
    __tablename__ = "actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    kind: Mapped[ActionKind] = mapped_column(Enum(ActionKind), index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)

    video: Mapped[Video] = relationship(back_populates="actions")


class BlacklistRule(Base):
    __tablename__ = "blacklist_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[RuleKind] = mapped_column(Enum(RuleKind), index=True)
    value: Mapped[str] = mapped_column(Text)
    note: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (UniqueConstraint("kind", "value", name="uq_rule_kind_value"),)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class VideoSummary(Base):
    __tablename__ = "video_summaries"

    bvid: Mapped[str] = mapped_column(String(32), primary_key=True)
    source: Mapped[str] = mapped_column(String(16), default="")  # 'bilibili' | 'llm'
    title: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    outline_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
