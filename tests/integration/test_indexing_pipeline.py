from pathlib import Path

from app.database.models import Chunk, Document
from app.indexing.pipeline import run_indexing
from tests.fixtures import write_fsd_docx, write_tsd_pdf


class FakeEmbeddingClient:
    """Deterministic fake - one call per document's chunk batch, records
    what was sent so tests can assert on it without a live API."""

    def __init__(self):
        self.calls: list[list[str]] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[float(len(t))] for t in texts]  # cheap deterministic "vector"


class FakeStore:
    """Models real transactional behavior: changes aren't visible via
    document_exists() until commit(); rollback() discards them. This
    matters - it's exactly what test_failed_document_is_retried_not_
    skipped_on_next_run below depends on being correct."""

    def __init__(self):
        self.documents: dict[str, Document] = {}
        self.chunks: dict[str, list[Chunk]] = {}
        self.committed = False
        self.rolled_back = False
        self._staged_documents: dict[str, Document] = {}
        self._staged_chunks: dict[str, list[Chunk]] = {}

    def document_exists(self, document_id: str) -> bool:
        return document_id in self.documents

    def upsert_document(self, doc: Document) -> None:
        self._staged_documents[doc.document_id] = doc

    def replace_chunks(self, document_id: str, chunks: list[Chunk]) -> None:
        self._staged_chunks[document_id] = chunks

    def commit(self) -> None:
        self.documents.update(self._staged_documents)
        self.chunks.update(self._staged_chunks)
        self._staged_documents.clear()
        self._staged_chunks.clear()
        self.committed = True

    def rollback(self) -> None:
        self._staged_documents.clear()
        self._staged_chunks.clear()
        self.rolled_back = True


def test_indexes_fsd_with_body_and_chunks(tmp_path: Path):
    root = tmp_path / "data"
    write_fsd_docx(
        root / "CO" / "CO-CE-001.docx",
        [
            "FUNCTIONAL SPECIFICATION DOCUMENT",
            "LOB: <CONTROLLING>",
            "WRICEF ID: < CO-CE-001 >",
            "1. Purpose",
            "This is the real requirement text for the enhancement.",
            "2. Scope",
            "This covers the second section of real content.",
        ],
    )

    store = FakeStore()
    embedder = FakeEmbeddingClient()
    stats = run_indexing(root, store, embedder)

    assert stats["documents_indexed"] == 1
    assert stats["documents_failed"] == 0
    assert stats["chunks_indexed"] == 2  # one chunk per section

    doc = store.documents["co-ce-001-fsd"]
    assert doc.wricef_id == "CO-CE-001"
    assert doc.module == "CO"
    assert doc.doc_type == "FSD"

    chunks = store.chunks["co-ce-001-fsd"]
    assert len(chunks) == 2
    assert chunks[0].section_title == "1. Purpose"
    assert "requirement text" in chunks[0].text

    # embedding client was actually called with the chunk text
    assert len(embedder.calls) == 1
    assert len(embedder.calls[0]) == 2


def test_indexes_tsd_and_embeds_body_if_present(tmp_path: Path):
    root = tmp_path / "data"
    write_tsd_pdf(
        root / "CO" / "TSD_CO-CE-001.pdf",
        title="Sample TSD",
        field_pairs=[
            ("WRICEF ID", "CO-CE-001"),
            ("Object Type", "Enhancement"),
            ("SAP Module", "Controlling (CO)"),
            ("Complexity", "Medium"),
            ("Project Code", "1073"),
            ("Landscape", "S/4HANA Private Cloud (DS4)"),
        ],
    )

    store = FakeStore()
    embedder = FakeEmbeddingClient()
    stats = run_indexing(root, store, embedder)

    assert stats["documents_indexed"] == 1
    doc = store.documents["co-ce-001-tsd"]
    assert doc.doc_type == "TSD"
    assert doc.title == "Sample TSD"
    # real TSDs in this corpus have little/no body beyond metadata -
    # zero chunks here is expected, not a failure
    assert stats["chunks_indexed"] == 0


def test_reindexing_replaces_chunks_not_duplicates(tmp_path: Path):
    root = tmp_path / "data"
    write_fsd_docx(
        root / "CO" / "CO-CE-001.docx",
        ["FUNCTIONAL SPECIFICATION DOCUMENT", "WRICEF ID: CO-CE-001", "1. Purpose", "Some text."],
    )
    store = FakeStore()
    embedder = FakeEmbeddingClient()

    run_indexing(root, store, embedder, skip_existing=False)
    first_count = len(store.chunks["co-ce-001-fsd"])
    run_indexing(root, store, embedder, skip_existing=False)
    second_count = len(store.chunks["co-ce-001-fsd"])

    assert first_count == second_count == 1  # replaced, not appended


def test_already_indexed_documents_are_skipped_by_default(tmp_path: Path):
    """Real scenario this fixes: a rate-limit error partway through a
    run shouldn't mean re-embedding (and re-billing quota for)
    documents that already succeeded."""
    root = tmp_path / "data"
    write_fsd_docx(
        root / "CO" / "CO-CE-001.docx",
        ["FUNCTIONAL SPECIFICATION DOCUMENT", "WRICEF ID: CO-CE-001", "1. Purpose", "Some text."],
    )
    store = FakeStore()
    embedder = FakeEmbeddingClient()

    run_indexing(root, store, embedder)
    assert len(embedder.calls) == 1

    stats = run_indexing(root, store, embedder)  # skip_existing=True by default
    assert stats["documents_indexed"] == 0
    assert stats["documents_skipped"] == 1
    assert len(embedder.calls) == 1  # no new embedding call made


def test_failed_document_is_retried_not_skipped_on_next_run(tmp_path: Path):
    """A document that failed (e.g. rate limit) never got a Document
    row committed, so it correctly isn't skipped next time."""
    root = tmp_path / "data"
    write_fsd_docx(
        root / "CO" / "CO-CE-001.docx",
        ["FUNCTIONAL SPECIFICATION DOCUMENT", "WRICEF ID: CO-CE-001", "1. Purpose", "Some text."],
    )
    store = FakeStore()

    class FailingEmbeddingClient:
        def __init__(self):
            self.attempts = 0

        def embed_documents(self, texts):
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeError("simulated rate limit")
            return [[1.0] for _ in texts]

    embedder = FailingEmbeddingClient()

    stats = run_indexing(root, store, embedder)
    assert stats["documents_failed"] == 1
    assert store.rolled_back is True
    assert "co-ce-001-fsd" not in store.documents

    stats = run_indexing(root, store, embedder)  # retry
    assert stats["documents_indexed"] == 1
    assert "co-ce-001-fsd" in store.documents


def test_non_fsd_document_does_not_crash_the_run(tmp_path: Path):
    """A file that fails loading (here: not a real docx at all)
    should never reach run_indexing's loop - only report.resolved
    successes get indexed."""
    root = tmp_path / "data"
    (root / "CO").mkdir(parents=True)
    (root / "CO" / "not_an_fsd.docx").write_text("placeholder")

    store = FakeStore()
    embedder = FakeEmbeddingClient()
    stats = run_indexing(root, store, embedder)

    assert stats["documents_indexed"] == 0
    assert stats["documents_failed"] == 0
    assert store.documents == {}
