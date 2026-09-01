"""Indexing pipeline: resolved documents (from the M2 ingestion report)
-> body extraction -> chunking -> embedding -> storage.

xlsx-sourced FSDs get metadata stored but no body chunks - no body
extractor built for xlsx yet, documented gap, not silent.
"""
from __future__ import annotations

from pathlib import Path

from app.database.models import Chunk, Document
from app.embeddings.gemini_client import GeminiEmbeddingClient
from app.ingestion.chunking.section_splitter import chunk_document
from app.ingestion.discovery import DiscoveredFile
from app.ingestion.loaders.fsd_loader import extract_fsd_body_lines, load_fsd_metadata
from app.ingestion.loaders.tsd_loader import extract_tsd_body_text, load_tsd_metadata
from app.ingestion.loaders.xlsx_loader import load_fsd_metadata_xlsx
from app.ingestion.report import build_ingestion_report


def _load_full_metadata(file: DiscoveredFile):
    suffix = file.path.suffix.lower()
    if file.doc_type == "FSD" and suffix == ".docx":
        return load_fsd_metadata(file.path)
    if file.doc_type == "FSD" and suffix == ".xlsx":
        return load_fsd_metadata_xlsx(file.path)
    if file.doc_type == "TSD" and suffix == ".pdf":
        return load_tsd_metadata(file.path)
    return None


def _extract_body_lines(file: DiscoveredFile) -> list[str]:
    suffix = file.path.suffix.lower()
    if suffix == ".docx":
        return extract_fsd_body_lines(file.path)
    if suffix == ".pdf":
        return extract_tsd_body_text(file.path)
    return []  # xlsx - metadata only, no body extractor yet


def index_document(
    store, embedding_client: GeminiEmbeddingClient, file: DiscoveredFile, document_id: str
) -> int:
    """Indexes one document. Returns chunk count (0 if metadata
    couldn't be reloaded, or the document has no body content)."""
    metadata = _load_full_metadata(file)
    if metadata is None:
        return 0

    title = getattr(metadata, "title", None) or getattr(metadata, "short_title", None)
    extra_metadata = metadata.model_dump(exclude={"wricef_id"})

    doc_row = Document(
        document_id=document_id,
        wricef_id=metadata.wricef_id,
        module=file.module.value,
        doc_type=file.doc_type,
        title=title,
        source_filename=file.path.name,
        source_path=str(file.path),
        extra_metadata=extra_metadata,
    )
    store.upsert_document(doc_row)

    body_lines = _extract_body_lines(file)
    doc_chunks = chunk_document(body_lines)

    if not doc_chunks:
        store.replace_chunks(document_id, [])
        store.commit()
        return 0

    vectors = embedding_client.embed_documents([c.text for c in doc_chunks])
    chunk_rows = [
        Chunk(
            chunk_id=f"{document_id}-{c.chunk_index}",
            document_id=document_id,
            chunk_index=c.chunk_index,
            section_title=c.section_title,
            text=c.text,
            embedding=vec,
        )
        for c, vec in zip(doc_chunks, vectors)
    ]
    store.replace_chunks(document_id, chunk_rows)
    store.commit()
    return len(chunk_rows)


def run_indexing(root: Path, store, embedding_client: GeminiEmbeddingClient) -> dict[str, int]:
    """Runs discovery + collision resolution (M2), then indexes every
    resolved document. Returns summary counts."""
    report = build_ingestion_report(root)
    stats = {"documents_indexed": 0, "chunks_indexed": 0, "documents_failed": 0}

    for success in report.resolved:
        try:
            n = index_document(store, embedding_client, success.file, success.document_id)
            stats["documents_indexed"] += 1
            stats["chunks_indexed"] += n
        except Exception as exc:
            stats["documents_failed"] += 1
            print(f"Failed to index {success.file.path.name}: {exc}")

    return stats
