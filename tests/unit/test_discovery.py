import zipfile
from pathlib import Path

from app.ingestion.discovery import discover


def _touch(path: Path, content: str = "placeholder") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_discovers_known_extensions_and_assigns_module_from_folder(tmp_path: Path):
    root = tmp_path / "data"
    _touch(root / "CO" / "CO-CE-001.docx")
    _touch(root / "CO" / "TSD_CO-CE-001.pdf")
    _touch(root / "MM" / "some_report.xlsx")

    report = discover(root)

    by_name = {f.path.name: f for f in report.discovered}
    assert by_name["CO-CE-001.docx"].module.value == "CO"
    assert by_name["CO-CE-001.docx"].doc_type == "FSD"
    assert by_name["TSD_CO-CE-001.pdf"].module.value == "CO"
    assert by_name["TSD_CO-CE-001.pdf"].doc_type == "TSD"
    assert by_name["some_report.xlsx"].module.value == "MM"
    assert by_name["some_report.xlsx"].doc_type == "FSD"


def test_unrecognized_extension_is_skipped_not_failed(tmp_path: Path):
    root = tmp_path / "data"
    _touch(root / "MM" / "notes.txt")

    report = discover(root)

    assert len(report.discovered) == 0
    assert len(report.skipped) == 1
    skipped_path, reason = report.skipped[0]
    assert skipped_path.name == "notes.txt"
    assert "unrecognized extension" in reason


def test_file_outside_a_known_module_folder_is_skipped(tmp_path: Path):
    root = tmp_path / "data"
    _touch(root / "NOT_A_REAL_MODULE" / "file.docx")

    report = discover(root)

    assert len(report.discovered) == 0
    assert len(report.skipped) == 1
    _, reason = report.skipped[0]
    assert "not a known module" in reason


def test_zip_is_unpacked_and_its_contents_discovered_under_the_same_module(tmp_path: Path):
    """Mirrors the real PP corpus, which includes a zip among its FSDs.
    The zip itself is never reported as unrecognized; what's inside it
    gets classified normally, under the module the zip was found in."""
    root = tmp_path / "data"
    (root / "PP").mkdir(parents=True)

    inner_docx = tmp_path / "inner.docx"
    inner_docx.write_text("placeholder")
    zip_path = root / "PP" / "bundle.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(inner_docx, arcname="inner.docx")

    report = discover(root)

    discovered_names = {f.path.name for f in report.discovered}
    assert "inner.docx" in discovered_names
    inner = next(f for f in report.discovered if f.path.name == "inner.docx")
    assert inner.module.value == "PP"
    assert inner.doc_type == "FSD"

    # the .zip itself must not show up as an unrecognized/skipped file
    skipped_names = {p.name for p, _ in report.skipped}
    assert "bundle.zip" not in skipped_names


def test_summary_reports_counts(tmp_path: Path):
    root = tmp_path / "data"
    _touch(root / "CO" / "a.docx")
    _touch(root / "CO" / "b.unknown")

    report = discover(root)

    summary = report.summary()
    assert "Discovered 1 file(s)" in summary
    assert "Skipped 1 file(s)" in summary
