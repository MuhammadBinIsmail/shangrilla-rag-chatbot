"""Loads and provides typed access to app/config/metadata_schema.yaml.

Keeping this as a thin loader (rather than hardcoding the schema in
Python) is the whole point of the config-driven design: adding an
eighth module, or a new stable TSD field, is a YAML edit here, not a
code change in the loaders.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_SCHEMA_PATH = Path(__file__).parent / "metadata_schema.yaml"


def load_schema(path: Path | None = None) -> dict[str, Any]:
    """Load the metadata schema YAML into a plain dict."""
    schema_path = path or _SCHEMA_PATH
    with schema_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def fsd_field_config(schema: dict[str, Any]) -> dict[str, Any]:
    return schema["doc_types"]["FSD"]["fields"]


def tsd_stable_field_config(schema: dict[str, Any]) -> dict[str, Any]:
    return schema["doc_types"]["TSD"]["stable_fields"]


def file_type_routing(schema: dict[str, Any]) -> dict[str, str]:
    return schema["file_types"]
