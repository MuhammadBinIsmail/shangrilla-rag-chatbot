"""Session/message persistence.

No conversation state lives in a shared Python object - every read
here goes back to the DB. This is the actual isolation mechanism: two
sessions can never leak into each other because there's no in-memory
object either of them could accidentally share. See architecture doc
section H.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session as OrmSession

from app.database.models import Message, Session


class SessionStore:
    def __init__(self, session: OrmSession):
        self._session = session

    def get_or_create_session(self, session_id: str) -> Session:
        existing = self._session.get(Session, session_id)
        if existing:
            return existing
        new_session = Session(session_id=session_id, module=None)
        self._session.add(new_session)
        self._session.commit()
        return new_session

    def set_module(self, session_id: str, module: str) -> None:
        session_row = self._session.get(Session, session_id)
        session_row.module = module
        self._session.commit()

    def get_history(self, session_id: str) -> list[Message]:
        session_row = self._session.get(Session, session_id)
        return list(session_row.messages) if session_row else []

    def add_message(self, session_id: str, role: str, content: str) -> None:
        message = Message(
            message_id=str(uuid.uuid4()), session_id=session_id, role=role, content=content
        )
        self._session.add(message)
        self._session.commit()
