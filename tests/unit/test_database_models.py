from app.database.models import Base, Chunk, Document, EMBEDDING_DIMENSIONS


def test_documents_table_has_expected_columns():
    columns = {c.name for c in Document.__table__.columns}
    assert columns == {
        "document_id", "wricef_id", "module", "doc_type", "title",
        "source_filename", "source_path", "extra_metadata", "ingested_at",
    }


def test_chunks_table_has_expected_columns():
    columns = {c.name for c in Chunk.__table__.columns}
    assert columns == {
        "chunk_id", "document_id", "chunk_index", "section_title", "text", "embedding",
    }


def test_chunk_document_id_is_a_foreign_key():
    fk_columns = {fk.column.table.name for fk in Chunk.__table__.foreign_keys}
    assert "documents" in fk_columns


def test_embedding_column_dimension_matches_constant():
    embedding_col = Chunk.__table__.columns["embedding"]
    assert embedding_col.type.dim == EMBEDDING_DIMENSIONS


def test_models_construct_without_a_live_database():
    doc = Document(
        document_id="co-ce-001-fsd",
        wricef_id="CO-CE-001",
        module="CO",
        doc_type="FSD",
        title="Sample",
        source_filename="CO-CE-001.docx",
        source_path="/data/CO/CO-CE-001.docx",
        extra_metadata={"lob": "CONTROLLING"},
    )
    chunk = Chunk(
        chunk_id="co-ce-001-fsd-0",
        document_id="co-ce-001-fsd",
        chunk_index=0,
        section_title="1. Purpose",
        text="Sample chunk text.",
        embedding=[0.1] * EMBEDDING_DIMENSIONS,
    )
    assert doc.wricef_id == "CO-CE-001"
    assert len(chunk.embedding) == EMBEDDING_DIMENSIONS


def test_all_tables_registered_on_base_metadata():
    assert set(Base.metadata.tables.keys()) == {"documents", "chunks", "sessions", "messages"}
