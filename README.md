# Shangrilla RAG Chatbot

Conversational RAG chatbot over Shangrilla Foods' SAP FSD/TSD documentation,
scoped per-module (CO, FI, MM, PP, QM, TM, WM), with session-isolated
conversation memory.

Full design record: `docs/architecture.md` (decisions logged round by round,
including what was tried and corrected as real data came in - not just the
final state).

## Status

M1 in progress: configuration, metadata schema, and ID normalization are
in place and tested. Ingestion pipeline (file discovery, loaders, chunking)
is next.

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

## Project structure

See `docs/architecture.md`, section F, for the full planned layout. Only
`app/config/` and `app/ingestion/metadata/` exist so far, matching what's
actually been built.
