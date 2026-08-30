"""Shared, config-driven metadata parsers for FSD/TSD loaders."""
from __future__ import annotations

import re

_LABEL_LINE_PATTERN = re.compile(r"^\s*([A-Za-z /]+?)\s*:\s*(.*)$")


def clean_value(raw: str) -> str:
    """Strip brackets/whitespace; collapse wrapped-line breaks to a space."""
    value = raw.strip().strip("<>").strip()
    return re.sub(r"\s*\n\s*", " ", value)


def parse_label_value_lines(lines: list[str], field_config: dict[str, dict]) -> dict[str, str | None]:
    """FSD-style 'LABEL: <value>' lines -> dict keyed by config field names."""
    extracted: dict[str, str | None] = {name: None for name in field_config}
    label_to_field = {
        cfg["label"].strip().lower(): name for name, cfg in field_config.items() if cfg.get("label")
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

    # short_title: unlabeled bracketed line right after WRICEF ID (not in every module)
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
    """TSD single-column layout: label line, then its value line, repeating.

    Confirmed against real corpus file TM_F_0008. Breaks if a value
    wraps across two lines (see PP-I-005 case) - caller falls back to
    parse_label_value_table when that happens.
    """
    stable: dict[str, str | None] = {name: None for name in stable_field_config}
    label_to_field = {cfg["label"].strip().lower(): name for name, cfg in stable_field_config.items()}
    technical_details: dict[str, str] = {}

    wricef_label = stable_field_config["wricef_id"]["label"].strip().lower()
    landscape_label = stable_field_config["landscape"]["label"].strip().lower()
    cleaned = [l.strip() for l in lines if l.strip()]

    start_idx = next((i for i, l in enumerate(cleaned) if l.lower() == wricef_label), None)
    if start_idx is None:
        return stable, technical_details

    end_idx = next(
        (i for i in range(start_idx, len(cleaned)) if cleaned[i].lower() == landscape_label), None
    )
    if end_idx is None or end_idx + 1 >= len(cleaned):
        return stable, technical_details

    block = cleaned[start_idx : end_idx + 2]
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
    """TSD grid layout: 2D table with label/value cell pairs per row.

    Confirmed against real corpus file PP-I-005 - used as fallback
    when the single-column parser above comes back incomplete.
    """
    stable: dict[str, str | None] = {name: None for name in stable_field_config}
    label_to_field = {cfg["label"].strip().lower(): name for name, cfg in stable_field_config.items()}
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
