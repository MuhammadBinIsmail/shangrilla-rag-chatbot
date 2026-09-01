"""Gemini embeddings client.

Pinned model (never auto-routed - embedding consistency matters more
than flexibility, see docs/architecture.md). Uses asymmetric task
types: documents and queries get embedded differently, which is
standard practice for retrieval quality with Gemini's embedding API.
"""
from __future__ import annotations

import os

from google import genai
from google.genai import types

EMBEDDING_MODEL = "gemini-embedding-001"


class GeminiEmbeddingClient:
    def __init__(self, api_key: str | None = None):
        self._client = genai.Client(api_key=api_key or os.environ["GEMINI_API_KEY"])

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, task_type="RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], task_type="RETRIEVAL_QUERY")[0]

    def _embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        response = self._client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(task_type=task_type),
        )
        return [e.values for e in response.embeddings]
