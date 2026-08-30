"""Shared fixture builders for tests - keeps the docx/pdf generation
logic in one place instead of duplicated across test files."""
from __future__ import annotations

from pathlib import Path

from docx import Document as DocxDocument
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def write_fsd_docx(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = DocxDocument()
    for line in lines:
        doc.add_paragraph(line)
    doc.save(str(path))


def write_tsd_pdf(path: Path, title: str, table_rows: list[list[str]]) -> None:
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
    table = Table(table_rows)
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
    elements.append(table)
    doc.build(elements)
