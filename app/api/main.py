"""FastAPI app wrapping the conversation pipeline - the piece a UI
(Chainlit) actually talks to over HTTP.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session as OrmSession

load_dotenv()  # every CLI script does this first - missed it here originally

from app.api.dependencies import get_db, get_embedder, get_llm, get_session_store  # noqa: E402
from app.api.schemas import ChatRequest, ChatResponse, MessageInfo, SourceInfo  # noqa: E402
from app.config.modules import Module  # noqa: E402
from app.database.session import get_engine, init_db  # noqa: E402
from app.database.session_store import SessionStore  # noqa: E402
from app.embeddings.gemini_client import GeminiEmbeddingClient  # noqa: E402
from app.llm.openrouter_client import OpenRouterClient  # noqa: E402
from app.retrieval.conversation import ask  # noqa: E402

_VALID_MODULES = {m.value for m in Module}


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = get_engine()
    init_db(engine)
    app.state.engine = engine
    app.state.embedder = GeminiEmbeddingClient()
    app.state.llm = OpenRouterClient()
    yield


app = FastAPI(title="Shangrilla RAG Chatbot API", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/modules")
def list_modules():
    return sorted(_VALID_MODULES)


@app.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    db: OrmSession = Depends(get_db),
    store: SessionStore = Depends(get_session_store),
    embedder: GeminiEmbeddingClient = Depends(get_embedder),
    llm: OpenRouterClient = Depends(get_llm),
):
    module = request.module.upper() if request.module else None
    if module and module not in _VALID_MODULES:
        raise HTTPException(status_code=400, detail=f"Unknown module: {module}")

    turn = ask(store, db, embedder, llm, request.session_id, request.message, module=module)

    return ChatResponse(
        text=turn.text,
        sources=[
            SourceInfo(
                wricef_id=s.wricef_id,
                doc_type=s.doc_type,
                source_filename=s.source_filename,
                section_title=s.section_title,
                distance=s.distance,
            )
            for s in turn.sources
        ],
        needs_module_selection=turn.needs_module_selection,
    )


@app.get("/sessions/{session_id}/history", response_model=list[MessageInfo])
def get_history(session_id: str, store: SessionStore = Depends(get_session_store)):
    history = store.get_history(session_id)
    return [MessageInfo(role=m.role, content=m.content) for m in history]
