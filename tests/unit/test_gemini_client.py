from unittest.mock import MagicMock, patch

from app.embeddings.gemini_client import EMBEDDING_MODEL, GeminiEmbeddingClient


def _mock_response(vectors: list[list[float]]) -> MagicMock:
    response = MagicMock()
    response.embeddings = [MagicMock(values=v) for v in vectors]
    return response


def test_embed_documents_uses_document_task_type_and_pinned_model():
    with patch("app.embeddings.gemini_client.genai.Client") as MockClient:
        instance = MockClient.return_value
        instance.models.embed_content.return_value = _mock_response([[0.1, 0.2]])

        client = GeminiEmbeddingClient(api_key="fake")
        result = client.embed_documents(["some chunk text"])

        assert result == [[0.1, 0.2]]
        _, kwargs = instance.models.embed_content.call_args
        assert kwargs["model"] == EMBEDDING_MODEL
        assert kwargs["config"].task_type == "RETRIEVAL_DOCUMENT"


def test_embed_query_uses_query_task_type_and_returns_single_vector():
    with patch("app.embeddings.gemini_client.genai.Client") as MockClient:
        instance = MockClient.return_value
        instance.models.embed_content.return_value = _mock_response([[0.5, 0.6]])

        client = GeminiEmbeddingClient(api_key="fake")
        result = client.embed_query("a user question")

        assert result == [0.5, 0.6]  # single vector, not a list of one
        _, kwargs = instance.models.embed_content.call_args
        assert kwargs["config"].task_type == "RETRIEVAL_QUERY"


def test_embed_documents_handles_multiple_texts_in_one_call():
    with patch("app.embeddings.gemini_client.genai.Client") as MockClient:
        instance = MockClient.return_value
        instance.models.embed_content.return_value = _mock_response([[0.1], [0.2], [0.3]])

        client = GeminiEmbeddingClient(api_key="fake")
        result = client.embed_documents(["chunk one", "chunk two", "chunk three"])

        assert len(result) == 3
        _, kwargs = instance.models.embed_content.call_args
        assert kwargs["contents"] == ["chunk one", "chunk two", "chunk three"]
