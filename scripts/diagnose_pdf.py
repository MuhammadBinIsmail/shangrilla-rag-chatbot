#!/usr/bin/env python3
"""One-off diagnostic: inspect exactly what pdfplumber and PyMuPDF see
in a specific PDF's first page, to figure out why table extraction is
failing on real files that pass every synthetic test.

Usage:
    python3 scripts/diagnose_pdf.py "/path/to/the/failing/file.pdf"
"""
from __future__ import annotations

import sys
from pathlib import Path

import pdfplumber
import pymupdf


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/diagnose_pdf.py <path-to-pdf>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"Not a file: {path}")
        sys.exit(1)

    print(f"=== Inspecting {path.name} ===\n")

    print("--- PyMuPDF get_text() (first 1000 chars) ---")
    with pymupdf.open(str(path)) as pdf:
        text = pdf[0].get_text()
    print(text[:1000])
    print()

    with pdfplumber.open(str(path)) as pdf:
        page = pdf.pages[0]

        print(f"--- Page size: {page.width} x {page.height} ---\n")

        print(f"--- Vector lines on page: {len(page.lines)} ---")
        print(f"--- Vector rects on page: {len(page.rects)} ---\n")

        print("--- extract_tables() with DEFAULT settings ---")
        default_tables = page.extract_tables()
        print(f"Found {len(default_tables)} table(s)")
        for t in default_tables:
            print(t)
        print()

        print("--- extract_tables() with 'text' strategy (no lines needed) ---")
        text_strategy_tables = page.extract_tables(
            {
                "vertical_strategy": "text",
                "horizontal_strategy": "text",
            }
        )
        print(f"Found {len(text_strategy_tables)} table(s)")
        for t in text_strategy_tables:
            print(t)


if __name__ == "__main__":
    main()
