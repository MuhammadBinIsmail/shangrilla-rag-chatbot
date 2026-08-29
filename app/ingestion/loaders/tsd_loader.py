"""TSD loader: PyMuPDF for page text (title extraction), pdfplumber for
first-page table extraction specifically. Plain text-stream extraction
risks scrambling a multi-column table's row/column order; pdfplumber's
extract_tables() avoids that - see architecture doc, Round 3, PDF
loader row.
"""
from __future__ import annotations

from pathlib import Path

import pdfplumber
import pymupdf

from app.config.schema_loader import load_schema, tsd_stable_field_config
from app.ingestion.loaders.common import parse_label_value_table
from app.ingestion.metadata.models import TSDMetadata

_HEADING_MARKER = "TECHNICAL SPECIFICATION"


def extract_title(first_page_text: str) -> str | None:
    """The document title sits between the 'TECHNICAL SPECIFICATION
    DOCUMENT' heading (which sometimes wraps across two lines in real
    samples) and the metadata table - identified here by the first
    line that looks like it belongs to the table."""
    lines = [l.strip() for l in first_page_text.splitlines() if l.strip()]

    heading_end = None
    for i, line in enumerate(lines):
        if _HEADING_MARKER in line.upper():
            heading_end = i
            break
    if heading_end is None:
        return None

    for line in lines[heading_end + 1 :]:
        upper = line.upper()
        if upper == "DOCUMENT":
            continue  # heading wrapped onto its own line
        if upper.startswith("WRICEF ID"):
            break
        return line
    return None


def load_tsd_metadata(path: Path, schema: dict | None = None) -> TSDMetadata | None:
    """Returns None when no WRICEF ID (or any other required stable
    field) can be found - handled by the caller as a validation
    failure, not a crash."""
    schema = schema or load_schema()
    stable_config = tsd_stable_field_config(schema)

    with pymupdf.open(str(path)) as pdf:
        first_page_text = pdf[0].get_text()
    title = extract_title(first_page_text)

    with pdfplumber.open(str(path)) as pdf:
        tables = pdf.pages[0].extract_tables()
    if not tables:
        return None

    stable, technical_details = parse_label_value_table(tables[0], stable_config)

    missing_required = [
        name
        for name, cfg in stable_config.items()
        if cfg.get("required") and not stable.get(name)
    ]
    if missing_required or not title:
        return None

    return TSDMetadata(**stable, title=title, technical_details=technical_details)
