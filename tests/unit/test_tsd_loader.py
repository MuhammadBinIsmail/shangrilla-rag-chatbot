from pathlib import Path

from app.config.schema_loader import load_schema, tsd_stable_field_config
from app.ingestion.loaders.common import parse_alternating_label_value_pairs, parse_label_value_table
from app.ingestion.loaders.tsd_loader import extract_title, load_tsd_metadata
from tests.fixtures import write_tsd_pdf, write_tsd_pdf_grid


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


def test_tsd_body_extraction_after_signature_block(tmp_path: Path):
    """Real evidence: TM_F_0008's page 1 ends right after the
    signature block, no separate body content - extraction should
    return that trailing content (here: nothing extra), not crash or
    re-include the metadata itself."""
    from app.ingestion.loaders.tsd_loader import extract_tsd_body_text

    path = tmp_path / "single_page.pdf"
    write_tsd_pdf(
        path,
        title="Some TSD",
        field_pairs=[
            ("WRICEF ID", "CO-CE-001"),
            ("Object Type", "Enhancement"),
            ("SAP Module", "Controlling (CO)"),
            ("Complexity", "Medium"),
            ("Project Code", "1073"),
            ("Landscape", "S/4HANA Private Cloud (DS4)"),
            ("TMC Project Manager", "Customer Project Manager"),
        ],
    )
    body = extract_tsd_body_text(path)
    # signature block line itself and everything before it excluded;
    # nothing follows it here, so body should be empty or near-empty
    assert "WRICEF ID" not in body
    assert "CO-CE-001" not in body


def test_matches_real_pp_i_005_grid_style_diagnostic():
    """Real corpus file: grid-style table, with a value wrapped
    across two lines (ZHU_PP_WORK_CENTER_MACHI / NE). Single-column
    parsing misaligns on this; table parsing handles it correctly."""
    schema = load_schema()
    stable_config = tsd_stable_field_config(schema)

    # exact pdfplumber extract_tables() output from the real file
    table_rows = [
        ["WRICEF ID", "PP-I-005", "Object Type", "Interface (Table-Control Screen)"],
        ["SAP Module", "Production Planning (PP)", "Program Name", "ZHU_PP_WORK_CENTER_MACHI\nNE"],
        ["T-Code", "ZPP_WC", "Complexity", "High"],
        ["Project Code", "1073", "Landscape", "S/4HANA Private Cloud (DS4)"],
    ]
    stable, technical_details = parse_label_value_table(table_rows, stable_config)

    assert stable["wricef_id"] == "PP-I-005"
    assert stable["complexity"] == "High"
    assert stable["landscape"] == "S/4HANA Private Cloud (DS4)"
    assert technical_details["Program Name"] == "ZHU_PP_WORK_CENTER_MACHI NE"


def test_grid_layout_falls_back_to_table_extraction(tmp_path: Path):
    """End-to-end: single-column parsing can't align this (a wrapped
    value), so load_tsd_metadata must fall back to table extraction."""
    path = tmp_path / "grid_style.pdf"
    write_tsd_pdf_grid(
        path,
        title="Work Center - Machine (Plant) Interface",
        table_rows=[
            ["WRICEF ID", "PP-I-005", "Object Type", "Interface (Table-Control Screen)"],
            ["SAP Module", "Production Planning (PP)", "Program Name", "ZHU_PP_WORK_CENTER_MACHINE"],
            ["T-Code", "ZPP_WC", "Complexity", "High"],
            ["Project Code", "1073", "Landscape", "S/4HANA Private Cloud (DS4)"],
        ],
    )
    metadata = load_tsd_metadata(path)
    assert metadata is not None
    assert metadata.wricef_id == "PP-I-005"
    assert metadata.complexity == "High"
    assert metadata.landscape == "S/4HANA Private Cloud (DS4)"


def test_real_wm_f_001_missing_landscape():
    """Real file: no Landscape row at all. Must still succeed -
    landscape is optional, everything else required is present."""
    schema = load_schema()
    stable_config = tsd_stable_field_config(schema)

    # exact pdfplumber extract_tables() output from the real file
    table_rows = [
        ["WRICEF ID", "WM_F_001", "Object Type", "Form"],
        ["SAP Module", "Warehouse Management (WM)", "Form", "ZMM_ISSUE_PICK_FORM"],
        ["Program", "ZHU_BIN_MIGO_FORM_DRIVER", "T-Code", "ZISPL_PRINT"],
        ["Project Code", "1073", "Complexity", "Medium"],
    ]
    stable, _ = parse_label_value_table(table_rows, stable_config)

    assert stable["wricef_id"] == "WM_F_001"
    assert stable["complexity"] == "Medium"
    assert stable["landscape"] is None


def test_real_tm_r_0026_landscape_before_project_code():
    """Real file: Landscape appears BEFORE Project Code, not after -
    the block-end anchor must not assume a fixed field order."""
    lines = [
        "WRICEF ID", "TM_R_0026", "Object Type", "Report (ALV Grid Output)",
        "SAP Module", "Transportation Management (TM)",
        "Program Name", "ZFH_DISPATCH_LOAD_RPT",
        "Complexity", "Medium",
        "Transaction Code", "ZTM_DLRP",
        "Landscape", "S/4HANA Private Cloud (DS4)",
        "Project Code", "1073",
        "TMC Project Manager", "Customer Project Manager",
    ]
    schema = load_schema()
    stable, technical_details = parse_alternating_label_value_pairs(
        lines, tsd_stable_field_config(schema)
    )
    assert stable["wricef_id"] == "TM_R_0026"
    assert stable["landscape"] == "S/4HANA Private Cloud (DS4)"
    assert stable["project_code"] == "1073"
    assert "TMC Project Manager" not in technical_details


def test_real_tm_i_0027_missing_project_code():
    """Real file: no Project Code field at all - must still succeed."""
    lines = [
        "WRICEF ID", "TM-I-0027", "Object Type", "Interface (Automated Email)",
        "SAP Module", "Transportation (TM)",
        "Complexity", "Medium",
        "Landscape", "S/4HANA Private Cloud",
        "TMC Project Manager", "Customer PM",
    ]
    schema = load_schema()
    stable, _ = parse_alternating_label_value_pairs(lines, tsd_stable_field_config(schema))
    assert stable["wricef_id"] == "TM-I-0027"
    assert stable["landscape"] == "S/4HANA Private Cloud"
    assert stable["project_code"] is None


def test_real_tm_i_0014_wrapped_sap_module_value():
    """Real file: SAP Module's value wraps across two lines
    ('Transportation Management' / '(TM) - with SD touchpoints').
    Must merge back into one value, not misread as a new label."""
    lines = [
        "WRICEF ID", "TM_I_0014", "Object Type", "Interface (Module Pool + Report)",
        "SAP Module", "Transportation Management", "(TM) - with SD touchpoints",
        "Program Name", "ZROUTE_INPUT2",
        "Complexity", "Medium",
        "Landscape", "S/4HANA Private Cloud (DS4)",
        "Project Code", "1073",
        "TMC Project Manager",
    ]
    schema = load_schema()
    stable, technical_details = parse_alternating_label_value_pairs(
        lines, tsd_stable_field_config(schema)
    )
    assert stable["sap_module"] == "Transportation Management (TM) - with SD touchpoints"
    assert stable["complexity"] == "Medium"
    assert stable["project_code"] == "1073"
    assert technical_details["Program Name"] == "ZROUTE_INPUT2"


def test_real_tm_f_0024_wrapped_compound_label():
    """Real file: label wraps after a trailing slash
    ('Adobe Form /' / 'Transaction Code'). Must merge into one
    compound label, not misread as two separate label lines."""
    lines = [
        "WRICEF ID", "TM_F_0024", "Object Type", "Report (Adobe Form Output)",
        "SAP Module", "Transportation Management (TM)",
        "Program Name", "ZTM_TRANSP_EXP_ADDA_0024",
        "Adobe Form /", "Transaction Code", "ZTM_EXP_ADDA_FORM",
        "Complexity", "Medium",
        "Project Code", "1073",
        "Landscape", "S/4HANA Private Cloud (DS4)",
        "TMC Project Manager",
    ]
    schema = load_schema()
    stable, technical_details = parse_alternating_label_value_pairs(
        lines, tsd_stable_field_config(schema)
    )
    assert stable["wricef_id"] == "TM_F_0024"
    assert stable["complexity"] == "Medium"
    assert stable["project_code"] == "1073"
    assert stable["landscape"] == "S/4HANA Private Cloud (DS4)"
    assert technical_details["Adobe Form / Transaction Code"] == "ZTM_EXP_ADDA_FORM"
