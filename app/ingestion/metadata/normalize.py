"""WRICEF ID normalization and document_id construction.

Real TSD filenames in the MM corpus include both:
    TSD_MM_E_007_Purchasing_Group_Validation_PR.pdf
    TSD_-_MM-E-007_-_Single_Purchasing_Group_Validation_PR.pdf

Both carry WRICEF ID "MM-E-007", just formatted differently (underscore
vs. hyphen). Without normalization these would silently become two
different document_ids for what's almost certainly the same development
at two different revisions. Normalizing first makes that collision
visible (and upsert-able) instead of silent.
"""
from __future__ import annotations

import re

_SEPARATOR_PATTERN = re.compile(r"[_\s.]+")


def normalize_wricef_id(raw: str) -> str:
    """Normalize a WRICEF ID for use as a stable identifier.

    Strips angle brackets and surrounding whitespace, lowercases, and
    unifies '_' / '.' / internal whitespace separators to '-'.
    """
    value = raw.strip().strip("<>").strip()
    value = _SEPARATOR_PATTERN.sub("-", value)
    return value.lower()


def build_document_id(wricef_id: str, doc_type: str) -> str:
    """Deterministic document_id: {wricef_id}-{doc_type}, normalized.

    Re-ingesting the same file (or a same-WRICEF-ID revision under a
    differently formatted filename) produces the same id, so the vector
    store upserts rather than duplicates.
    """
    return f"{normalize_wricef_id(wricef_id)}-{doc_type.lower()}"
