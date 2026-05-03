from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .settings import settings


class Base(DeclarativeBase):
    pass


_engine = create_engine(
    f"sqlite:///{settings.db_path}",
    echo=False,
    future=True,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    from . import models  # noqa: F401  (register models)

    Base.metadata.create_all(bind=_engine)
    _seed_defaults()


def _seed_defaults() -> None:
    """Seed sensible default blacklist rules on a fresh DB."""
    from sqlalchemy import select

    from .models import BlacklistRule, RuleKind

    legacy_keywords = [
        "直播录像",
        "寅子录播",
        "助眠",
        "BILLBOARD",
        "公告牌",
        "单曲周榜",
        "直播回放",
    ]
    with SessionLocal() as db:
        existing = db.execute(select(BlacklistRule).limit(1)).first()
        if existing is not None:
            return
        for kw in legacy_keywords:
            db.add(BlacklistRule(kind=RuleKind.title_keyword, value=kw, note="迁移自旧 config.json"))
        db.commit()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
