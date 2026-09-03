"""Module-filtered vector similarity search.

The module filter is a hard SQL WHERE clause, not just semantic
similarity - a chunk from a different module should never come back
regardless of how similar it scores, see architecture doc for why
this matters (cross-module contamination is the one thing this
project cannot get wrong).
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Chunk, Document
from app.embeddings.gemini_client import GeminiEmbeddingClient


@dataclass
class RetrievedChunk:
    text: str
    section_title: str | None
    document_id: str
    wricef_id: str
    module: str
    doc_type: str
    title: str | None
    source_filename: str
    distance: float


def retrieve(
    session: Session,
    embedding_client: GeminiEmbeddingClient,
    query: str,
    module: str,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    query_vector = embedding_client.embed_query(query)
    distance = Chunk.embedding.cosine_distance(query_vector)

    stmt = (
        select(Chunk, Document, distance.label("distance"))
        .join(Document, Chunk.document_id == Document.document_id)
        .where(Document.module == module)
        .order_by(distance)
        .limit(top_k)
    )

    return [
        RetrievedChunk(
            text=chunk.text,
            section_title=chunk.section_title,
            document_id=document.document_id,
            wricef_id=document.wricef_id,
            module=document.module,
            doc_type=document.doc_type,
            title=document.title,
            source_filename=document.source_filename,
            distance=dist,
        )
        for chunk, document, dist in session.execute(stmt)
    ]
