#!/usr/bin/env python3
"""Check pdfplumber's table detection for two specific known-uncertain files."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pdfplumber
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_TARGETS = ("TM_I_0014_Route_Management_TSD.pdf", "TSD_TM-F-0030_Customer_Load_Execution_Report.pdf")


def main() -> None:
    load_dotenv()
    root = Path(os.environ["SHANGRILLA_DATA_ROOT"]).expanduser()

    for name in _TARGETS:
        matches = list(root.rglob(name))
        if not matches:
            print(f"NOT FOUND: {name}")
            continue
        path = matches[0]
        print(f"===== {name} =====")
        with pdfplumber.open(str(path)) as pdf:
            tables = pdf.pages[0].extract_tables()
        print(f"Tables found: {len(tables)}")
        for t in tables:
            print(t)
        print()


if __name__ == "__main__":
    main()
