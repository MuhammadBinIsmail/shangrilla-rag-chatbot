"""Pydantic models for extracted FSD/TSD metadata.

Deliberately permissive: only wricef_id-family fields are required on
FSDMetadata, because real samples (architecture doc, Rounds 3-4) show
PROCESS/WORKPACKAGE can be blank and don't track WRICEF ID reliably.
TSDMetadata's stable_fields are required because all seven modules'
samples had them; technical_details is a free-form dict because its
keys vary by Object Type, not by module.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class FSDMetadata(BaseModel):
    wricef_id: str
    lob: str | None = None
    process: str | None = None
    workpackage: str | None = None
    short_title: str | None = None


class TSDMetadata(BaseModel):
    wricef_id: str
    object_type: str
    sap_module: str
    complexity: str
    project_code: str | None = None
    landscape: str | None = None
    title: str
    technical_details: dict[str, str] = Field(default_factory=dict)


class DocumentMetadata(BaseModel):
    """Common envelope attached to every ingested document, regardless
    of underlying type (FSD/TSD, docx/pdf/xlsx)."""

    document_id: str  # {wricef_id}-{doc_type}, normalized
    wricef_id: str
    module: str  # from folder path - authoritative, never parsed text
    doc_type: str  # "FSD" | "TSD"
    source_filename: str
    source_path: str
    fsd: FSDMetadata | None = None
    tsd: TSDMetadata | None = None
