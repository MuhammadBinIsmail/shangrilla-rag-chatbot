"""Engine/session setup. Connection details from env (see .env.example) -
same values docker-compose.yml uses, so they always match.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import Base


def get_engine():
    user = os.environ.get("POSTGRES_USER", "shangrilla")
    password = os.environ.get("POSTGRES_PASSWORD", "changeme")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "shangrilla_rag")
    url = f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"
    return create_engine(url)


def init_db(engine=None) -> None:
    """Enable the pgvector extension, then create tables if missing."""
    engine = engine or get_engine()
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(engine)


def get_session(engine=None) -> Session:
    return sessionmaker(bind=engine or get_engine())()
