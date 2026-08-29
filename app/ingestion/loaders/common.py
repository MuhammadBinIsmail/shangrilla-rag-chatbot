"""Generic, config-driven metadata parsers shared by the FSD and TSD
loaders. These don't know anything about docx/pdf/xlsx specifically -
they operate on already-extracted lines or table rows, which is what
lets the same two functions cover all seven modules without per-module
branching.
"""
from __future__ import annotations

import re

_LABEL_LINE_PATTERN = re.compile(r"^\s*([A-Za-z /]+?)\s*:\s*(.*)$")


def clean_value(raw: str) -> str:
    """Strip angle brackets and surrounding whitespace, matching every
    real FSD sample (e.g. 'LOB: <CONTROLLING>' -> 'CONTROLLING')."""
    return raw.strip().strip("<>").strip()


def parse_label_value_lines(
    lines: list[str], field_config: dict[str, dict]
) -> dict[str, str | None]:
    """Parse FSD-style 'LABEL: <value>' lines into a dict keyed by the
    config's field names. Fields not found are set to None rather than
    raising - real samples show PROCESS/WORKPACKAGE can be blank or the
    line absent entirely (QM's sample)."""
    extracted: dict[str, str | None] = {name: None for name in field_config}
    label_to_field = {
        cfg["label"].strip().lower(): name
        for name, cfg in field_config.items()
        if cfg.get("label")
    }

    wricef_line_index: int | None = None
    for i, line in enumerate(lines):
        match = _LABEL_LINE_PATTERN.match(line)
        if not match:
            continue
        label, value = match.group(1).strip().lower(), match.group(2)
        field_name = label_to_field.get(label)
        if field_name:
            extracted[field_name] = clean_value(value) or None
            if field_name == "wricef_id":
                wricef_line_index = i

    # short_title: the unlabeled bracketed line that sometimes follows
    # WRICEF ID (present: MM/PP/QM/TM/WM samples; absent: CO/FI samples)
    if "short_title" in field_config and wricef_line_index is not None:
        for line in lines[wricef_line_index + 1 : wricef_line_index + 3]:
            stripped = line.strip()
            if stripped.startswith("<") and stripped.endswith(">"):
                extracted["short_title"] = clean_value(stripped)
                break

    return extracted


def parse_label_value_table(
    rows: list[list[str | None]], stable_field_config: dict[str, dict]
) -> tuple[dict[str, str | None], dict[str, str]]:
    """Parse TSD-style table rows (alternating label/value cells) into
    the stable named fields plus a catch-all dict for everything else.

    Real TSD tables vary in row count (4 rows in most modules, 5 in
    TM's sample) and in which labels appear beyond the stable set
    (BAdI Name, Program, T-Code, Adobe Form, Process, ...) - which is
    exactly why only the stable fields get named columns; everything
    else lands in the catch-all rather than breaking on an unexpected
    label.
    """
    stable: dict[str, str | None] = {name: None for name in stable_field_config}
    label_to_field = {
        cfg["label"].strip().lower(): name for name, cfg in stable_field_config.items()
    }
    technical_details: dict[str, str] = {}

    for row in rows:
        cells = [c.strip() if c else "" for c in row]
        for i in range(0, len(cells) - 1, 2):
            label, value = cells[i], cells[i + 1]
            if not label:
                continue
            field_name = label_to_field.get(label.strip().lower())
            value_clean = clean_value(value)
            if field_name:
                stable[field_name] = value_clean or None
            elif value_clean:
                technical_details[label.strip()] = value_clean

    return stable, technical_details
