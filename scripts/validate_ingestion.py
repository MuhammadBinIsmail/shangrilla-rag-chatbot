#!/usr/bin/env python3
"""Run the ingestion pipeline (discovery + loaders) against the real
SHANGRILLA_DATA_ROOT and print a summary report.

Usage:
    python3 scripts/validate_ingestion.py

Reads SHANGRILLA_DATA_ROOT from .env. This is the first point where
the loaders touch real files rather than synthetic test fixtures - run
this before trusting anything built on top of ingestion.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion.report import build_ingestion_report  # noqa: E402


def main() -> None:
    load_dotenv()
    root_str = os.environ.get("SHANGRILLA_DATA_ROOT")
    if not root_str:
        print("SHANGRILLA_DATA_ROOT is not set in .env - nothing to scan.")
        sys.exit(1)

    root = Path(root_str).expanduser()
    if not root.is_dir():
        print(f"SHANGRILLA_DATA_ROOT does not point to a real directory: {root}")
        sys.exit(1)

    print(f"Scanning {root} ...\n")
    report = build_ingestion_report(root)
    print(report.summary())

    if report.collisions:
        print(
            "\nCollisions found - likely duplicate/revised documents "
            "(e.g. the same WRICEF ID with different filename formatting). "
            "Not an error, but decide which file should win before M3."
        )


if __name__ == "__main__":
    main()
