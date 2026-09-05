#!/usr/bin/env python3
"""Session isolation check against the real database: two distinct
sessions, distinct injected facts, confirm neither's history leaks
into the other. Same spirit as test_module_isolation.py, but for
sessions instead of modules.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database.session import get_engine, get_session, init_db  # noqa: E402
from app.database.session_store import SessionStore  # noqa: E402
from app.embeddings.gemini_client import GeminiEmbeddingClient  # noqa: E402
from app.llm.openrouter_client import OpenRouterClient  # noqa: E402
from app.retrieval.conversation import ask  # noqa: E402


def main() -> None:
    load_dotenv()
    engine = get_engine()
    init_db(engine)
    db_session = get_session(engine)
    store = SessionStore(db_session)
    embedder = GeminiEmbeddingClient()
    llm = OpenRouterClient()

    session_a = f"isolation-test-a-{uuid.uuid4()}"
    session_b = f"isolation-test-b-{uuid.uuid4()}"

    marker_a = "PURPLE_ELEPHANT_MARKER_A"
    marker_b = "ORANGE_GIRAFFE_MARKER_B"

    print(f"Session A ({session_a}): injecting marker {marker_a}")
    ask(store, db_session, embedder, llm, session_a, f"Remember this word: {marker_a}", module="CO")

    print(f"Session B ({session_b}): injecting marker {marker_b}")
    ask(store, db_session, embedder, llm, session_b, f"Remember this word: {marker_b}", module="FI")

    history_a = store.get_history(session_a)
    history_b = store.get_history(session_b)

    text_a = " ".join(m.content for m in history_a)
    text_b = " ".join(m.content for m in history_b)

    leak_a_into_b = marker_a in text_b
    leak_b_into_a = marker_b in text_a
    module_leak = store.get_or_create_session(session_a).module == store.get_or_create_session(
        session_b
    ).module

    print(f"\nSession A module: {store.get_or_create_session(session_a).module}")
    print(f"Session B module: {store.get_or_create_session(session_b).module}")
    print(f"Marker A leaked into session B: {leak_a_into_b}")
    print(f"Marker B leaked into session A: {leak_b_into_a}")

    if leak_a_into_b or leak_b_into_a:
        print("\nISOLATION FAILURE - sessions are leaking into each other.")
        sys.exit(1)
    print("\nPASS - sessions fully isolated.")


if __name__ == "__main__":
    main()
