# Shangrilla RAG Chatbot

Conversational RAG chatbot over Shangrilla Foods' SAP FSD/TSD documentation,
scoped per-module (CO, FI, MM, PP, QM, TM, WM), with session-isolated
conversation memory.

Full design record: `docs/architecture.md` (decisions logged round by round,
including what was tried and corrected as real data came in - not just the
final state).

## Status

Configuration & Metadata Schema: done, tested.
Document Discovery & Loaders: done, fully validated against the real
corpus (119/158, all remaining failures confirmed non-bugs).
Chunking & Vector Indexing: **done.** 106/106 resolved documents
indexed into Postgres/pgvector with real Gemini embeddings. Two real
bugs found and fixed along the way (see architecture doc): a runaway
chunking loop that could consume unbounded memory, and Gemini
rate-limit handling that now backs off using Google's actual
suggested delay instead of failing outright.
Retrieval: built and unit-tested (mocked LLM/embeddings) - **live
verification against your real index still needed**, run
`scripts/ask.py` and `scripts/test_module_isolation.py`.

Next: Conversational Memory (multi-turn sessions).

## Local setup

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) if you don't have it.
2. Copy `.env.example` to `.env` and fill in:
   - `SHANGRILLA_DATA_ROOT` - path to your local Shangrilla documents folder (must be **outside** this repo)
   - `GEMINI_API_KEY`, `OPENROUTER_API_KEY`
3. Start Postgres + pgvector:
   ```
   docker compose up -d
   ```
4. Create a virtual environment and install dependencies:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```
5. Run the tests:
   ```
   pytest
   ```
6. Point the pipeline at your real documents:
   ```
   python3 scripts/validate_ingestion.py
   ```
   Prints a summary of what was discovered, what loaded successfully,
   what failed validation and why, what was skipped, and any
   document_id collisions (likely duplicate/revised files).
7. Confirm your embedding dimension matches the configured value:
   ```
   python3 scripts/check_embedding_dimension.py
   ```
8. Run the full indexing pipeline (chunks + embeddings into Postgres):
   ```
   python3 scripts/run_indexing.py
   ```
9. Ask a question against one module:
   ```
   python3 scripts/ask.py CO "What triggers the cost estimate check?"
   ```
10. Verify cross-module isolation holds on your real data:
    ```
    python3 scripts/test_module_isolation.py
    ```

## Project structure

See `docs/architecture.md`, section F, for the full planned layout. Only
`app/config/` and `app/ingestion/metadata/` exist so far, matching what's
actually been built.
