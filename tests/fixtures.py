"""Shared fixture builders for tests - keeps the docx/pdf generation
logic in one place instead of duplicated across test files."""
from __future__ import annotations

from pathlib import Path

from docx import Document as DocxDocument
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def write_fsd_docx(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = DocxDocument()
    for line in lines:
        doc.add_paragraph(line)
    doc.save(str(path))


def write_tsd_pdf(path: Path, title: str, field_pairs: list[tuple[str, str]]) -> None:
    """Builds a TSD-style PDF matching the layout confirmed against a
    real corpus file: single-column, label line then its value line,
    repeating - not a 2D grid."""
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(path), pagesize=letter)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph("SHANGRILA FOODS (PRIVATE) LIMITED", styles["Normal"]),
        Paragraph("The Food Experts!", styles["Normal"]),
        Paragraph("TECHNICAL SPECIFICATION DOCUMENT", styles["Normal"]),
        Spacer(1, 12),
        Paragraph(title, styles["Normal"]),
        Spacer(1, 12),
    ]
    for label, value in field_pairs:
        elements.append(Paragraph(label, styles["Normal"]))
        elements.append(Paragraph(value, styles["Normal"]))
    doc.build(elements)
