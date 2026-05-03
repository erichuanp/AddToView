from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthOut(BaseModel):
    ok: bool
    version: str


class StatusOut(BaseModel):
    logged_in: bool
    mid: int | None = None
    uname: str = ""
    vip_status: int = 0
    cookie_present: bool = False


class VideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    bvid: str
    aid: int | None = None
    title: str = ""
    cover: str = ""
    duration: int = 0
    pubdate: int = 0
    owner_mid: int | None = None
    owner_name: str = ""
    partition_tid: int | None = None
    partition_name: str = ""
    desc: str = ""


class WatchLaterItem(VideoOut):
    progress: int = 0
    add_at: int = 0


class FilteredItem(VideoOut):
    reason: str = ""
    filtered_at: datetime


class IngestSummary(BaseModel):
    fetched: int
    new: int
    filtered: int
    pages: int
    cutoff_pubdate: int


class ActionResult(BaseModel):
    kind: Literal["ok", "skip", "error"]
    code: int = 0
    message: str = ""


class BatchAddResult(BaseModel):
    added: list[str]
    skipped: list[dict]
    errors: list[dict]
