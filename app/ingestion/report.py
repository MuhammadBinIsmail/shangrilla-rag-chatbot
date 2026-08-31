"""End-to-end ingestion dry run: discovery + loaders + collision
resolution. Stand-in for "ingestion status in app DB" until the
database lands (Chunking & Vector Indexing milestone).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.ingestion.discovery import DiscoveredFile, discover
from app.ingestion.loaders.fsd_loader import load_fsd_metadata
from app.ingestion.loaders.tsd_loader import load_tsd_metadata
from app.ingestion.loaders.xlsx_loader import load_fsd_metadata_xlsx
from app.ingestion.metadata.normalize import build_document_id


@dataclass
class LoadSuccess:
    file: DiscoveredFile
    document_id: str
    wricef_id: str


@dataclass
class LoadFailure:
    file: DiscoveredFile
    reason: str


@dataclass
class IdCollision:
    document_id: str
    files: list[Path]


@dataclass
class Superseded:
    kept: Path
    dropped: Path
    document_id: str


def resolve_collisions(successes: list[LoadSuccess]) -> tuple[list[LoadSuccess], list[Superseded]]:
    """Deterministic tie-break for duplicate document_ids: most
    recently modified file wins. Reasonable default for genuine
    duplicates/revisions - NOT reliable when content disagrees with
    filename (see QM-F-06/QM-F-02 mismatch in architecture doc),
    which still needs manual review regardless of this outcome."""
    by_id: dict[str, list[LoadSuccess]] = {}
    for s in successes:
        by_id.setdefault(s.document_id, []).append(s)

    resolved: list[LoadSuccess] = []
    superseded: list[Superseded] = []
    for doc_id, group in by_id.items():
        if len(group) == 1:
            resolved.append(group[0])
            continue
        winner = max(group, key=lambda s: s.file.path.stat().st_mtime)
        resolved.append(winner)
        for s in group:
            if s is not winner:
                superseded.append(Superseded(kept=winner.file.path, dropped=s.file.path, document_id=doc_id))
    return resolved, superseded


@dataclass
class IngestionReport:
    successes: list[LoadSuccess] = field(default_factory=list)
    failures: list[LoadFailure] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)
    collisions: list[IdCollision] = field(default_factory=list)
    resolved: list[LoadSuccess] = field(default_factory=list)
    superseded: list[Superseded] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Discovered and attempted: {len(self.successes) + len(self.failures)}",
            f"  Succeeded: {len(self.successes)}",
            f"  Failed validation: {len(self.failures)}",
            f"Skipped (unrecognized): {len(self.skipped)}",
            f"document_id collisions: {len(self.collisions)}",
            f"Resolved for indexing: {len(self.resolved)} ({len(self.superseded)} superseded)",
        ]

        if self.successes:
            by_module: dict[str, int] = {}
            for s in self.successes:
                by_module[s.file.module.value] = by_module.get(s.file.module.value, 0) + 1
            lines.append("Succeeded by module: " + ", ".join(
                f"{m}={c}" for m, c in sorted(by_module.items())
            ))

        if self.failures:
            lines.append("Failures:")
            for f in self.failures:
                lines.append(f"  {f.file.path.name} ({f.file.module.value}): {f.reason}")

        if self.superseded:
            lines.append("Superseded (kept most recently modified file):")
            for s in self.superseded:
                lines.append(f"  {s.document_id}: kept {s.kept.name}, dropped {s.dropped.name}")

        return "\n".join(lines)


def _load_one(file: DiscoveredFile) -> "LoadSuccess | LoadFailure":
    suffix = file.path.suffix.lower()

    try:
        if file.doc_type == "FSD" and suffix == ".docx":
            metadata = load_fsd_metadata(file.path)
        elif file.doc_type == "FSD" and suffix == ".xlsx":
            metadata = load_fsd_metadata_xlsx(file.path)
        elif file.doc_type == "TSD" and suffix == ".pdf":
            metadata = load_tsd_metadata(file.path)
        else:
            return LoadFailure(file=file, reason=f"no loader for {suffix} as {file.doc_type}")
    except Exception as exc:
        # Malformed/corrupt file is a per-file validation failure,
        # not a reason to crash the whole ingestion run.
        return LoadFailure(file=file, reason=f"{type(exc).__name__}: {exc}")

    if metadata is None:
        return LoadFailure(
            file=file, reason="no WRICEF ID / required fields found - not a valid FSD/TSD"
        )

    document_id = build_document_id(metadata.wricef_id, file.doc_type)
    return LoadSuccess(file=file, document_id=document_id, wricef_id=metadata.wricef_id)


def build_ingestion_report(root: Path) -> IngestionReport:
    discovery = discover(root)
    report = IngestionReport(skipped=list(discovery.skipped))

    id_to_paths: dict[str, list[Path]] = {}
    for file in discovery.discovered:
        result = _load_one(file)
        if isinstance(result, LoadSuccess):
            report.successes.append(result)
            id_to_paths.setdefault(result.document_id, []).append(file.path)
        else:
            report.failures.append(result)

    report.collisions = [
        IdCollision(document_id=doc_id, files=paths)
        for doc_id, paths in sorted(id_to_paths.items())
        if len(paths) > 1
    ]
    report.resolved, report.superseded = resolve_collisions(report.successes)

    return report
