#!/usr/bin/env python3
"""Confirms the real embedding dimension from a live Gemini API call.
Run once before trusting EMBEDDING_DIMENSIONS in app/database/models.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database.models import EMBEDDING_DIMENSIONS  # noqa: E402
from app.embeddings.gemini_client import GeminiEmbeddingClient  # noqa: E402


def main() -> None:
    load_dotenv()
    client = GeminiEmbeddingClient()
    vectors = client.embed_documents(["This is a test sentence for dimension checking."])
    actual_dim = len(vectors[0])

    print(f"Real embedding dimension: {actual_dim}")
    print(f"Configured EMBEDDING_DIMENSIONS: {EMBEDDING_DIMENSIONS}")

    if actual_dim != EMBEDDING_DIMENSIONS:
        print(
            f"\nMISMATCH - update EMBEDDING_DIMENSIONS in "
            f"app/database/models.py to {actual_dim} before creating tables."
        )
    else:
        print("\nMatches - safe to proceed with table creation.")


if __name__ == "__main__":
    main()
