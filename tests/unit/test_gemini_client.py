from unittest.mock import MagicMock, patch

from google.genai import errors

from app.embeddings.gemini_client import EMBEDDING_MODEL, GeminiEmbeddingClient


def _mock_response(vectors: list[list[float]]) -> MagicMock:
    response = MagicMock()
    response.embeddings = [MagicMock(values=v) for v in vectors]
    return response


def _rate_limit_error(retry_delay: str | None = "5s") -> errors.ClientError:
    body: dict = {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "quota"}}
    if retry_delay:
        body["error"]["details"] = [
            {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retry_delay}
        ]
    return errors.ClientError(code=429, response_json=body)


def test_embed_documents_uses_pinned_model_and_direct_api():
    with patch("app.embeddings.gemini_client.genai.Client") as MockClient:
        instance = MockClient.return_value
        instance.models.embed_content.return_value = _mock_response([[0.1, 0.2]])

        GeminiEmbeddingClient(api_key="fake").embed_documents(["text"])

        _, init_kwargs = MockClient.call_args
        assert init_kwargs["vertexai"] is False
        _, call_kwargs = instance.models.embed_content.call_args
        assert call_kwargs["model"] == EMBEDDING_MODEL


def test_embed_query_uses_query_task_type_and_single_vector():
    with patch("app.embeddings.gemini_client.genai.Client") as MockClient:
        instance = MockClient.return_value
        instance.models.embed_content.return_value = _mock_response([[0.5, 0.6]])

        result = GeminiEmbeddingClient(api_key="fake").embed_query("a question")

        assert result == [0.5, 0.6]


def test_non_rate_limit_error_is_not_retried():
    with patch("app.embeddings.gemini_client.genai.Client") as MockClient, patch(
        "app.embeddings.gemini_client.time.sleep"
    ) as mock_sleep:
        instance = MockClient.return_value
        instance.models.embed_content.side_effect = errors.ClientError(
            code=403, response_json={"error": {"code": 403, "status": "PERMISSION_DENIED"}}
        )

        try:
            GeminiEmbeddingClient(api_key="fake").embed_documents(["text"])
            assert False, "expected ClientError to propagate"
        except errors.ClientError as exc:
            assert exc.code == 403

        mock_sleep.assert_not_called()  # no retry attempted for a non-429


def test_rate_limit_waits_the_parsed_retry_delay_then_succeeds():
    with patch("app.embeddings.gemini_client.genai.Client") as MockClient, patch(
        "app.embeddings.gemini_client.time.sleep"
    ) as mock_sleep:
        instance = MockClient.return_value
        instance.models.embed_content.side_effect = [
            _rate_limit_error(retry_delay="5s"),
            _mock_response([[0.1]]),
        ]

        result = GeminiEmbeddingClient(api_key="fake").embed_documents(["text"])

        assert result == [[0.1]]
        mock_sleep.assert_called_once_with(7.0)  # parsed 5s + 2s buffer


def test_rate_limit_falls_back_to_default_backoff_when_unparseable():
    with patch("app.embeddings.gemini_client.genai.Client") as MockClient, patch(
        "app.embeddings.gemini_client.time.sleep"
    ) as mock_sleep:
        instance = MockClient.return_value
        instance.models.embed_content.side_effect = [
            _rate_limit_error(retry_delay=None),  # no retryDelay in the body
            _mock_response([[0.1]]),
        ]

        GeminiEmbeddingClient(api_key="fake").embed_documents(["text"])

        mock_sleep.assert_called_once_with(67.0)  # 65s default + 2s buffer


def test_rate_limit_raises_after_max_retries_exhausted():
    with patch("app.embeddings.gemini_client.genai.Client") as MockClient, patch(
        "app.embeddings.gemini_client.time.sleep"
    ):
        instance = MockClient.return_value
        instance.models.embed_content.side_effect = _rate_limit_error(retry_delay="1s")

        try:
            GeminiEmbeddingClient(api_key="fake").embed_documents(["text"])
            assert False, "expected ClientError after exhausting retries"
        except errors.ClientError as exc:
            assert exc.code == 429

        assert instance.models.embed_content.call_count == 4  # 1 initial + 3 retries
