"""TSD loader: uses PyMuPDF plain text to extract the title and metadata.
Real-corpus testing showed this is more reliable than pdfplumber table 
extraction, which was splitting label/value pairs incorrectly."""
from __future__ import annotations

from pathlib import Path

import pymupdf

from app.config.schema_loader import load_schema, tsd_stable_field_config
from app.ingestion.loaders.common import parse_alternating_label_value_pairs
from app.ingestion.metadata.models import TSDMetadata

_HEADING_MARKER = "TECHNICAL SPECIFICATION"


def extract_title(lines: list[str]) -> str | None:
    """Extracts the document title between the 'TECHNICAL SPECIFICATION DOCUMENT' 
    heading and the metadata block. Expects pre-cleaned lines with blanks removed."""
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
        raw_text = pdf[0].get_text()
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

    title = extract_title(lines)
    stable, technical_details = parse_alternating_label_value_pairs(lines, stable_config)

    missing_required = [
        name
        for name, cfg in stable_config.items()
        if cfg.get("required") and not stable.get(name)
    ]
    if missing_required or not title:
        return None

    return TSDMetadata(**stable, title=title, technical_details=technical_details)
