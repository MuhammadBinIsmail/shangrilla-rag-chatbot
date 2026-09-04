"""Multi-turn conversation: history-aware query reformulation +
per-session module binding, built on top of the single-turn qa module.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.database.session_store import SessionStore
from app.embeddings.gemini_client import GeminiEmbeddingClient
from app.llm.openrouter_client import OpenRouterClient
from app.retrieval.qa import RetrievedChunk, answer_query

_REFORMULATION_SYSTEM_PROMPT = """Given a conversation history and a \
follow-up question, rewrite the follow-up into a standalone question \
that makes sense without the history. If it's already standalone, \
return it unchanged. Return ONLY the rewritten question, nothing else."""


@dataclass
class ConversationTurn:
    text: str
    sources: list[RetrievedChunk]
    needs_module_selection: bool = False


def reformulate_query(llm_client: OpenRouterClient, history: list, latest_query: str) -> str:
    """Skips the LLM call entirely when there's no history yet - no
    need to pay for a reformulation call on the first turn."""
    if not history:
        return latest_query
    history_text = "\n".join(f"{m.role}: {m.content}" for m in history)
    prompt = f"Conversation history:\n{history_text}\n\nFollow-up question: {latest_query}"
    return llm_client.generate(_REFORMULATION_SYSTEM_PROMPT, prompt).strip()


def ask(
    session_store: SessionStore,
    db_session,
    embedding_client: GeminiEmbeddingClient,
    llm_client: OpenRouterClient,
    session_id: str,
    user_message: str,
    module: str | None = None,
) -> ConversationTurn:
    """One turn of a conversation. `module` is only used to set the
    session's module on first contact - once set, it's session-bound
    and further module args are ignored (a session doesn't switch
    modules mid-conversation)."""
    session_row = session_store.get_or_create_session(session_id)

    if module and not session_row.module:
        session_store.set_module(session_id, module)
        session_row.module = module

    if not session_row.module:
        return ConversationTurn(text="Please select a module first.", sources=[], needs_module_selection=True)

    history = session_store.get_history(session_id)
    query = reformulate_query(llm_client, history, user_message)

    answer = answer_query(db_session, embedding_client, llm_client, query, session_row.module)

    session_store.add_message(session_id, "user", user_message)
    session_store.add_message(session_id, "assistant", answer.text)

    return ConversationTurn(text=answer.text, sources=answer.sources)
