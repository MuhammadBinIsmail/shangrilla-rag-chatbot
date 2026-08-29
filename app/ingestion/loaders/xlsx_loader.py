"""Excel FSD loader - unverified real structure, so this is
deliberately tolerant. Some xlsx files in the real corpus
(Purchase_Order.xlsx, "Logic - FSD - QM.xlsx", the GATE PASS WRICEF
workbooks) read like working/reference files rather than the standard
FSD template; this loader is expected to return None for those, which
the caller records as a validation failure - not a bug to chase down.

Default assumption: metadata lives in the first sheet, first ~15 rows,
as label/value pairs in adjacent cells (mirroring the docx layout).
Revisit this once a real xlsx sample with actual metadata is on hand.
"""
from __future__ import annotations

from pathlib import Path

import openpyxl

from app.config.schema_loader import fsd_field_config, load_schema
from app.ingestion.loaders.common import clean_value
from app.ingestion.metadata.models import FSDMetadata

_MAX_SCAN_ROWS = 15


def load_fsd_metadata_xlsx(path: Path, schema: dict | None = None) -> FSDMetadata | None:
    schema = schema or load_schema()
    field_config = fsd_field_config(schema)
    label_to_field = {
        cfg["label"].strip().lower(): name
        for name, cfg in field_config.items()
        if cfg.get("label")
    }

    workbook = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    try:
        sheet = workbook.worksheets[0]
        extracted: dict[str, str | None] = {name: None for name in field_config}

        for row in sheet.iter_rows(min_row=1, max_row=_MAX_SCAN_ROWS):
            for i, cell in enumerate(row):
                if cell.value is None:
                    continue
                label = str(cell.value).strip().lower().rstrip(":")
                field_name = label_to_field.get(label)
                if not field_name:
                    continue
                # value is whichever of (same row, next cell) is populated
                value = row[i + 1].value if i + 1 < len(row) else None
                extracted[field_name] = clean_value(str(value)) if value is not None else None
    finally:
        workbook.close()

    missing_required = [
        name
        for name, cfg in field_config.items()
        if cfg.get("required") and not extracted.get(name)
    ]
    if missing_required:
        return None

    return FSDMetadata(**extracted)
