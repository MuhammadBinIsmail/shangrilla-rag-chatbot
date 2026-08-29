from app.ingestion.metadata.normalize import build_document_id, normalize_wricef_id


def test_normalize_strips_angle_brackets_and_whitespace():
    assert normalize_wricef_id(" < CO-CE-001 > ") == "co-ce-001"


def test_normalize_unifies_underscore_and_hyphen_separators():
    assert normalize_wricef_id("MM_I_003") == "mm-i-003"
    assert normalize_wricef_id("MM-I-003") == "mm-i-003"


def test_document_id_combines_wricef_and_doc_type():
    assert build_document_id("CO-CE-001", "FSD") == "co-ce-001-fsd"
    assert build_document_id("CO-CE-001", "TSD") == "co-ce-001-tsd"


def test_known_collision_case_from_real_mm_corpus():
    """TSD_MM_E_007_Purchasing_Group_Validation_PR.pdf and
    TSD_-_MM-E-007_-_Single_Purchasing_Group_Validation_PR.pdf both carry
    WRICEF ID MM-E-007 (formatting aside) and near-identical titles -
    almost certainly two revisions of the same TSD. They MUST resolve to
    the same document_id so the vector store upserts instead of treating
    them as unrelated documents. Discovery is responsible for detecting
    and logging this collision, not for it happening silently.
    """
    assert build_document_id("MM_E_007", "TSD") == build_document_id(
        "MM-E-007", "TSD"
    )


def test_short_title_and_process_fields_are_optional():
    """QM's real FSD sample had PROCESS and WORKPACKAGE blank; CO and FI's
    samples had no short_title line at all. FSDMetadata must accept both
    without erroring."""
    from app.ingestion.metadata.models import FSDMetadata

    minimal = FSDMetadata(wricef_id="QM-F-02")
    assert minimal.process is None
    assert minimal.short_title is None
