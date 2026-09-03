from unittest.mock import MagicMock, patch

from app.llm.openrouter_client import DEFAULT_MODEL, OpenRouterClient


def _mock_completion(content: str) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    return response


def test_generate_uses_openrouter_base_url_and_default_model():
    with patch("app.llm.openrouter_client.OpenAI") as MockOpenAI:
        instance = MockOpenAI.return_value
        instance.chat.completions.create.return_value = _mock_completion("an answer")

        client = OpenRouterClient(api_key="fake")
        result = client.generate("system prompt", "user prompt")

        assert result == "an answer"
        _, init_kwargs = MockOpenAI.call_args
        assert init_kwargs["base_url"] == "https://openrouter.ai/api/v1"
        _, call_kwargs = instance.chat.completions.create.call_args
        assert call_kwargs["model"] == DEFAULT_MODEL


def test_generate_sends_system_and_user_messages_correctly():
    with patch("app.llm.openrouter_client.OpenAI") as MockOpenAI:
        instance = MockOpenAI.return_value
        instance.chat.completions.create.return_value = _mock_completion("answer")

        OpenRouterClient(api_key="fake").generate("system text", "user text")

        _, call_kwargs = instance.chat.completions.create.call_args
        messages = call_kwargs["messages"]
        assert messages[0] == {"role": "system", "content": "system text"}
        assert messages[1] == {"role": "user", "content": "user text"}


def test_custom_model_overrides_default():
    with patch("app.llm.openrouter_client.OpenAI") as MockOpenAI:
        instance = MockOpenAI.return_value
        instance.chat.completions.create.return_value = _mock_completion("answer")

        OpenRouterClient(api_key="fake", model="anthropic/claude-3-haiku").generate("s", "u")

        _, call_kwargs = instance.chat.completions.create.call_args
        assert call_kwargs["model"] == "anthropic/claude-3-haiku"
