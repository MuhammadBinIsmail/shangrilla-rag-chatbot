"""Generic, config-driven metadata parsers shared by FSD and TSD loaders.
 They process extracted lines or table rows, allowing the same 
 parsers to support all seven modules without module-specific branching."""
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
    """Parses FSD-style 'LABEL: <value>' lines into a dict using configured 
    field names. Missing or blank fields are set to None instead of raising an error."""
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


def parse_alternating_label_value_pairs(
    lines: list[str], stable_field_config: dict[str, dict]
) -> tuple[dict[str, str | None], dict[str, str]]:
    """Parses TSD metadata from PyMuPDF plain text, where fields appear as
    label/value pairs in order. The metadata block is located between the
    WRICEF ID and Landscape labels, avoiding unreliable table extraction."""
    stable: dict[str, str | None] = {name: None for name in stable_field_config}
    label_to_field = {
        cfg["label"].strip().lower(): name for name, cfg in stable_field_config.items()
    }
    technical_details: dict[str, str] = {}

    wricef_label = stable_field_config["wricef_id"]["label"].strip().lower()
    landscape_label = stable_field_config["landscape"]["label"].strip().lower()

    cleaned = [l.strip() for l in lines if l.strip()]

    start_idx = next(
        (i for i, l in enumerate(cleaned) if l.lower() == wricef_label), None
    )
    if start_idx is None:
        return stable, technical_details

    end_idx = next(
        (
            i
            for i in range(start_idx, len(cleaned))
            if cleaned[i].lower() == landscape_label
        ),
        None,
    )
    if end_idx is None or end_idx + 1 >= len(cleaned):
        return stable, technical_details

    block = cleaned[start_idx : end_idx + 2]  # include landscape's value line

    for i in range(0, len(block) - 1, 2):
        label, value = block[i], block[i + 1]
        field_name = label_to_field.get(label.lower())
        value_clean = clean_value(value)
        if field_name:
            stable[field_name] = value_clean or None
        elif value_clean:
            technical_details[label] = value_clean

    return stable, technical_details


def parse_label_value_table(
    rows: list[list[str | None]], stable_field_config: dict[str, dict]
) -> tuple[dict[str, str | None], dict[str, str]]:
    """Superseded by parse_alternating_label_value_pairs. Kept as a reusable
    primitive for future document types with clean 2D grid layouts, but not
    used by the TSD loader based on the real-corpus diagnostic findings."""
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
