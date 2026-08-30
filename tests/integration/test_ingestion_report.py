from pathlib import Path

from app.ingestion.report import build_ingestion_report
from tests.fixtures import write_fsd_docx, write_tsd_pdf


def test_full_ingestion_report_end_to_end(tmp_path: Path):
    root = tmp_path / "data"

    # A valid FSD/TSD pair
    write_fsd_docx(
        root / "CO" / "CO-CE-001.docx",
        [
            "FUNCTIONAL SPECIFICATION DOCUMENT",
            "LOB: <CONTROLLING>",
            "PROCESS: < CO-CE-001 >",
            "WORKPACKAGE: < CO-CE-001 >",
            "WRICEF ID: < CO-CE-001 >",
        ],
    )
    write_tsd_pdf(
        root / "CO" / "TSD_CO-CE-001.pdf",
        title="Restriction on Process Order Release without Cost Estimate",
        table_rows=[
            ["WRICEF ID", "CO-CE-001", "Object Type", "Enhancement (BAdI)"],
            ["SAP Module", "Controlling (CO)", "BAdI Name", "WORKORDER_UPDATE"],
            ["T-Code / Method", "AT_RELEASE", "Complexity", "Medium"],
            ["Project Code", "1073", "Landscape", "S/4HANA Private Cloud (DS4)"],
        ],
    )

    # A deliberate collision: two TSDs, same WRICEF ID, different
    # filename formatting - mirrors the real MM-E-007 case
    write_tsd_pdf(
        root / "MM" / "TSD_MM_E_007_Purchasing_Group_Validation_PR.pdf",
        title="Purchasing Group Validation in PR",
        table_rows=[
            ["WRICEF ID", "MM_E_007", "Object Type", "Enhancement"],
            ["SAP Module", "Materials Mgmt (MM)", "Program", "ZPG_VALIDATE"],
            ["Complexity", "Low", "Project Code", "1073"],
            ["Landscape", "S/4HANA Private Cloud (DS4)", "", ""],
        ],
    )
    write_tsd_pdf(
        root / "MM" / "TSD_-_MM-E-007_-_Single_Purchasing_Group_Validation_PR.pdf",
        title="Single Purchasing Group Validation in PR",
        table_rows=[
            ["WRICEF ID", "MM-E-007", "Object Type", "Enhancement"],
            ["SAP Module", "Materials Mgmt (MM)", "Program", "ZPG_VALIDATE_V2"],
            ["Complexity", "Low", "Project Code", "1073"],
            ["Landscape", "S/4HANA Private Cloud (DS4)", "", ""],
        ],
    )

    # A non-FSD xlsx (mirrors Purchase_Order.xlsx)
    import openpyxl

    (root / "MM").mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["PO Number", "Vendor", "Amount"])
    ws.append(["4500001234", "Acme Supplies", "15000"])
    wb.save(str(root / "MM" / "Purchase_Order.xlsx"))

    # An unrecognized file
    (root / "MM" / "readme_notes.txt").write_text("internal notes, ignore")

    report = build_ingestion_report(root)

    assert len(report.successes) == 4  # CO FSD, CO TSD, 2x MM TSD
    assert len(report.failures) == 1  # Purchase_Order.xlsx
    assert len(report.skipped) == 1  # readme_notes.txt

    assert len(report.collisions) == 1
    collision = report.collisions[0]
    assert collision.document_id == "mm-e-007-tsd"
    assert len(collision.files) == 2

    failure_names = {f.file.path.name for f in report.failures}
    assert "Purchase_Order.xlsx" in failure_names
