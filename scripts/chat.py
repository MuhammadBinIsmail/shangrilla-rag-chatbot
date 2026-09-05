#!/usr/bin/env python3
"""Interactive multi-turn chat against one module's indexed documents.

Usage:
    python3 scripts/chat.py CO
    python3 scripts/chat.py CO --session my-session-id   # resume a session

Type 'exit' or 'quit' to end.
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
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/chat.py <MODULE> [--session <id>]")
        sys.exit(1)

    module = sys.argv[1].upper()
    session_id = None
    if "--session" in sys.argv:
        session_id = sys.argv[sys.argv.index("--session") + 1]
    else:
        session_id = str(uuid.uuid4())
        print(f"New session: {session_id}")
        print(f"(resume later with: python3 scripts/chat.py {module} --session {session_id})\n")

    load_dotenv()
    engine = get_engine()
    init_db(engine)
    db_session = get_session(engine)
    session_store = SessionStore(db_session)
    embedder = GeminiEmbeddingClient()
    llm = OpenRouterClient()

    print(f"Module: {module}. Type 'exit' or 'quit' to end.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if user_input.lower() in ("exit", "quit"):
            break
        if not user_input:
            continue

        turn = ask(session_store, db_session, embedder, llm, session_id, user_input, module=module)
        print(f"\nAssistant: {turn.text}\n")
        if turn.sources:
            cited = ", ".join(sorted({s.wricef_id for s in turn.sources}))
            print(f"(sources: {cited})\n")


if __name__ == "__main__":
    main()
