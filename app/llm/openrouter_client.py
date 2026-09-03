"""OpenRouter LLM client for generation.

Generation (unlike embeddings) tolerates provider abstraction fine -
any coherent answer from the retrieved context works regardless of
which underlying model produced it, so OpenRouter's model flexibility
is a real advantage here, not a consistency risk. See architecture
doc for the reasoning behind this split (Gemini direct for
embeddings, OpenRouter for generation).

max_tokens is explicit, not left to the model's default - an unset
value defaults to the model's max output (65535 for gemini-2.5-flash),
and OpenRouter checks whether your credit balance covers that WORST
CASE before generating anything, causing a 402 even on a normal-sized
request. A RAG answer needs nowhere near that many tokens.
"""
from __future__ import annotations

import os

from openai import OpenAI

DEFAULT_MODEL = "google/gemini-2.5-flash"
DEFAULT_MAX_TOKENS = 1024
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ):
        self._client = OpenAI(
            base_url=_OPENROUTER_BASE_URL,
            api_key=api_key or os.environ["OPENROUTER_API_KEY"],
        )
        self._model = model
        self._max_tokens = max_tokens

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content
