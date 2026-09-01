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
    def __init__(self):
        self.documents: dict[str, Document] = {}
        self.chunks: dict[str, list[Chunk]] = {}
        self.committed = False

    def upsert_document(self, doc: Document) -> None:
        self.documents[doc.document_id] = doc

    def replace_chunks(self, document_id: str, chunks: list[Chunk]) -> None:
        self.chunks[document_id] = chunks

    def commit(self) -> None:
        self.committed = True


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

    run_indexing(root, store, embedder)
    first_count = len(store.chunks["co-ce-001-fsd"])
    run_indexing(root, store, embedder)
    second_count = len(store.chunks["co-ce-001-fsd"])

    assert first_count == second_count == 1  # replaced, not appended


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
