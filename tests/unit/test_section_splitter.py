from app.ingestion.chunking.section_splitter import chunk_document, split_into_sections

# Real content from FSD_Interface_Asset_to_Vendor_with_VendorName.docx
_REAL_FSD_BODY = [
    "1. Purpose",
    "The purpose of this enhancement is to develop a custom interface that "
    "allows users to allocate and unallocate assets to vendors within SAP.",
    "2. Business Requirement",
    "Currently, there is no dedicated functionality to track and manage "
    "the relationship between an asset and a vendor.",
    "3. Functional Requirement",
    "The new Z-interface screen will allow users to input selection criteria.",
    "3.2 Interface Screen Fields",
    "3.3 Interface Behavior",
    "A. Allocation Process",
    "When user selects 'Allocation': validate that the asset exists.",
    "B. Unallocation Process",
    "When user selects 'Unallocation': validate that the asset is allocated.",
]


def test_splits_on_real_numbered_and_lettered_headings():
    sections = split_into_sections(_REAL_FSD_BODY)
    headings = [h for h, _ in sections]
    assert "1. Purpose" in headings
    assert "2. Business Requirement" in headings
    assert "3.2 Interface Screen Fields" in headings
    assert "A. Allocation Process" in headings
    assert "B. Unallocation Process" in headings


def test_section_content_grouped_under_correct_heading():
    sections = split_into_sections(_REAL_FSD_BODY)
    by_heading = dict(sections)
    assert "purpose of this enhancement" in by_heading["1. Purpose"][0]


def test_no_headings_falls_back_to_one_section():
    sections = split_into_sections(["Just some plain prose.", "More prose."])
    assert len(sections) == 1
    assert sections[0][0] is None


def test_empty_input_returns_empty_section():
    assert split_into_sections([]) == [(None, [])]


def test_long_section_gets_split_with_overlap():
    long_text = "Sentence one. " * 200  # well over any reasonable max_chars
    chunks = chunk_document(["1. Long Section", long_text], max_chars=500, overlap_chars=50)
    assert len(chunks) > 1
    assert all(c.section_title == "1. Long Section" for c in chunks)
    assert all(len(c.text) <= 500 + 1 for c in chunks)  # +1 tolerance for boundary rounding


def test_chunk_index_is_sequential_across_sections():
    chunks = chunk_document(_REAL_FSD_BODY, max_chars=1500)
    indices = [c.chunk_index for c in chunks]
    assert indices == list(range(len(chunks)))


def test_short_document_produces_one_chunk_per_section():
    chunks = chunk_document(_REAL_FSD_BODY, max_chars=5000)
    # 5 headings in the sample -> 5 chunks, each well under max_chars
    assert len(chunks) == 5
