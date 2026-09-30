from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from queryrag.config import get_settings


@lru_cache
def get_engine():
    settings = get_settings()

    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required for database access")

    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
    )


@lru_cache
def get_session_factory():
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        autocommit=False,
    )


def get_db() -> Generator[Session, None, None]:
    database = get_session_factory()()

    try:
        yield database
    finally:
        database.close()
