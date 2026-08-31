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
    label_to_field: dict[str, str] = {}
    for name, cfg in field_config.items():
        if cfg.get("label"):
            label_to_field[cfg["label"].strip().lower()] = name
        for alias in cfg.get("aliases", []):
            label_to_field[alias.strip().lower()] = name

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


_BLOCK_TERMINATORS = ("tmc", "developed by")  # signature block always follows the metadata


def _find_block_end(cleaned: list[str], start_idx: int) -> int:
    """Field order varies (Landscape before or after Project Code, etc.)
    so anchor on the reliable signature-block marker instead of any
    one field's position."""
    for i in range(start_idx, len(cleaned)):
        if any(cleaned[i].lower().startswith(t) for t in _BLOCK_TERMINATORS):
            return i
    return min(start_idx + 40, len(cleaned))  # fallback cap if marker absent


def _merge_wrapped_continuations(cleaned: list[str]) -> list[str]:
    """Two known wrap patterns, merged back before pairing:
    - continuation starts with '(' or lowercase -> wrapped value
      (e.g. 'Transportation Management' / '(TM)...')
    - previous line ends with '/' -> wrapped compound label
      (e.g. 'Adobe Form /' / 'Transaction Code')
    Confirmed against real files TM_I_0014, TM-F-0030, TM_F_0024."""
    merged: list[str] = []
    for line in cleaned:
        if merged and merged[-1].endswith("/"):
            merged[-1] = f"{merged[-1]} {line}"
        elif merged and line and (line[0] == "(" or line[0].islower()):
            merged[-1] = f"{merged[-1]} {line}"
        else:
            merged.append(line)
    return merged


def parse_alternating_label_value_pairs(
    lines: list[str], stable_field_config: dict[str, dict]
) -> tuple[dict[str, str | None], dict[str, str]]:
    """TSD single-column layout: label line, then its value line, repeating.

    Confirmed against real corpus files. Falls back to
    parse_label_value_table when required fields still come back
    missing (e.g. a genuinely different grid-style document).
    """
    stable: dict[str, str | None] = {name: None for name in stable_field_config}
    label_to_field = {cfg["label"].strip().lower(): name for name, cfg in stable_field_config.items()}
    technical_details: dict[str, str] = {}

    wricef_label = stable_field_config["wricef_id"]["label"].strip().lower()
    cleaned = _merge_wrapped_continuations([l.strip() for l in lines if l.strip()])

    start_idx = next((i for i, l in enumerate(cleaned) if l.lower() == wricef_label), None)
    if start_idx is None:
        return stable, technical_details

    end_idx = _find_block_end(cleaned, start_idx)
    block = cleaned[start_idx:end_idx]

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
