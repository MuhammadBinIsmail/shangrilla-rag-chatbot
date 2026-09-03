"""Single-turn RAG: retrieve module-filtered chunks, assemble a
prompt that constrains the LLM to only that context, generate an
answer with source citations.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.embeddings.gemini_client import GeminiEmbeddingClient
from app.llm.openrouter_client import OpenRouterClient
from app.retrieval.retriever import RetrievedChunk, retrieve

_SYSTEM_PROMPT = """You are answering questions about SAP {module} module \
functional and technical specifications for Shangrila Foods.

Answer ONLY using the provided context below. If the answer isn't in \
the context, say so explicitly - do not guess or use outside knowledge.

When you use information from a chunk, cite its WRICEF ID in brackets, \
e.g. [CO-CE-001]."""


@dataclass
class Answer:
    text: str
    sources: list[RetrievedChunk]


def _build_context(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "(no relevant content found)"
    blocks = []
    for c in chunks:
        header = f"[{c.wricef_id}] {c.doc_type}"
        if c.section_title:
            header += f" - {c.section_title}"
        blocks.append(f"{header}\n{c.text}")
    return "\n\n---\n\n".join(blocks)


def answer_query(
    session: Session,
    embedding_client: GeminiEmbeddingClient,
    llm_client: OpenRouterClient,
    query: str,
    module: str,
    top_k: int = 5,
) -> Answer:
    chunks = retrieve(session, embedding_client, query, module, top_k=top_k)
    context = _build_context(chunks)
    system_prompt = _SYSTEM_PROMPT.format(module=module)
    user_prompt = f"Context:\n\n{context}\n\nQuestion: {query}"

    text = llm_client.generate(system_prompt, user_prompt)
    return Answer(text=text, sources=chunks)
