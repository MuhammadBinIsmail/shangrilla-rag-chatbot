"""Thin persistence interface. Keeps indexing logic testable without
a live Postgres - a fake implementing the same methods stands in for
this in tests.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.models import Chunk, Document


class DocumentStore:
    def __init__(self, session: Session):
        self._session = session

    def upsert_document(self, doc: Document) -> None:
        self._session.merge(doc)

    def replace_chunks(self, document_id: str, chunks: list[Chunk]) -> None:
        self._session.query(Chunk).filter(Chunk.document_id == document_id).delete()
        self._session.add_all(chunks)

    def commit(self) -> None:
        self._session.commit()
