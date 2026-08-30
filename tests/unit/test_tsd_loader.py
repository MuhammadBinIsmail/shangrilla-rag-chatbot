from pathlib import Path

from app.config.schema_loader import load_schema, tsd_stable_field_config
from app.ingestion.loaders.common import parse_alternating_label_value_pairs
from app.ingestion.loaders.tsd_loader import extract_title, load_tsd_metadata
from tests.fixtures import write_tsd_pdf


def test_matches_real_tm_f_0008_diagnostic_output():
    """Exact line sequence from PyMuPDF's real extraction of
    TM_F_0008_Transporter_Expense_Booking_Report_TSD.pdf - the file
    that proved the original pdfplumber-table-based design wrong for
    real data. This is the strongest possible regression test: not
    synthetic, the actual evidence."""
    lines = [
        "SHANGRILA FOODS (PRIVATE) LIMITED",
        "The Food Experts!",
        "TECHNICAL SPECIFICATION",
        "DOCUMENT",
        "TM - Transporter Expense Booking Report (Freight Expense Booking)",
        "WRICEF ID",
        "TM_F_0008",
        "Object Type",
        "Report (Adobe Form Output)",
        "SAP Module",
        "Transportation Management (TM)",
        "Program Name",
        "ZDRPG_TM_0008",
        "Transaction Code",
        "ZTM_TRANSPORT_EXP",
        "Adobe Form",
        "ZAF_TM_0008",
        "Complexity",
        "Medium",
        "Project Code",
        "1073",
        "Landscape",
        "S/4HANA Private Cloud (DS4)",
        "TMC Project Manager",
        "Customer Project Manager",
    ]
    schema = load_schema()
    stable_config = tsd_stable_field_config(schema)

    title = extract_title(lines)
    stable, technical_details = parse_alternating_label_value_pairs(lines, stable_config)

    assert title == "TM - Transporter Expense Booking Report (Freight Expense Booking)"
    assert stable["wricef_id"] == "TM_F_0008"
    assert stable["object_type"] == "Report (Adobe Form Output)"
    assert stable["sap_module"] == "Transportation Management (TM)"
    assert stable["complexity"] == "Medium"
    assert stable["project_code"] == "1073"
    assert stable["landscape"] == "S/4HANA Private Cloud (DS4)"
    assert technical_details == {
        "Program Name": "ZDRPG_TM_0008",
        "Transaction Code": "ZTM_TRANSPORT_EXP",
        "Adobe Form": "ZAF_TM_0008",
    }
    # signature block after Landscape must not leak into technical_details
    assert "TMC Project Manager" not in technical_details


def test_tsd_co_style_badi_labels_via_pdf(tmp_path: Path):
    """Full PDF round-trip: CO's field pattern (BAdI Name / T-Code)."""
    path = tmp_path / "co_style.pdf"
    write_tsd_pdf(
        path,
        title="Restriction on Process Order Release without Cost Estimate",
        field_pairs=[
            ("WRICEF ID", "CO-CE-001"),
            ("Object Type", "Enhancement (BAdI)"),
            ("SAP Module", "Controlling (CO)"),
            ("BAdI Name", "WORKORDER_UPDATE"),
            ("T-Code / Method", "AT_RELEASE"),
            ("Complexity", "Medium"),
            ("Project Code", "1073"),
            ("Landscape", "S/4HANA Private Cloud (DS4)"),
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


def test_tsd_fi_style_different_variable_labels_via_pdf(tmp_path: Path):
    """FI's field pattern (Program / Custom Table) - proves the same
    parser handles a different Object Type's labels with no
    per-module branching."""
    path = tmp_path / "fi_style.pdf"
    write_tsd_pdf(
        path,
        title="Asset Allocation / Unallocation to Vendor",
        field_pairs=[
            ("WRICEF ID", "FI-AA-024"),
            ("Object Type", "Interface / Report"),
            ("SAP Module", "FI - Asset Accounting (AA)"),
            ("Program", "ZASSET_VENDOR_INT"),
            ("Custom Table", "ZALLOCATIONNN"),
            ("Complexity", "Medium"),
            ("Project Code", "1073"),
            ("Landscape", "S/4HANA Private Cloud (DS4)"),
        ],
    )
    metadata = load_tsd_metadata(path)
    assert metadata is not None
    assert metadata.wricef_id == "FI-AA-024"
    assert metadata.technical_details == {
        "Program": "ZASSET_VENDOR_INT",
        "Custom Table": "ZALLOCATIONNN",
    }


def test_tsd_missing_wricef_id_returns_none(tmp_path: Path):
    """A PDF with no WRICEF ID anywhere is a validation failure, not
    a crash."""
    path = tmp_path / "no_metadata.pdf"
    write_tsd_pdf(
        path,
        title="Some unrelated document",
        field_pairs=[("Some Field", "Some Value")],
    )
    assert load_tsd_metadata(path) is None
