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
_MAX_CHUNKS_PER_DOCUMENT = 500  # sanity cap - real FSD/TSD content never needs this many


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
    where possible.

    Bug fixed here: an early sentence boundary close to `start` used
    to pull `end` in tight, which could make `end - overlap_chars`
    land BEFORE `start` - an infinite loop, confirmed to run away to
    unbounded memory on real content (a short sentence followed by a
    long run of text with no more periods, e.g. an identifier list).
    Two independent guards now: (1) only snap to a boundary that keeps
    at least half of max_chars, (2) `start` is hard-guaranteed to
    strictly increase every iteration no matter what.
    """
    if len(text) <= max_chars:
        return [text] if text.strip() else []

    min_chunk_chars = max_chars // 2
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            boundary = text.rfind(". ", start, end)
            if boundary - start > min_chunk_chars:
                end = boundary + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap_chars, start + 1)  # guaranteed forward progress
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
            if index > _MAX_CHUNKS_PER_DOCUMENT:
                raise ValueError(
                    f"chunk_document exceeded {_MAX_CHUNKS_PER_DOCUMENT} chunks - "
                    "almost certainly a chunking bug, not real content. Aborting "
                    "here (fast, loud failure) instead of continuing to consume "
                    "memory indefinitely."
                )
    return chunks
