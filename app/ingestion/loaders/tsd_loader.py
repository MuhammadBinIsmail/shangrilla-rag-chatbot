"""TSD loader.

Real corpus has two layouts: single-column (TM_F_0008) and 2D grid
(PP-I-005). Try single-column first (cheap, no pdfplumber); if
required fields come back incomplete, fall back to table extraction.
"""
from __future__ import annotations

from pathlib import Path

import pdfplumber
import pymupdf

from app.config.schema_loader import load_schema, tsd_stable_field_config
from app.ingestion.loaders.common import parse_alternating_label_value_pairs, parse_label_value_table
from app.ingestion.metadata.models import TSDMetadata

_HEADING_MARKER = "TECHNICAL SPECIFICATION"


def extract_title(lines: list[str]) -> str | None:
    """Title sits between the (sometimes 2-line-wrapped) heading and the metadata block."""
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
            continue
        if upper.startswith("WRICEF ID"):
            break
        return line
    return None


def _missing_required(stable: dict, stable_config: dict) -> list[str]:
    return [name for name, cfg in stable_config.items() if cfg.get("required") and not stable.get(name)]


def _load_via_table(path: Path, stable_config: dict) -> tuple[dict, dict]:
    with pdfplumber.open(str(path)) as pdf:
        tables = pdf.pages[0].extract_tables()
    if not tables:
        return {name: None for name in stable_config}, {}
    return parse_label_value_table(tables[0], stable_config)


def load_tsd_metadata(path: Path, schema: dict | None = None) -> TSDMetadata | None:
    schema = schema or load_schema()
    stable_config = tsd_stable_field_config(schema)

    with pymupdf.open(str(path)) as pdf:
        raw_text = pdf[0].get_text()
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

    title = extract_title(lines)
    stable, technical_details = parse_alternating_label_value_pairs(lines, stable_config)

    if _missing_required(stable, stable_config):
        stable, technical_details = _load_via_table(path, stable_config)

    if _missing_required(stable, stable_config) or not title:
        return None

    return TSDMetadata(**stable, title=title, technical_details=technical_details)
