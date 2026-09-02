"""Gemini embeddings client.

Pinned model (never auto-routed - embedding consistency matters more
than flexibility, see docs/architecture.md). Uses asymmetric task
types: documents and queries get embedded differently, which is
standard practice for retrieval quality with Gemini's embedding API.

vertexai=False is explicit, not a default - the SDK was observed
silently switching between the direct Gemini API and Vertex AI
(different product, different quota pool) depending on ambient
environment detection. Forcing direct API only.

Rate-limit handling: on a real 429, parses Google's suggested
retryDelay from the error body and waits that long (plus a small
buffer) before retrying, rather than a blind fixed delay - short
waits (seen: 2-5s) recover fast, and a generous fallback covers cases
where the suggestion can't be parsed.
"""
from __future__ import annotations

import os
import time

from google import genai
from google.genai import errors, types

EMBEDDING_MODEL = "gemini-embedding-001"
_MAX_RATE_LIMIT_RETRIES = 3
_DEFAULT_BACKOFF_SECONDS = 65.0  # safely past a 60s quota window if we can't parse a suggestion


def _extract_retry_delay_seconds(exc: errors.ClientError) -> float | None:
    """Best-effort parse of Google's suggested retryDelay (e.g. '30s')
    from a 429 error body. Returns None if not found - caller falls
    back to a safe default rather than failing to parse."""
    details = getattr(exc, "details", None)
    if not isinstance(details, dict):
        return None

    error_obj = details.get("error", details)
    for item in error_obj.get("details", []) or []:
        if isinstance(item, dict) and "retryDelay" in item:
            try:
                return float(str(item["retryDelay"]).rstrip("s"))
            except ValueError:
                return None
    return None


class GeminiEmbeddingClient:
    def __init__(self, api_key: str | None = None):
        self._client = genai.Client(
            api_key=api_key or os.environ["GEMINI_API_KEY"],
            vertexai=False,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, task_type="RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], task_type="RETRIEVAL_QUERY")[0]

    def _embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        attempt = 0
        while True:
            try:
                response = self._client.models.embed_content(
                    model=EMBEDDING_MODEL,
                    contents=texts,
                    config=types.EmbedContentConfig(task_type=task_type),
                )
                return [e.values for e in response.embeddings]
            except errors.ClientError as exc:
                is_rate_limit = getattr(exc, "code", None) == 429
                if not is_rate_limit or attempt >= _MAX_RATE_LIMIT_RETRIES:
                    raise
                attempt += 1
                wait_seconds = (_extract_retry_delay_seconds(exc) or _DEFAULT_BACKOFF_SECONDS) + 2
                print(
                    f"  Rate limited - waiting {wait_seconds:.0f}s before retry "
                    f"{attempt}/{_MAX_RATE_LIMIT_RETRIES}...",
                    flush=True,
                )
                time.sleep(wait_seconds)
