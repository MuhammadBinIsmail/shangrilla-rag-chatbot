#!/usr/bin/env python3
"""Sanity check: what's actually in the vector store right now,
queried directly from Postgres rather than trusting run logs.
"""
from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import func, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database.models import Chunk, Document  # noqa: E402
from app.database.session import get_engine, get_session  # noqa: E402


def main() -> None:
    load_dotenv()
    session = get_session(get_engine())

    doc_count = session.scalar(select(func.count()).select_from(Document))
    chunk_count = session.scalar(select(func.count()).select_from(Chunk))
    print(f"Documents in store: {doc_count}")
    print(f"Chunks in store:    {chunk_count}")

    print("\nBy module:")
    for module, count in session.execute(
        select(Document.module, func.count()).group_by(Document.module).order_by(Document.module)
    ):
        print(f"  {module}: {count}")

    print("\nBy doc_type:")
    for doc_type, count in session.execute(
        select(Document.doc_type, func.count()).group_by(Document.doc_type)
    ):
        print(f"  {doc_type}: {count}")


if __name__ == "__main__":
    main()
