"""OpenRouter LLM client for generation.

Generation (unlike embeddings) tolerates provider abstraction fine -
any coherent answer from the retrieved context works regardless of
which underlying model produced it, so OpenRouter's model flexibility
is a real advantage here, not a consistency risk. See architecture
doc for the reasoning behind this split (Gemini direct for
embeddings, OpenRouter for generation).
"""
from __future__ import annotations

import os

from openai import OpenAI

DEFAULT_MODEL = "google/gemini-2.5-flash"
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterClient:
    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL):
        self._client = OpenAI(
            base_url=_OPENROUTER_BASE_URL,
            api_key=api_key or os.environ["OPENROUTER_API_KEY"],
        )
        self._model = model

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content
