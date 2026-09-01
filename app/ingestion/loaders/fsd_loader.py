"""FSD loader: python-docx text extraction + the generic label/value
line parser from common.py. Reads both paragraphs and table cells,
since a real FSD could plausibly use either layout for its metadata
block - a document with nothing found in paragraphs still gets checked
against any tables before being treated as a validation failure.
"""
from __future__ import annotations

from pathlib import Path

from docx import Document as DocxDocument

from app.config.schema_loader import fsd_field_config, load_schema
from app.ingestion.loaders.common import parse_label_value_lines
from app.ingestion.metadata.models import FSDMetadata


def extract_docx_lines(path: Path) -> list[str]:
    """Flatten a docx's paragraphs and table cells into an ordered list
    of text lines, so the same line-based parser works regardless of
    whether the source document used plain paragraphs or a table for
    its metadata block."""
    doc = DocxDocument(str(path))
    lines = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            lines.extend(c for c in cells if c)
    return lines


def extract_fsd_body_lines(path: Path, field_config: dict[str, dict] | None = None) -> list[str]:
    """Everything after the metadata block (WRICEF ID line and its
    optional short_title) - the substantive requirement prose to chunk."""
    schema = field_config or fsd_field_config(load_schema())
    wricef_label = schema["wricef_id"]["label"].strip().lower()
    lines = extract_docx_lines(path)

    for i, line in enumerate(lines):
        if line.strip().lower().startswith(wricef_label):
            body_start = i + 1
            # skip an immediately-following unlabeled short_title line
            if body_start < len(lines) and lines[body_start].strip().startswith("<"):
                body_start += 1
            return lines[body_start:]
    return lines  # no metadata block found - treat everything as body


def load_fsd_metadata(path: Path, schema: dict | None = None) -> FSDMetadata | None:
    """Returns None (not an exception) when no WRICEF ID can be found -
    the expected outcome for FSD-folder files that aren't actually
    FSDs (working files, raw WRICEF intake forms), and handled by the
    caller as a validation failure, not a crash."""
    schema = schema or load_schema()
    field_config = fsd_field_config(schema)

    lines = extract_docx_lines(path)
    extracted = parse_label_value_lines(lines, field_config)

    missing_required = [
        name
        for name, cfg in field_config.items()
        if cfg.get("required") and not extracted.get(name)
    ]
    if missing_required:
        return None

    return FSDMetadata(**extracted)
