from pathlib import Path

from docx import Document as DocxDocument

from app.ingestion.loaders.fsd_loader import load_fsd_metadata


def _write_docx(path: Path, lines: list[str]) -> None:
    doc = DocxDocument()
    for line in lines:
        doc.add_paragraph(line)
    doc.save(str(path))


def test_fsd_without_short_title(tmp_path: Path):
    """Mirrors the CO/FI samples: four labeled lines, no trailing
    unlabeled bracket line."""
    path = tmp_path / "co_style.docx"
    _write_docx(
        path,
        [
            "FUNCTIONAL SPECIFICATION DOCUMENT",
            "LOB: <CONTROLLING>",
            "PROCESS: < CO-CE-001 >",
            "WORKPACKAGE: < CO-CE-001 >",
            "WRICEF ID: < CO-CE-001 >",
        ],
    )
    metadata = load_fsd_metadata(path)
    assert metadata is not None
    assert metadata.wricef_id == "CO-CE-001"
    assert metadata.lob == "CONTROLLING"
    assert metadata.short_title is None


def test_fsd_with_short_title_and_blank_fields(tmp_path: Path):
    """Mirrors the QM sample: PROCESS/WORKPACKAGE blank, plus a
    trailing unlabeled bracket line (short_title)."""
    path = tmp_path / "qm_style.docx"
    _write_docx(
        path,
        [
            "FUNCTIONAL SPECIFICATION DOCUMENT",
            "LOB: <QUALITY MANAGEMENT>",
            "PROCESS: <>",
            "WORKPACKAGE: <>",
            "WRICEF ID: < QM-F-02>",
            "<QM - EXPORT 2 (MEGA)>",
        ],
    )
    metadata = load_fsd_metadata(path)
    assert metadata is not None
    assert metadata.wricef_id == "QM-F-02"
    assert metadata.process is None
    assert metadata.workpackage is None
    assert metadata.short_title == "QM - EXPORT 2 (MEGA)"


def test_fsd_where_process_and_workpackage_diverge_from_wricef_id(tmp_path: Path):
    """Mirrors the PP sample: PROCESS == WORKPACKAGE, but WRICEF ID is
    a genuinely different value - must not be assumed equal."""
    path = tmp_path / "pp_style.docx"
    _write_docx(
        path,
        [
            "FUNCTIONAL SPECIFICATION DOCUMENT",
            "LOB: < PRODUCTION EXECUTION >",
            "PROCESS: < PPE-PP.06 >",
            "WORKPACKAGE: < PPE-PP.06 >",
            "WRICEF ID: < PP_F_002 >",
        ],
    )
    metadata = load_fsd_metadata(path)
    assert metadata is not None
    assert metadata.wricef_id == "PP_F_002"
    assert metadata.process == "PPE-PP.06"
    assert metadata.workpackage == "PPE-PP.06"
    assert metadata.process == metadata.workpackage != metadata.wricef_id


def test_fsd_missing_wricef_id_returns_none(tmp_path: Path):
    """A file that doesn't actually carry a WRICEF ID (e.g. a
    misfiled working document) is a validation failure, not a crash."""
    path = tmp_path / "not_really_an_fsd.docx"
    _write_docx(path, ["Just some notes.", "No metadata block here."])
    assert load_fsd_metadata(path) is None
