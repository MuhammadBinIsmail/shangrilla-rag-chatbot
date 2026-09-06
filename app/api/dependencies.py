"""Per-request DB session (fresh every request - see architecture doc
section H on why this matters for isolation) and app-wide client
singletons, set up once in main.py's lifespan.
"""
from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session as OrmSession

from app.database.session import get_session
from app.database.session_store import SessionStore


def get_db(request: Request):
    session = get_session(request.app.state.engine)
    try:
        yield session
    finally:
        session.close()


def get_session_store(db: OrmSession = Depends(get_db)) -> SessionStore:
    return SessionStore(db)


def get_embedder(request: Request):
    return request.app.state.embedder


def get_llm(request: Request):
    return request.app.state.llm
