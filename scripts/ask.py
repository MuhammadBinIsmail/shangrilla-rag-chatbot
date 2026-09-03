#!/usr/bin/env python3
"""Ask a single-turn question against one module's indexed documents.

Usage:
    python3 scripts/ask.py CO "What triggers the cost estimate check?"
"""
from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database.session import get_engine, get_session  # noqa: E402
from app.embeddings.gemini_client import GeminiEmbeddingClient  # noqa: E402
from app.llm.openrouter_client import OpenRouterClient  # noqa: E402
from app.retrieval.qa import answer_query  # noqa: E402


def main() -> None:
    if len(sys.argv) < 3:
        print('Usage: python3 scripts/ask.py <MODULE> "<question>"')
        print("Example: python3 scripts/ask.py CO \"What triggers the cost estimate check?\"")
        sys.exit(1)

    module = sys.argv[1].upper()
    query = sys.argv[2]

    load_dotenv()
    session = get_session(get_engine())
    embedder = GeminiEmbeddingClient()
    llm = OpenRouterClient()

    print(f"Module: {module}")
    print(f"Question: {query}\n")
    print("Retrieving and generating...\n")

    result = answer_query(session, embedder, llm, query, module)

    print("--- Answer ---")
    print(result.text)

    print("\n--- Sources ---")
    if not result.sources:
        print("(none retrieved)")
    for s in result.sources:
        print(f"  [{s.wricef_id}] {s.doc_type} - {s.source_filename} (distance: {s.distance:.4f})")


if __name__ == "__main__":
    main()
