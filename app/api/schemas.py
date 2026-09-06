"""Request/response models for the API."""
from __future__ import annotations

from pydantic import BaseModel


class ChatRequest(BaseModel):
    session_id: str
    message: str
    module: str | None = None


class SourceInfo(BaseModel):
    wricef_id: str
    doc_type: str
    source_filename: str
    section_title: str | None
    distance: float


class ChatResponse(BaseModel):
    text: str
    sources: list[SourceInfo]
    needs_module_selection: bool


class MessageInfo(BaseModel):
    role: str
    content: str
