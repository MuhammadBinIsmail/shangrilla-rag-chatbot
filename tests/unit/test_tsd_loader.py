from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.ingestion.loaders.tsd_loader import load_tsd_metadata


def _write_tsd_pdf(path: Path, title: str, table_rows: list[list[str]]) -> None:
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


def test_tsd_co_style_badi_labels(tmp_path: Path):
    """CO sample: BAdI Name / T-Code / Method as the variable labels."""
    path = tmp_path / "co_style.pdf"
    _write_tsd_pdf(
        path,
        title="Restriction on Process Order Release without Cost Estimate",
        table_rows=[
            ["WRICEF ID", "CO-CE-001", "Object Type", "Enhancement (BAdI)"],
            ["SAP Module", "Controlling (CO) / PP", "BAdI Name", "WORKORDER_UPDATE"],
            ["T-Code / Method", "AT_RELEASE", "Complexity", "Medium"],
            ["Project Code", "1073", "Landscape", "S/4HANA Private Cloud (DS4)"],
        ],
    )
    metadata = load_tsd_metadata(path)
    assert metadata is not None
    assert metadata.wricef_id == "CO-CE-001"
    assert metadata.title == "Restriction on Process Order Release without Cost Estimate"
    assert metadata.technical_details == {
        "BAdI Name": "WORKORDER_UPDATE",
        "T-Code / Method": "AT_RELEASE",
    }


def test_tsd_fi_style_different_variable_labels(tmp_path: Path):
    """FI sample: Program / Custom Table instead of BAdI Name / T-Code -
    proves the same parser handles a different Object Type's labels
    without any per-module branching."""
    path = tmp_path / "fi_style.pdf"
    _write_tsd_pdf(
        path,
        title="Asset Allocation / Unallocation to Vendor",
        table_rows=[
            ["WRICEF ID", "FI-AA-024", "Object Type", "Interface / Report"],
            ["SAP Module", "FI - Asset Accounting (AA)", "Program", "ZASSET_VENDOR_INT"],
            ["Custom Table", "ZALLOCATIONNN", "Complexity", "Medium"],
            ["Project Code", "1073", "Landscape", "S/4HANA Private Cloud (DS4)"],
        ],
    )
    metadata = load_tsd_metadata(path)
    assert metadata is not None
    assert metadata.wricef_id == "FI-AA-024"
    assert metadata.technical_details == {
        "Program": "ZASSET_VENDOR_INT",
        "Custom Table": "ZALLOCATIONNN",
    }


def test_tsd_tm_style_five_row_table(tmp_path: Path):
    """TM sample: a 5th table row, with Complexity/Project Code paired
    together instead of the usual Project Code/Landscape pairing -
    all stable fields must still resolve correctly regardless of which
    row they land on."""
    path = tmp_path / "tm_style.pdf"
    _write_tsd_pdf(
        path,
        title="TM - Transporter Expense Booking Report (Freight Expense Booking)",
        table_rows=[
            ["WRICEF ID", "TM_F_0008", "Object Type", "Report (Adobe Form Output)"],
            ["SAP Module", "Transportation Management (TM)", "Program Name", "ZDRPG_TM_0008"],
            ["Transaction Code", "ZTM_TRANSPORT_EXP", "Adobe Form", "ZAF_TM_0008"],
            ["Complexity", "Medium", "Project Code", "1073"],
            ["Landscape", "S/4HANA Private Cloud (DS4)", "", ""],
        ],
    )
    metadata = load_tsd_metadata(path)
    assert metadata is not None
    assert metadata.wricef_id == "TM_F_0008"
    assert metadata.complexity == "Medium"
    assert metadata.project_code == "1073"
    assert metadata.landscape == "S/4HANA Private Cloud (DS4)"
    assert metadata.technical_details == {
        "Program Name": "ZDRPG_TM_0008",
        "Transaction Code": "ZTM_TRANSPORT_EXP",
        "Adobe Form": "ZAF_TM_0008",
    }


def test_tsd_missing_table_returns_none(tmp_path: Path):
    """A PDF with no detectable table (e.g. a scanned or malformed
    file) is a validation failure, not a crash."""
    path = tmp_path / "no_table.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=letter)
    styles = getSampleStyleSheet()
    doc.build([Paragraph("Just some unrelated text, no table here.", styles["Normal"])])
    assert load_tsd_metadata(path) is None
