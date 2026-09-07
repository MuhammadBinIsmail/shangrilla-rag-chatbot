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
Retrieval: **done.** Verified end-to-end on the real index: grounded,
correctly-cited answers (confirmed against known real content), and
zero cross-module leakage across all seven modules (10/10 chunks each,
via `scripts/test_module_isolation.py`).
Conversational Memory: **done.** Verified on the real database: correct
grounded answers with citations, correct refusal on out-of-scope
questions (tested against CEO/weather/ML questions - none hallucinated),
and full session isolation confirmed via `scripts/test_session_isolation.py`.
API Layer: **done.** Verified with a real running server: correct
JSON responses, correct grounding and citations, and real section
titles from actual document body content (first live confirmation the
chunker's section-splitting works correctly on real body text, not
just the metadata block).
Chat UI: built (Chainlit) - **no automated test coverage possible**
(Chainlit has no test utilities; mocking its WebSocket/context
internals would be fragile for little value) - needs live
verification by running it and clicking through.

Next: Hardening (retries, edge cases, error handling).

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
11. Have a multi-turn conversation:
    ```
    python3 scripts/chat.py CO
    ```
12. Verify cross-session isolation holds on your real database:
    ```
    python3 scripts/test_session_isolation.py
    ```
13. Run the API server:
    ```
    uvicorn app.api.main:app --reload
    ```
    Then try it: `curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d '{"session_id": "test1", "message": "hello", "module": "CO"}'`
    Interactive docs at `http://localhost:8000/docs`.
14. Run the chat UI:
    ```
    chainlit run ui/app.py
    ```
    Opens in your browser - pick a module, then chat.

## Project structure

See `docs/architecture.md`, section F, for the full planned layout. Only
`app/config/` and `app/ingestion/metadata/` exist so far, matching what's
actually been built.
