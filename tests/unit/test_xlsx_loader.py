from pathlib import Path

import openpyxl

from app.ingestion.loaders.xlsx_loader import load_fsd_metadata_xlsx


def test_xlsx_with_standard_metadata_layout(tmp_path: Path):
    """First sheet, label in column A, value in column B - the
    documented default assumption."""
    path = tmp_path / "standard.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["LOB:", "MATERIALS MANAGEMENT"])
    ws.append(["PROCESS:", "SOME PROCESS"])
    ws.append(["WORKPACKAGE:", "MM_X_099"])
    ws.append(["WRICEF ID:", "MM_X_099"])
    wb.save(str(path))

    metadata = load_fsd_metadata_xlsx(path)
    assert metadata is not None
    assert metadata.wricef_id == "MM_X_099"
    assert metadata.lob == "MATERIALS MANAGEMENT"


def test_xlsx_working_file_with_no_metadata_returns_none(tmp_path: Path):
    """Mirrors the real corpus: Purchase_Order.xlsx, the GATE PASS
    WRICEF workbooks, and 'Logic - FSD - QM.xlsx' are raw data/working
    files, not FSDs in the standard template. This must fail gracefully,
    not raise - it's the correct outcome, not a bug."""
    path = tmp_path / "purchase_order_style.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["PO Number", "Vendor", "Amount", "Date"])
    ws.append(["4500001234", "Acme Supplies", "15000", "2026-01-15"])
    wb.save(str(path))

    assert load_fsd_metadata_xlsx(path) is None
