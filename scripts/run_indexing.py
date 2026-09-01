#!/usr/bin/env python3
"""Runs the real indexing pipeline: SHANGRILLA_DATA_ROOT -> chunks ->
Gemini embeddings -> Postgres/pgvector.

Usage:
    python3 scripts/run_indexing.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database.session import get_engine, get_session, init_db  # noqa: E402
from app.database.store import DocumentStore  # noqa: E402
from app.embeddings.gemini_client import GeminiEmbeddingClient  # noqa: E402
from app.indexing.pipeline import run_indexing  # noqa: E402


def main() -> None:
    load_dotenv()
    root_str = os.environ.get("SHANGRILLA_DATA_ROOT")
    if not root_str:
        print("SHANGRILLA_DATA_ROOT is not set in .env")
        sys.exit(1)
    root = Path(root_str).expanduser()

    print("Connecting to Postgres and ensuring schema exists...")
    engine = get_engine()
    init_db(engine)

    session = get_session(engine)
    store = DocumentStore(session)
    embedder = GeminiEmbeddingClient()

    print(f"Indexing {root} ...\n")
    stats = run_indexing(root, store, embedder)

    print("\n--- Summary ---")
    print(f"Documents indexed: {stats['documents_indexed']}")
    print(f"Chunks indexed:    {stats['chunks_indexed']}")
    print(f"Documents failed:  {stats['documents_failed']}")


if __name__ == "__main__":
    main()
