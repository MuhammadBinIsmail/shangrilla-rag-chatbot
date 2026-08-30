# Shangrilla RAG Chatbot

Conversational RAG chatbot over Shangrilla Foods' SAP FSD/TSD documentation,
scoped per-module (CO, FI, MM, PP, QM, TM, WM), with session-isolated
conversation memory.

Full design record: `docs/architecture.md` (decisions logged round by round,
including what was tried and corrected as real data came in - not just the
final state).

## Status

Configuration & Metadata Schema: done, tested.
Document Discovery & Loaders: done, tested against synthetic fixtures
**and validated against the real corpus**. One real bug found and
fixed: TSD metadata extraction originally assumed a 2D table layout
needing pdfplumber; a real file proved PyMuPDF's plain text extraction
already gives a clean single-column label/value sequence, no table
detection needed. See docs/architecture.md for the diagnostic.

Known real-data findings (not code bugs, need manual review):
a few source documents have internal WRICEF ID fields that don't match
their filenames (see architecture doc) - flagged by the collision
detector, worth checking with whoever maintains the SAP docs.

Next: Chunking & Vector Indexing.

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

## Project structure

See `docs/architecture.md`, section F, for the full planned layout. Only
`app/config/` and `app/ingestion/metadata/` exist so far, matching what's
actually been built.
