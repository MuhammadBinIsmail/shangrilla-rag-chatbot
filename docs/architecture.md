# Enterprise RAG Chatbot — Architecture & Requirements Analysis

This is the analysis phase, not implementation. No code yet, per your master prompt.

---

## Round 2 — Decisions Log (applied on top of Round 1)

| Question | Your answer | Impact |
|---|---|---|
| Deployment | Files stay local on your Mac; embeddings/LLM calls go to external APIs | Resolves B.6 — this is a **hybrid** architecture, not full on-prem or full cloud. Documents never leave your machine; only text sent for embedding/generation goes out over the API |
| Module set | Fixed at CO/FI/MM/PP/QM/TM/WM, no growth | `module` becomes a closed enum, not a free string — simpler validation |
| Role-based filtering | **Removed entirely** | Metadata schema drops `role`; retrieval filter drops the role clause; A.5, B.4, session `role` column, and roadmap M6 are all void — struck through below rather than deleted, so the record stays honest |
| Corpus shape | Not FSD(docx)+TSD(pdf) only — MM has Excel FSDs, PP has a zip, and there are unlisted extra files/folders | **Architecture change**, not just a data point — see below |
| LLM / embeddings | Gemini + OpenRouter, my pick on the split | See reasoning under section E |
| Database | Open choice, want efficient + convenient | PostgreSQL + pgvector via Docker Compose, finalized |
| UI | Needed, market-ready | Chainlit, finalized — reasoning under E |
| Code style | Idiomatic Python for the main project | Standing convention: PEP 8, type hints throughout, no note-worthy architecture impact, just a delivery standard |

### On the file inventory specifically

You don't need to enumerate every file — that would fight the "generalized pipeline" goal anyway. What changes is that **file discovery can no longer assume exactly two extensions per module**. Concretely:

- **`.xlsx` becomes a third supported document type** (MM's 4 Excel FSDs aren't a one-off — treat it as a first-class loader, not a special case).
- **`.zip` is not a document type, it's a container.** The pipeline gets a pre-ingestion "unpack" step: any `.zip` found during discovery is extracted into a staging folder, and its contents re-enter normal discovery (so the core pipeline never needs zip-aware branching).
- **Anything else** (the "other folders" you mentioned) gets **logged and skipped**, not silently ignored and not a hard failure. This is what makes the pipeline robust to a corpus you haven't fully catalogued — discovery only needs to know what it *does* support; everything else surfaces in an ingestion report you can review later.

One thing I do need eventually (not urgent, default noted): where does metadata live in an Excel FSD — first sheet, a dedicated "Metadata" sheet, fixed header rows? I'll design the extractor with a **first-sheet, first-N-rows** default; tell me if that's wrong when you get to a real file.

---

## Round 3 — Metadata Schema Confirmed From Real Samples

| Finding | Impact |
|---|---|
| WRICEF ID appears identically in both FSD and TSD (`CO-CE-001`) | **Supersedes B.2** — `document_id` is now `{wricef_id}-{doc_type}` (deterministic, human-readable), not a content/filename hash. WRICEF ID also serves as the FSD↔TSD cross-reference key |
| TSD metadata is a table, not line-based text | **Adds `pdfplumber`** for first-page table extraction on TSDs specifically; PyMuPDF remains the body-text/page-number workhorse for the rest of the document |
| TSD `SAP Module` field can name more than one module (e.g. "Controlling (CO) / PP") | Folder location stays authoritative for the `module` filter (confirms the B.7-era default was right); this field is stored as descriptive metadata only, and doubles as a good module-isolation test case later |
| Schema validated against **CO only so far** | Working hypothesis is that FSD/TSD field structure is shared across modules and only values differ — not yet confirmed. Get one more pair from a different module when convenient (not blocking) to validate before M2 is called "done" |

Updated field schema:

| Field | Source | Notes |
|---|---|---|
| `document_id` | derived | `{wricef_id}-{doc_type}`, lowercased |
| `wricef_id` | extracted | cross-reference key linking FSD↔TSD pairs |
| `module` | folder path | authoritative for retrieval filtering, not parsed text |
| `doc_type` | FSD / TSD | |
| `title` | extracted (TSD) | fallback to filename where absent (e.g. FSD, pending confirmation it doesn't have an equivalent line) |
| `lob`, `process`, `workpackage` | extracted (FSD) | `lob` used as a cross-check against folder `module`, not source of truth |
| `object_type`, `sap_module`, `badi_name`, `tcode_method`, `complexity`, `project_code`, `landscape` | extracted (TSD) | |

---

## Round 4 — Schema Validated Across All Seven Modules; Round 3 TSD Fields Corrected

Real FSD/TSD samples now seen from all seven modules (CO, FI, MM, PP, QM, TM, WM).

**Holds up everywhere:** WRICEF ID present and populated in every sample — the only field the pipeline requires without exception. FSD's four-line label block and TSD's heading→title→table structure hold in every module.

**Corrected:** Round 3 assumed the TSD table's middle fields were fixed names (`badi_name`, `tcode_method`, etc.). Real samples show they vary by Object Type — FI uses `Program`/`Custom Table`, MM uses `Programs`/`T-Codes`, PP/QM/TM use `Program Name` (+ `Adobe Form` or `Transaction Code`), WM uses `Process`; TM's table even runs a 5th row. A fixed field list would break on module-specific labels.

**Fix:** extract only what's genuinely stable everywhere as named columns; capture the rest as a flexible dict.

| Field | Doc type | Required | Notes |
|---|---|---|---|
| `wricef_id` | both | **Yes** | only field reliable across all seven modules; also FSD↔TSD cross-reference key |
| `lob`, `process`, `workpackage` | FSD | No | free text; not cross-validated against each other or against `module` (PP shows PROCESS=WORKPACKAGE≠WRICEF ID; QM shows both blank; MM's LOB is a process name, not a module name) |
| `short_title` | FSD | No | unlabeled bracketed line after WRICEF ID — present in MM/PP/QM/TM/WM samples, absent in CO/FI |
| `title` | TSD | Yes | line between the doc-type heading and the table, present in every sample |
| `object_type`, `sap_module`, `complexity`, `project_code`, `landscape` | TSD | Yes | stable everywhere, though not always the same row position |
| `technical_details` | TSD | No | **catch-all dict** for whatever else the table contains (BAdI Name, Program, T-Code, Adobe Form, Process, etc.) — stored as JSONB, not fixed columns. This is what makes one TSD config cover all seven modules with no per-module branching |

**Resilience addition:** if in-document WRICEF ID extraction is blank or fails validation, fall back to a regex pull from the filename before marking the file a validation failure — several real filenames embed it directly (`TM_F_0008_...pdf`).

**Still unverified:** Excel FSD layout (no sample yet, first-sheet/first-N-rows default stands); real PDF byte-level extraction (everything above is validated against clean pasted text, not actual `pdfplumber`/`PyMuPDF` output) — closes at M2 when code runs against the real corpus, with a per-file pass/fail in the ingestion report rather than an all-or-nothing result.

---

## Round 5 — Document Discovery & Loaders: Closed Out

Validated against the full real corpus (158 files) across several
rounds of real-file diagnosis and fixes:

- Round 3-4's assumption that TSD metadata needed pdfplumber table
  extraction was wrong for most files - PyMuPDF's plain text gives a
  clean single-column sequence for the majority. Table extraction
  remains a fallback for the minority that genuinely use a bordered
  grid (confirmed: PP-I-005, WM_F_001).
- Landscape and Project Code are NOT always present (confirmed in
  multiple real files) - both made optional, not required.
- Field order varies (Landscape can appear before OR after Project
  Code) - block-end detection anchors on the reliable "TMC Project
  Manager" signature marker, not on any one field's position.
- Values and labels both wrap across lines in some files - merged back
  before pairing, using two narrow, evidence-backed rules (continuation
  starts with '(' or lowercase = wrapped value; previous line ends
  with '/' = wrapped compound label).
- A WRIECF ID typo (one real file) is handled via a config-level label
  alias, not a code branch.

**Final result: 119/158 succeed.** Every one of the 39 remaining
failures was individually confirmed as genuinely not an FSD/TSD
(scanned PDFs with no text layer, Outlook email printouts, working
spreadsheets, two draft FSDs with no WRICEF ID ever assigned) - not
parsing bugs. Collision resolution (most recently modified file wins)
is implemented for genuine duplicates/revisions; two collisions where
a file's content disagrees with its own filename still need manual
review, since no automated signal can resolve that correctly.

---

## Round 6 — Gemini API Access: Account-Specific, Not Regional

Hit a `403 PERMISSION_DENIED: Your project has been denied access`
error when first calling the Gemini embeddings API - persisted across
a fresh API key, fresh Google Cloud project, enabling the Generative
Language API explicitly, and removing all key restrictions. Matched
the exact pattern of several public Gemini API forum/GitHub reports
(including one from the same city), which all pointed to an
account-level access flag only resolvable by Google, not a config fix.

Resolved by switching to a different Google account and generating a
fresh key there - worked immediately, confirming this was tied to the
specific account, not the region, the project config, or the code.
Original design (Gemini direct, `gemini-embedding-001`, pinned,
asymmetric document/query task types) stands unchanged.

Real embedding dimension confirmed via live call: **3072**, matching
the value already configured in `app/database/models.py`.

---

## Round 7 — Chunking & Vector Indexing: Closed Out

**106/106 resolved documents indexed** into Postgres/pgvector with
real Gemini embeddings - the full pipeline (discover → load → chunk →
embed → store) now runs end to end against the real corpus.

Two real bugs found running it for real, both fixed with regression
tests:

- **Runaway chunking (critical)**: the sliding-window chunker's
  overlap math could make `start` move backward instead of forward
  when an early sentence boundary was found close to the window
  start, followed by a long run of text with no more periods (real
  case: a short line followed by an identifier list). This produced
  an unbounded, ever-growing list of near-duplicate chunks - confirmed
  to consume 40+ GB of swap and get the process killed by macOS.
  Fixed with two independent guards: only snap to a boundary that
  keeps at least half the target chunk size, and `start` is now
  hard-guaranteed to strictly increase every iteration regardless of
  the boundary logic. A second, independent cap in `chunk_document`
  aborts loudly if any document ever produces an unreasonable number
  of chunks, as insurance against any future regression of this bug
  class.
- **Rate-limit handling**: the free tier's 100-requests/minute cap
  was being hit repeatedly with no real backoff, burning through
  quota windows immediately rather than waiting for them to reset.
  Fixed by parsing Google's actual suggested `retryDelay` from the
  429 response and waiting that long (plus a small buffer) before
  retrying, up to 3 attempts, with a safe fallback when the delay
  can't be parsed.

Also fixed: the SDK was silently alternating between the direct
Gemini API and Vertex AI (different product, different quota pool)
depending on ambient environment detection - `vertexai=False` is now
explicit. And the pipeline is resumable - a document already
committed to the store is skipped on the next run, so a mid-run
failure never means re-embedding (and re-billing quota for) work that
already succeeded.

---

## A. Requirement Interpretation

| Business statement | Technical requirement |
|---|---|
| "Conversational chatbot over company docs" | Multi-turn RAG system with server-side conversation state keyed by session |
| "Seven modules, FSD (docx) + TSD (pdf)" | Two document-type loaders, one metadata schema, module-aware ingestion |
| "Single generalized extraction pipeline" | Configuration-driven metadata extraction (field mappings/rules per doc type, not per module) — not literally one hardcoded regex set for all seven modules if their layouts differ |
| "Don't accidentally retrieve CO when PP is selected" | Retrieval must be a **hard metadata filter** (`module == selected`), not just semantic similarity hoping same-module content ranks higher |
| ~~"Role-based filtering, eventually"~~ | **Removed in Round 2** — no `role` field anywhere in the design |
| "Session isolation, mandatory" | No shared/global memory object; state must be re-derived per request from a persistent store keyed by `session_id` |
| "Database, not sure which" | Separate concerns: app/session/metadata DB vs vector store vs (later) object storage — don't default to one DB for everything |
| "Survive 3–4 mentor review rounds" | Modularity: ingestion, retrieval, generation, session, and persistence must be independently swappable/testable |

---

## B. Assumptions I'm Flagging (please confirm or correct)

1. **"Single generalized pipeline" ≠ "one hardcoded parser."** I'm assuming this means *one codebase, configuration-driven*, where module/doc-type differences are expressed as data (field-mapping configs) rather than as branching logic per module. If FSD/TSD layouts are wildly inconsistent across modules, we'll still want one pipeline, just parameterized — I don't think this contradicts your mentor's guidance, but I want to state the interpretation explicitly.
2. ~~Document IDs (`document_id`) are pipeline-generated...~~ — **resolved in Round 3**: real FSD/TSD samples both carry a `WRICEF ID` that's identical across the pair. `document_id = {wricef_id}-{doc_type}`.
3. **"Sequential chain" framing is a simplification, not a requirement.** Module selection is *session state*, not something that needs to happen inside an LLM chain at all — it's an app-layer decision (has this session already picked a module? if not, ask). I'll treat this as your working mental model rather than a hard implementation instruction, and design the actual orchestration around what the state machine needs (see section D/G).
4. ~~Roles are an enumerable, closed set...~~ — **moot, role-based filtering removed in Round 2.**
5. **"Metadata on the first page"** is consistent enough across FSD/TSD to be machine-extractable (e.g., a metadata table or fixed heading block), not free-text prose that would require an LLM to parse reliably. If it's the latter, extraction gets meaningfully harder and does justify LLM-based extraction for that one step (still not for the rest of the pipeline). Now also applies to the first sheet of Excel FSDs — same open question.
6. ~~Deployment target is unknown~~ — **resolved**: local file storage, external APIs for embeddings/LLM. See Round 2 log.
7. **New (Round 2): unlisted "other files/folders" per module are assumed non-essential to answer quality** — since the pipeline will log-and-skip anything it doesn't recognize rather than fail, this is a safe default, but it does mean the corpus you actually search over is whatever the pipeline *classifies*, not literally everything in the folder. Worth a periodic glance at the skip-log so nothing important silently falls out.

---

## C. Non-Confidential Information I Need From You

Specific, not "tell me more":

1. **Metadata block format** — still open, not urgent until M1. Paste (or synthetically recreate) the first-page metadata layout of one FSD and one TSD when convenient.
2. ~~Module set stability~~ — **answered: fixed, no new modules.**
3. ~~Role model~~ — **moot: role-based filtering removed.**
4. ~~Corpus size~~ — **answered**, see the Round 2 log above. Enough to size decisions; no full inventory needed.
5. ~~Deployment constraints~~ — **answered: local files, external APIs.**
6. ~~Existing infra mandate~~ — **answered: open choice, going with PostgreSQL + pgvector.**
7. ~~Interface expectation~~ — **answered: proper UI, going with Chainlit.**
8. **Python version constraint** — still open, defaulting to 3.11+ unless you tell me otherwise.
9. The `id="..."` note — no response needed unless something looked off to you; treating it as a drafting artifact.

**Still open, low urgency:**
- Excel FSD metadata location (first sheet, dedicated sheet, fixed rows?) — defaulting to first-sheet/first-N-rows for now.
- Whether zip contents should always be extracted-and-ingested, or whether some zips are just backups/irrelevant — defaulting to "extract and let normal discovery classify what's inside."

---

## D. Proposed End-to-End Architecture

**Ingestion (offline/batch) — updated for Round 2 corpus shape:**
```
Source Folder (per module)
  → File Discovery (recursive walk, module subfolders)
  → Pre-extraction: any .zip found → unpack to staging → re-enter discovery
  → File Type Identification
        .docx → FSD
        .pdf  → TSD
        .xlsx → FSD (Excel)
        anything else → logged to skip-report, NOT ingested, NOT a pipeline failure
  → Document Loading (structure-preserving, per-type loader, see E)
  → Metadata Extraction (first block/sheet, config-driven per doc type)
  → Metadata Validation (required fields present & well-formed → else: record failure, don't ingest)
  → Content Cleaning
  → Heading/Section-Aware Chunking (docx/pdf) or Row/Sheet-Aware Chunking (xlsx)
  → Metadata Propagation to every chunk (document_id, module, doc_type, page_or_sheet, section, chunk_id, version)
  → Embedding Generation (Gemini, gemini-embedding-001 — pinned, see E)
  → Vector Store Upsert (keyed by deterministic chunk_id, so re-ingestion overwrites rather than duplicates)
  → Ingestion Status recorded in app DB (success/failure/skipped per file, timestamp, version)
```

**Conversation (online/request path):**
```
Request arrives with session_id
  → Load session state from DB (module selected? history?)
  → If no module selected yet → ask user to select (no retrieval call)
  → History-aware query reformulation (only if history exists)
  → Build metadata filter: module == selected
  → Retriever.invoke(reformulated_query, filter=...)
  → Prompt assembly (system rules + retrieved chunks w/ citations + question)
  → LLM generation (OpenRouter, model swappable — see E)
  → Persist turn (user msg, assistant msg, module, retrieved doc_ids) to session store
  → Log (ids, latency, module, filter — not raw content)
  → Return answer (+ source references) to Chainlit UI
```

---

## E. Technology Recommendations

| Component | Recommendation | Why | Alternative considered |
|---|---|---|---|
| Python | 3.11+ | Current, stable typing/perf features | — |
| LLM (generation) | **OpenRouter**, defaulting to a Gemini model (e.g. `google/gemini-2.5-flash`) through it | One API key/client gives you generation model flexibility — you can swap to a different model later (cost, quality, or a mentor request to compare models) by changing a config string, not code. Generation quality tolerates this kind of provider abstraction fine — any coherent answer from the retrieved context is acceptable regardless of which underlying model produced it | Calling Gemini directly — rejected only because it locks you into one provider with no swap path; still a fine choice if you'd rather have one fewer account to manage |
| Embeddings | **Google Gemini API directly**, `gemini-embedding-001` (pinned, not auto-routed) | Currently Google's GA, top-MTEB-ranked text embedding model — strong choice on quality alone. More importantly: **embedding consistency matters in a way generation doesn't** — every chunk and every query must be embedded by the *exact same* model version, or the vector space stops being comparable. OpenRouter's routing/failover is a genuine strength for chat, but a liability for embeddings if it ever serves a different underlying model on retry. Pinning directly to Gemini avoids that risk entirely | OpenRouter's `/embeddings` endpoint (confirmed to exist and support Gemini/OpenAI/Cohere/Voyage models) — considered and set aside specifically for the pinning reason above, not because it lacks the capability |
| DOCX loader (FSD) | Direct `python-docx` parsing wrapped as LangChain `Document`s (custom loader) | Preserves heading levels and paragraph structure, which the chunker needs; LangChain's default `Docx2txtLoader` flattens to plain text and loses this | `Docx2txtLoader` — rejected, loses structure |
| PDF loader (TSD) | `PyMuPDF` (fitz) for body text + page numbers; `pdfplumber` for first-page **table** extraction specifically | PyMuPDF is fast and reliable for the bulk of the document. But real TSD metadata (confirmed Round 3) is a 2-column table, and plain text-stream extraction risks scrambling row/column order — `pdfplumber`'s explicit `extract_tables()` handles that correctly. Using it only where it's needed (page 1) avoids paying its extra weight across the whole document | `unstructured` — heavier dependency, unnecessary once the actual layout (a simple table) is known |
| Excel loader (FSD, MM) | `openpyxl`, read sheet-by-sheet | Preserves cell structure and sheet names as metadata (`sheet` instead of `page`); avoids `pandas`' tendency to silently coerce/guess types when a sheet contains a metadata header block above tabular data | `pandas.read_excel` — fine for pure tabular sheets, but riskier for a mixed metadata-header-plus-table layout until we've actually seen one of these files |
| Zip pre-processing | `zipfile` (stdlib), extract to a staging dir before discovery runs | Keeps the core pipeline free of archive-aware branching — a zip is just a source of more files, not a new document type | Parsing zip contents in-memory without extraction — rejected, adds complexity for no real benefit at this corpus size |
| Text splitter | Custom heading/section-aware splitter (split on parsed headings first, character-split only within long sections) | Chunk boundaries should respect document structure, not cut mid-section — matters more than embedding model choice for retrieval quality here | Plain `RecursiveCharacterTextSplitter` — rejected as sole strategy, acceptable only as the fallback within a section |
| Vector store + app DB | **PostgreSQL + pgvector**, run via Docker Compose | Finalized. Unifies vector store with the app/metadata DB → metadata and vectors stay transactionally consistent; one `docker compose up` gives you the whole DB layer on your Mac with no manual install, which is the "convenient" half of your ask, while still being a real production-credible choice (the "efficient/market-ready" half) | `Chroma` — simpler file-based store, no Docker needed, but you'd then run two separate stores (app data + vectors) with no transactional link between them; `SQLite` for app data — rejected, no vector extension and awkward with pgvector's Postgres-only nature |
| UI | **Chainlit** | Purpose-built for LLM chat apps: per-session state, streaming responses, and a built-in side panel for showing source/citation elements — which maps directly onto your source-traceability requirement instead of you having to build that panel yourself. Pure Python, so it doesn't conflict with the "Python-style coding" requirement, and it reads as a deliberately chosen tool for this problem rather than a generic dashboard | `Streamlit` — more familiar to some, but it's a general dashboard tool; you'd hand-roll chat bubbles, streaming, and session handling that Chainlit gives you for free; a custom React frontend — rejected as disproportionate effort for what this project needs |
| App/relational DB | PostgreSQL | JSONB for flexible metadata, native pgvector support, mature | MySQL — fine if mandated (C.6), but no first-class vector extension |
| Orchestration | LCEL (explicit `RunnableLambda`/`RunnableParallel` composition), not a prebuilt monolithic chain | Module/role resolution and filter construction are app logic, not LLM reasoning — LCEL lets us compose only what's needed | `ConversationalRetrievalChain` — deprecated pattern, rejected; **LangGraph** — worth adopting *if* the conversation flow grows branchy (module switching mid-chat, clarifying questions); flagged as a likely upgrade for session-state handling once M5 is reached, not needed on day one |
| History-aware retrieval | LCEL-based query condensation (reformulate follow-up → standalone query via LLM), skipped entirely on turn 1 | Matches your "who is responsible for step 3" example directly | `ConversationalRetrievalChain`'s built-in condensation — deprecated |
| API framework | FastAPI | Async, Pydantic validation, dependency injection maps cleanly onto per-request session loading | Flask — rejected, weaker async story |
| Session store | Postgres tables (`sessions`, `messages`), reloaded per request | Solves both persistence *and* isolation without a second moving part; scales across multiple API workers/replicas since state isn't held in process memory | Redis — deferred; add only if latency profiling later shows it's needed |
| Logging | `logging` + structured JSON output | Greppable, avoids ad hoc string logs | `structlog` — fine equivalent, pick either |
| Testing | `pytest` | Standard; unit tests for extraction/chunking (deterministic, no LLM calls), integration tests for retrieval isolation | — |

---

## F. Project Structure

```
app/
  config/            # settings, module enum, field-mapping configs
  ingestion/
    discovery.py      # recursive walk, extension routing, skip-report
    unpack.py          # zip → staging extraction
    loaders/           # docx_loader.py, pdf_loader.py, xlsx_loader.py
    metadata/           # extraction rules, validators, normalizers
    chunking/            # heading/section-aware + sheet-aware splitters
    pipeline.py            # orchestrates discovery → ... → vector upsert
  embeddings/           # gemini_client.py (pinned model)
  vectorstore/          # pgvector client wrapper
  retrieval/             # filter construction, retriever composition
  chains/                # LCEL runnables: reformulation, RAG chain
  llm/                   # openrouter_client.py
  sessions/              # session state load/save, isolation boundary
  database/              # SQLAlchemy models: sessions, messages, documents, ingestion_status
  api/                   # FastAPI routers (backing the Chainlit app)
  ui/                    # chainlit app entrypoint, module-selection start screen
  logging/
  tests/
    unit/
    integration/
```

---

## G. Retrieval Flow (module + query + history → answer)

1. Session lookup by `session_id` → `{module, history}`.
2. No module yet? → app asks user to pick one; **no retriever call happens** until then.
3. History present? → LLM condenses `history + latest question` into a standalone query. First turn: skip this call entirely (no need to pay for it).
4. Build filter: `{"module": selected_module}` — single clause now that role is out of scope.
5. `retriever.invoke(query, filter=filter)` → top-k chunks, each carrying `document_id, module, page_or_sheet, section, chunk_id`.
6. Prompt assembly: system instructions (answer only from provided context; say so explicitly when the answer isn't in the retrieved chunks; never use another module's info even if it seems relevant) + chunks + question.
7. LLM generates the answer.
8. Persist both turns + which `document_id`s were used, to the session store — this is also what makes answers auditable later (source traceability requirement).
9. Log ids/latency/module — never raw chunk text or full message content by default.

---

## H. Session Isolation Design

- Every request carries a `session_id` (server-issued at session start, or client-generated UUID validated server-side).
- **No shared Python object holds conversation state.** State lives in the `sessions`/`messages` tables, loaded fresh each request.
- `module` and `role` are columns on the session row, not attributes of any long-lived in-memory object.
- Because state is reloaded from the DB per request rather than mutated in shared memory, this holds even under concurrency and across multiple API worker processes/replicas — the DB *is* the isolation boundary, not a Python dict.
- This gets encoded directly as a test: two sessions, distinct facts injected into each, assert zero leakage — literally your Session A / Session B example, turned into an integration test in M5.

---

## I. Risks & Controls

| Risk | Control |
|---|---|
| Wrong/missed metadata extraction | Validation step fails loudly (recorded, not silently skipped); synthetic test fixtures per doc type |
| Module leakage in retrieval | Hard metadata filter at the vector-store query level, not just prompt instructions; isolation test per module pair |
| Cross-session memory leakage | DB-backed, per-request state reload (section H); explicit two-session test |
| Unclassified files silently dropped from the corpus | Skip-report generated per ingestion run, reviewable — not a silent gap |
| Embedding model drift (if provider auto-routes) | Embedding model pinned directly to Gemini, not routed through a service that could serve a swapped model on retry |
| Excel FSDs with mixed metadata-header + tabular layout mis-parsed | `openpyxl` cell-level parsing instead of `pandas` auto-typing; validation step catches malformed extraction same as docx/pdf |
| Duplicate indexing on re-ingestion | Deterministic `chunk_id`/`document_id` generation → upsert, not insert |
| Bad chunking (mid-sentence/mid-table cuts) | Heading/section-aware splitter, page/section metadata retained for debugging |
| Hallucination | Prompt constrains to retrieved context + "not found in documentation" fallback instruction; not eliminated, only reduced |
| DB / vector-store inconsistency | Same Postgres instance for both (pgvector) keeps writes transactionally aligned |
| Ingestion failures (malformed doc, missing metadata) | Per-file status recorded, pipeline continues past one bad file rather than aborting the batch |
| Library/API drift (LangChain moves fast) | Pin versions; isolate LangChain usage behind thin wrapper modules so upgrades touch one layer |

---

## J. Implementation Roadmap

- **M0** (done): requirements + Round 2 decisions locked in
- **M1**: metadata schema finalized (docx/pdf/xlsx field-mapping configs); Docker Compose Postgres+pgvector spun up
- **M2**: ingestion pipeline — discovery (incl. zip unpack, skip-report) + all three loaders + extraction + validation, no vectors yet, tested against synthetic FSD/TSD/Excel samples
- **M3**: chunking + Gemini embeddings + pgvector indexing; per-module filter isolation tests
- **M4**: single-turn RAG query (module passed explicitly, no session/memory yet); cross-module contamination tests
- **M5**: session + conversation memory (DB-backed) + history-aware retrieval; Session A/B/C isolation tests
- **M6**: FastAPI layer wrapping the pipeline; logging/observability wired through
- **M7**: Chainlit UI — module-selection start screen, chat, source panel wired to the API
- **M8**: hardening — retries, duplicate/version handling, failure-path tests
- **M9**: polish for mentor review — source citations in responses, docs

---

**Next step**: whenever you're ready, send a synthetic (fake-data) sample of one FSD's first-page metadata block and one TSD's — that's the one thing still blocking M1. Everything else is enough to start.

## Round 8 — Retrieval: Built, Live Verification Pending

Retrieval and single-turn generation built:
- `app/retrieval/retriever.py` - module-filtered cosine similarity
  search via pgvector's `cosine_distance()`. The module filter is a
  hard SQL WHERE clause, not a semantic hope - a chunk from another
  module cannot come back regardless of similarity score.
- `app/llm/openrouter_client.py` - generation via OpenRouter, default
  model `google/gemini-2.5-flash`, swappable.
- `app/retrieval/qa.py` - assembles a prompt that constrains the LLM
  to only the retrieved context, requires WRICEF ID citations, and
  explicitly instructs it to say so rather than guess when the answer
  isn't present.

Verified so far (mocked LLM/embeddings, no live DB needed): prompt
assembly, module filter is correctly passed through to retrieval,
citation formatting, source traceability. NOT yet verified: actual
retrieval quality and cross-module isolation on the real, live index
- that needs `scripts/test_module_isolation.py` run against the real
Postgres instance, since the whole point is confirming the hard SQL
filter behaves as designed on real data, not just trusting the
architecture is correct by construction.


## Round 9 — Retrieval: Verified on Real Data, Closed Out

`python3 scripts/ask.py CO "What triggers the cost estimate check on process order release?"`
returned a grounded, correctly-cited answer matching CO-CE-001's real
content (BAdI `WORKORDER_UPDATE`, method `AT_RELEASE`, order category
check) - the same file diagnosed character-by-character back in
Round 3 to fix the original TSD parser design.

`scripts/test_module_isolation.py` against the real index: **all
seven modules PASS, 10/10 chunks each, 0 leaked.** This was the one
requirement stated at the very start of this project - verified
empirically on real data, not just true by architecture.

One real bug found and fixed along the way: `max_tokens` was left
unset on the OpenRouter generation call, defaulting to the model's
max output (65535 for gemini-2.5-flash) - OpenRouter checks credit
balance against that worst case before generating anything, causing
a 402 even for a small, normal request. Fixed by capping it
explicitly (default 1024, configurable).

## Round 10 — Conversational Memory: Built, Live Verification Pending

Multi-turn conversation built on top of single-turn retrieval:
- `app/database/models.py` - added `Session` and `Message` tables.
- `app/database/session_store.py` - all reads go back to the DB, no
  conversation state cached in a shared Python object. This is the
  actual isolation mechanism, not just a design intention.
- `app/retrieval/conversation.py` - history-aware query reformulation
  (skipped on turn 1, no history to reformulate from), session-bound
  module (set once on first message, ignored after), message
  persistence.

Critical test (fakes, no live DB needed): two sessions, distinct
injected facts, assert neither's history contains the other's -
`test_two_sessions_never_share_history_or_module`, passing.

NOT yet verified: the same guarantee on the real, live database -
that needs `scripts/test_session_isolation.py` run for real, since a
correct-by-construction guarantee and a confirmed-on-real-data
guarantee have consistently been treated as different levels of
confidence throughout this project.


## Round 11 — Conversational Memory: Verified on Real Data, Closed Out

Real multi-turn session against CO module: a grounded, correctly-cited
answer on a real technical question (ZME_PROCESS_REQ_CUST,
ZCL_IM_ME_PROCESS_REQ_CUST - actual CO-CE-003 content), followed by
three deliberately out-of-scope questions (company CEO, weather,
machine learning) - all three correctly refused rather than
hallucinated, confirming the "answer only from context" system prompt
constraint holds under real use, not just in the happy path.

`scripts/test_session_isolation.py` against the real database: two
sessions, distinct injected markers, neither leaked into the other,
modules stayed correctly bound per session. Same guarantee already
proven with fakes, now confirmed on real data - this project's
consistent bar for calling something done.

One cosmetic observation, not a bug: retrieval always returns its
top-k nearest chunks regardless of true relevance (no distance
threshold), so "sources" are still listed even on questions the LLM
correctly refused to answer from them. The LLM handles this
correctly (ignores irrelevant context, says so explicitly), but
displaying sources alongside an "I don't know" is a little
misleading. Worth a future refinement (a distance cutoff below which
sources aren't shown), not urgent.


## Round 12 — API Layer: Built, Live Verification Pending

FastAPI app wrapping the conversation pipeline:
- `app/api/main.py` - `/chat`, `/sessions/{id}/history`, `/modules`,
  `/health`. Uses the modern `lifespan` context manager (not the
  deprecated `on_event("startup")`) to set up the engine and client
  singletons once per process.
- `app/api/dependencies.py` - DB session is created fresh per request
  via FastAPI's dependency injection, not shared - the same isolation
  mechanism from section H, now applied at the HTTP layer specifically
  because this is where "multiple concurrent requests" first becomes
  a real possibility rather than a theoretical one.

Tested via FastAPI's TestClient with dependency overrides (fake
session store, mocked embedder/LLM/answer_query) - no live DB/API
calls needed for these. Notably, the two-session isolation test from
Round 10 is now re-proven through the actual HTTP layer
(`test_two_sessions_isolated_through_the_api`), not just the
underlying Python function - a request boundary is a meaningfully
different thing to get right than a function call boundary.

NOT yet verified: a real running server, real concurrent requests,
real Postgres. That needs `uvicorn app.api.main:app` run for real.


## Round 13 — API Layer: Verified on Real Data, Closed Out

Real HTTP round-trip: `curl -X POST /chat` against a running
`uvicorn` server, real Postgres, real Gemini embeddings, real
OpenRouter generation. Correct JSON response shape, correct grounded
answer with citation, and a small but meaningful confirmation - the
returned section titles (`3.1 LINKED PROCESSES`, `4.4 VALIDATION`,
`9 TESTING SCENARIOS`) are real headings from TSD_CO-CE-001's actual
body content, the first live proof that the heading-aware chunker
(Round 7) works correctly on real document body text, not just the
synthetic/metadata cases it was tested against directly.

One real bug found and fixed: `app/api/main.py` never called
`load_dotenv()` - every CLI script does this first, but the API
module was missed, so `GEMINI_API_KEY` was never actually in the
environment when uvicorn imported the module directly.


## Round 14 — Chat UI: Built, Live Verification Pending

`ui/app.py` - Chainlit UI talking directly to the conversation
pipeline (not through the FastAPI layer, avoiding an unnecessary
network hop for a single-process deployment). Module selection via
`AskActionMessage` buttons (verified against the real 2.12.0 API, not
assumed), then multi-turn chat with source citations shown as side
panel elements. Fresh DB session per message, same isolation
principle as the API layer.

No automated tests - Chainlit has no test utilities, and mocking its
WebSocket/context internals for a UI this thin would be more fragile
than valuable. This is the one piece of the project that gets its
"real evidence" purely from being run and used, not from a test suite
- consistent with how Docker and live API calls have been treated
throughout, just with no partial automated coverage possible at all
here.

Real, separate bug found while wiring this up: adding a new top-level
`ui/` folder made setuptools' automatic package discovery ambiguous
(multiple plausible top-level packages: app, tests, scripts, ui,
docs), breaking `pip install -e`. Fixed by explicitly scoping
discovery to `app*` in pyproject.toml.


## Round 15 — Chat UI: Verified Live, Closed Out

Real click-through in the browser against the running Chainlit app,
real Postgres, real Gemini embeddings, real OpenRouter generation.
Module-selection buttons rendered correctly; CO module question
("What triggers the cost estimate check?") answered correctly with
citation [CO-CE-001]; correct refusal on a context-dependent follow-up
("who is responsible for step 3?") rather than hallucinating.

Two independent browser sessions (a normal tab plus an incognito
window, to guarantee separate cookie stores rather than two tabs
sharing one Chainlit session) confirmed full isolation: Session A
stayed on CO throughout, Session B independently selected FI and its
"summarize this module" answer cited only FI documents
(FI-CB-013, FI-AP-038, FI-AA-024, FI-AP-035-1) - no cross-session
leakage of module or history in either direction. Session B was
confirmed to start fresh (module-selection prompt shown again) rather
than silently continuing an existing thread.

Two environment issues along the way, neither a code bug:
`ui/app.py` collided with the `app` package name once Chainlit
registered it in `sys.modules` under that name - renamed to
`ui/chainlit_app.py`. Separately, the dev machine's Python 3.14 +
outdated Xcode Command Line Tools combination broke `platform.mac_ver()`
and `pyexpat` system-wide; resolved by updating macOS/CLT and rebuilding
Python 3.12 from source via Homebrew, not by patching the project.

Next: Hardening (M8) - retries, edge cases, error handling.

## Round 15 — Chat UI: Verified Live, Closed Out

Real click-through in the browser against the running Chainlit app,
real Postgres, real Gemini embeddings, real OpenRouter generation.
Module-selection buttons rendered correctly; CO module question
("What triggers the cost estimate check?") answered correctly with
citation [CO-CE-001]; correct refusal on a context-dependent follow-up
("who is responsible for step 3?") rather than hallucinating.

Two independent browser sessions (a normal tab plus an incognito
window, to guarantee separate cookie stores rather than two tabs
sharing one Chainlit session) confirmed full isolation: Session A
stayed on CO throughout, Session B independently selected FI and its
"summarize this module" answer cited only FI documents
(FI-CB-013, FI-AP-038, FI-AA-024, FI-AP-035-1) - no cross-session
leakage of module or history in either direction. Session B was
confirmed to start fresh (module-selection prompt shown again) rather
than silently continuing an existing thread.

Two environment issues along the way, neither a code bug:
`ui/app.py` collided with the `app` package name once Chainlit
registered it in `sys.modules` under that name - renamed to
`ui/chainlit_app.py`. Separately, the dev machine's Python 3.14 +
outdated Xcode Command Line Tools combination broke `platform.mac_ver()`
and `pyexpat` system-wide; resolved by updating macOS/CLT and rebuilding
Python 3.12 from source via Homebrew, not by patching the project.

Next: Hardening (M8) - retries, edge cases, error handling.
