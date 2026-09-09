#!/usr/bin/env python3
"""Full-text triage for remaining TSD/FSD failures (skips xlsx/scans)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pymupdf
from docx import Document as DocxDocument

from app.ingestion.report import build_ingestion_report

_TARGET_PREFIXES = ("TSD_", "TM_", "FSD_")  # focus on genuinely uncertain files


def full_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        doc = DocxDocument(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if suffix == ".pdf":
        with pymupdf.open(str(path)) as pdf:
            return pdf[0].get_text()
    return ""


def main() -> None:
    load_dotenv()
    root = Path(os.environ["SHANGRILLA_DATA_ROOT"]).expanduser()
    report = build_ingestion_report(root)

    for f in report.failures:
        name = f.file.path.name
        if not name.startswith(_TARGET_PREFIXES):
            continue
        print(f"===== {name} ({f.file.module.value}) =====")
        print(full_text(f.file.path))
        print()


if __name__ == "__main__":
    main()
