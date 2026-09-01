"""Heading-aware chunking for FSD/TSD body content.

Heading pattern below matches the real numbering seen in FSD prose
(e.g. "1. Purpose", "3.2 Interface Screen Fields", "A. Allocation
Process" - see FSD_Interface_Asset_to_Vendor sample). Falls back to
one unsectioned block if nothing matches - not every document uses
this convention.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING_PATTERN = re.compile(r"^(?:\d+(?:\.\d+)*\.?|[A-Z]\.)\s+\S")

DEFAULT_MAX_CHARS = 1500
DEFAULT_OVERLAP_CHARS = 200


@dataclass
class Chunk:
    text: str
    section_title: str | None
    chunk_index: int


def split_into_sections(lines: list[str]) -> list[tuple[str | None, list[str]]]:
    """Group lines into (heading, content_lines). No headings found ->
    one section with heading=None holding everything."""
    sections: list[tuple[str | None, list[str]]] = []
    heading: str | None = None
    buffer: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if _HEADING_PATTERN.match(stripped):
            if buffer or heading:
                sections.append((heading, buffer))
            heading, buffer = stripped, []
        else:
            buffer.append(stripped)

    if buffer or heading:
        sections.append((heading, buffer))

    return sections or [(None, [])]


def _chunk_text(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    """Sliding window with overlap, breaking at a sentence boundary
    where possible instead of mid-word."""
    if len(text) <= max_chars:
        return [text] if text.strip() else []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            boundary = text.rfind(". ", start, end)
            if boundary > start:
                end = boundary + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = end - overlap_chars
    return chunks


def chunk_document(
    lines: list[str],
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[Chunk]:
    """Full pipeline: detect sections, then size-bound each one."""
    chunks: list[Chunk] = []
    index = 0
    for heading, section_lines in split_into_sections(lines):
        text = " ".join(section_lines)
        for piece in _chunk_text(text, max_chars, overlap_chars):
            chunks.append(Chunk(text=piece, section_title=heading, chunk_index=index))
            index += 1
    return chunks
