"""File discovery.

Walks SHANGRILLA_DATA_ROOT (one subfolder per Module), extracts any .zip
archives into a staging area first, then classifies every file by
extension using the metadata_schema.yaml file_types map. Anything that
isn't a known module folder or a known extension is reported, not
ingested, and does not stop the run - matches the architecture doc's
"log-and-skip, don't fail the batch" design.
"""
from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.config.modules import Module

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "app" / "config" / "metadata_schema.yaml"
)


@dataclass(frozen=True)
class DiscoveredFile:
    path: Path
    module: Module
    doc_type: str  # "FSD" | "TSD"


@dataclass
class DiscoveryReport:
    discovered: list[DiscoveredFile]
    skipped: list[tuple[Path, str]]  # (path, reason)

    def summary(self) -> str:
        lines = [f"Discovered {len(self.discovered)} file(s)."]
        if self.skipped:
            lines.append(f"Skipped {len(self.skipped)} file(s):")
            for path, reason in self.skipped:
                lines.append(f"  - {path.name}: {reason}")
        return "\n".join(lines)


def _load_file_type_map(schema_path: Path) -> dict[str, str]:
    with open(schema_path) as f:
        schema = yaml.safe_load(f)
    return schema["file_types"]


def _unpack_zips(root: Path, staging_root: Path) -> None:
    """Extract every .zip under root into staging_root, keeping the
    module subfolder it was found in, so extracted contents are
    classified under the correct module during the main walk."""
    staging_root.mkdir(parents=True, exist_ok=True)
    for zip_path in root.rglob("*.zip"):
        module_dir = zip_path.parent.relative_to(root)
        target = staging_root / module_dir / zip_path.stem
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(target)


def discover(root: Path | str, schema_path: Path = _SCHEMA_PATH) -> DiscoveryReport:
    """Walk `root`, unpack any zips, and classify every file found.

    `root` is expected to contain one subfolder per Module (CO/FI/MM/...).
    Files outside a known module folder, or with an unrecognized
    extension, are recorded in the report's `skipped` list rather than
    raising - a single bad file never aborts the whole run.
    """
    root = Path(root)
    file_type_map = _load_file_type_map(schema_path)
    known_modules = {m.value for m in Module}

    staging_root = root.parent / f".{root.name}-unpacked"
    if staging_root.exists():
        shutil.rmtree(staging_root)
    _unpack_zips(root, staging_root)

    discovered: list[DiscoveredFile] = []
    skipped: list[tuple[Path, str]] = []

    for scan_root in (root, staging_root):
        if not scan_root.exists():
            continue
        for path in scan_root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() == ".zip":
                continue  # already unpacked above; not reported as unknown
            if path.name.startswith("~$"):
                skipped.append((path, "Office lock file, not a real document"))
                continue

            try:
                module_name = path.relative_to(scan_root).parts[0]
            except IndexError:
                skipped.append((path, "not inside a module subfolder"))
                continue

            if module_name not in known_modules:
                skipped.append((path, f"'{module_name}' is not a known module"))
                continue

            doc_type = file_type_map.get(path.suffix.lower())
            if doc_type is None or doc_type == "UNPACK":
                skipped.append((path, f"unrecognized extension '{path.suffix}'"))
                continue

            discovered.append(
                DiscoveredFile(path=path, module=Module(module_name), doc_type=doc_type)
            )

    return DiscoveryReport(discovered=discovered, skipped=skipped)
