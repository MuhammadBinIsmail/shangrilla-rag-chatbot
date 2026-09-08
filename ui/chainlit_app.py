"""Chainlit chat UI.

Talks directly to the conversation pipeline, not through the FastAPI
layer - avoids an unnecessary network hop for a single-process
deployment; the API layer stays available for other clients.

A fresh DB session is created per incoming message, not held for the
lifetime of the Chainlit process - same isolation principle as the
API layer (architecture doc, section H), applied here because a
single Chainlit server handles multiple concurrent browser sessions.
"""
from __future__ import annotations

import uuid

import chainlit as cl
from dotenv import load_dotenv

load_dotenv()

from app.config.modules import Module  # noqa: E402
from app.database.session import get_engine, get_session, init_db  # noqa: E402
from app.database.session_store import SessionStore  # noqa: E402
from app.embeddings.gemini_client import GeminiEmbeddingClient  # noqa: E402
from app.llm.openrouter_client import OpenRouterClient  # noqa: E402
from app.retrieval.conversation import ask  # noqa: E402

_engine = get_engine()
init_db(_engine)
_embedder = GeminiEmbeddingClient()
_llm = OpenRouterClient()


@cl.on_chat_start
async def start() -> None:
    cl.user_session.set("session_id", str(uuid.uuid4()))
    cl.user_session.set("module", None)

    actions = [
        cl.Action(name="select_module", payload={"module": m.value}, label=m.value)
        for m in Module
    ]
    response = await cl.AskActionMessage(
        content="Which SAP module would you like to ask about?",
        actions=actions,
    ).send()

    if response is None:
        await cl.Message(content="No module selected - refresh to try again.").send()
        return

    module = response["payload"]["module"]
    cl.user_session.set("module", module)
    await cl.Message(content=f"Module set to **{module}**. Ask me anything.").send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    session_id = cl.user_session.get("session_id")
    module = cl.user_session.get("module")

    if not module:
        await cl.Message(content="Please select a module first - refresh to restart.").send()
        return

    db_session = get_session(_engine)
    try:
        turn = ask(
            SessionStore(db_session), db_session, _embedder, _llm, session_id, message.content, module=module
        )
    finally:
        db_session.close()

    elements = []
    seen = set()
    for source in turn.sources:
        if source.wricef_id in seen:
            continue
        seen.add(source.wricef_id)
        elements.append(
            cl.Text(
                name=source.wricef_id,
                content=(
                    f"{source.doc_type} - {source.source_filename}\n"
                    f"Section: {source.section_title or '(none)'}"
                ),
                display="side",
            )
        )

    await cl.Message(content=turn.text, elements=elements).send()
