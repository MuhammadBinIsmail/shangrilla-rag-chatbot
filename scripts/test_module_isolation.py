#!/usr/bin/env python3
"""Cross-module isolation check: for every module, confirm retrieval
NEVER returns a chunk from a different module - the one thing this
project cannot get wrong.

The module filter is a hard SQL WHERE clause (see app/retrieval/
retriever.py), so this is really confirming that guarantee holds on
real data, not searching for a subtle semantic leak - but "should be
true by construction" and "confirmed true on real data" are different
levels of confidence, and this project has consistently preferred the
second.
"""
from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.modules import Module  # noqa: E402
from app.database.session import get_engine, get_session  # noqa: E402
from app.embeddings.gemini_client import GeminiEmbeddingClient  # noqa: E402
from app.retrieval.retriever import retrieve  # noqa: E402

# Generic enough to plausibly return content in any populated module,
# so a failure here is meaningful, not just "no results anyway"
_PROBE_QUERY = "What is the technical implementation and process for this requirement?"


def main() -> None:
    load_dotenv()
    session = get_session(get_engine())
    embedder = GeminiEmbeddingClient()

    print(f"Probe query: {_PROBE_QUERY!r}\n")

    all_passed = True
    for module in Module:
        chunks = retrieve(session, embedder, _PROBE_QUERY, module.value, top_k=10)
        leaked = [c for c in chunks if c.module != module.value]

        status = "PASS" if not leaked else "FAIL"
        if leaked:
            all_passed = False
        print(f"[{status}] {module.value}: {len(chunks)} chunks retrieved, {len(leaked)} leaked")
        for c in leaked:
            print(f"    LEAK: got module={c.module} chunk from {c.source_filename}")

    print()
    if all_passed:
        print("All modules isolated correctly - no cross-module leakage detected.")
    else:
        print("ISOLATION FAILURE - see LEAK lines above. Do not trust retrieval until fixed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
