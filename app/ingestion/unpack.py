"""Pre-ingestion zip extraction.

A zip is not a document type - it's a container. Extracting it to a
staging folder before discovery classifies anything means the rest of
the pipeline never needs zip-aware branching; extracted contents just
re-enter normal file classification like any other file on disk.
"""
from __future__ import annotations

import zipfile
from pathlib import Path


def unpack_zip(zip_path: Path, staging_root: Path) -> Path:
    """Extract zip_path into a dedicated subfolder under staging_root,
    named after the zip file so multiple zips don't collide, and
    return that subfolder's path for the caller to walk."""
    destination = staging_root / zip_path.stem
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(destination)
    return destination
