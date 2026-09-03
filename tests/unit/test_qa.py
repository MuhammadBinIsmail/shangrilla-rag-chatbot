from unittest.mock import MagicMock, patch

from app.retrieval.qa import _build_context, answer_query
from app.retrieval.retriever import RetrievedChunk


def _sample_chunk(module="CO", wricef_id="CO-CE-001", section_title="1. Purpose"):
    return RetrievedChunk(
        text="Some requirement text.",
        section_title=section_title,
        document_id=f"{wricef_id.lower()}-fsd",
        wricef_id=wricef_id,
        module=module,
        doc_type="FSD",
        title="Sample title",
        source_filename=f"{wricef_id}.docx",
        distance=0.1,
    )


def test_build_context_includes_wricef_id_and_section():
    context = _build_context([_sample_chunk()])
    assert "[CO-CE-001]" in context
    assert "1. Purpose" in context
    assert "Some requirement text." in context


def test_build_context_empty_chunks_says_so_explicitly():
    context = _build_context([])
    assert "no relevant content" in context.lower()


def test_build_context_separates_multiple_chunks():
    chunks = [_sample_chunk(wricef_id="CO-CE-001"), _sample_chunk(wricef_id="CO-CE-002")]
    context = _build_context(chunks)
    assert "[CO-CE-001]" in context
    assert "[CO-CE-002]" in context
    assert "---" in context  # separator between chunks


def test_answer_query_passes_module_filter_to_retrieval():
    with patch("app.retrieval.qa.retrieve") as mock_retrieve:
        mock_retrieve.return_value = [_sample_chunk(module="FI")]
        llm_client = MagicMock()
        llm_client.generate.return_value = "the answer"

        result = answer_query(
            session=MagicMock(),
            embedding_client=MagicMock(),
            llm_client=llm_client,
            query="what is the approval process?",
            module="FI",
        )

        args, kwargs = mock_retrieve.call_args
        assert args[3] == "FI"  # module is the 4th positional arg to retrieve()
        assert result.text == "the answer"
        assert len(result.sources) == 1


def test_answer_query_system_prompt_mentions_the_module():
    with patch("app.retrieval.qa.retrieve") as mock_retrieve:
        mock_retrieve.return_value = []
        llm_client = MagicMock()
        llm_client.generate.return_value = "answer"

        answer_query(
            session=MagicMock(),
            embedding_client=MagicMock(),
            llm_client=llm_client,
            query="a question",
            module="MM",
        )

        call_args = llm_client.generate.call_args[0]
        system_prompt = call_args[0]
        assert "MM" in system_prompt


def test_answer_query_returns_sources_for_citation_traceability():
    with patch("app.retrieval.qa.retrieve") as mock_retrieve:
        chunks = [_sample_chunk(wricef_id="TM_F_0008")]
        mock_retrieve.return_value = chunks
        llm_client = MagicMock()
        llm_client.generate.return_value = "answer citing [TM_F_0008]"

        result = answer_query(
            session=MagicMock(),
            embedding_client=MagicMock(),
            llm_client=llm_client,
            query="q",
            module="TM",
        )

        assert result.sources == chunks
        assert result.sources[0].wricef_id == "TM_F_0008"
