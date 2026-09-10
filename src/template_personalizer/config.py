"""Configuration loader and manager for template personalization."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


class PersonalizerConfig:
    """Manages the configuration mapping tables and fields to static replacement values."""

    def __init__(self, data: Optional[Dict[str, Any]] = None, base_dir: Optional[Path] = None):
        self._raw_data: Dict[str, Any] = data or {}
        self._base_dir: Optional[Path] = base_dir
        # Normalized lookup: (table_lower, field_lower) -> str_value
        self._fields: Dict[Tuple[str, str], str] = {}
        self._tables: Dict[str, Dict[str, str]] = {}
        self._build_normalized_map()

    def get_logo_image_bytes(self) -> Optional[Tuple[bytes, str]]:
        """Look up configured logo file path (from logo.filename, logo.image_path, logo.image, logo.file).
        If the file exists, return (image_bytes, file_suffix).
        """
        for field in ("filename", "image_path", "image", "file", "path"):
            val = self.get_value("logo", field)
            if not val:
                continue
            candidates = [Path(val)]
            if self._base_dir:
                candidates.append(self._base_dir / val)
            candidates.append(Path.cwd() / val)

            for cand in candidates:
                if cand.is_file():
                    try:
                        return cand.read_bytes(), cand.suffix
                    except Exception:
                        pass
        return None

    def _build_normalized_map(self) -> None:
        self._fields.clear()
        self._tables.clear()
        for table, fields in self._raw_data.items():
            if isinstance(fields, dict):
                tbl_lower = table.strip().lower()
                if tbl_lower not in self._tables:
                    self._tables[tbl_lower] = {}
                for fld, val in fields.items():
                    fld_lower = fld.strip().lower()
                    str_val = "" if val is None else str(val)
                    self._fields[(tbl_lower, fld_lower)] = str_val
                    self._tables[tbl_lower][fld_lower] = str_val
            elif isinstance(fields, str) and "." in table:
                # Flat format support: "praxis.name": "value"
                tbl, fld = table.split(".", 1)
                tbl_lower = tbl.strip().lower()
                fld_lower = fld.strip().lower()
                str_val = "" if fields is None else str(fields)
                self._fields[(tbl_lower, fld_lower)] = str_val
                if tbl_lower not in self._tables:
                    self._tables[tbl_lower] = {}
                self._tables[tbl_lower][fld_lower] = str_val

    def has_field(self, table: str, field: str) -> bool:
        """Check if a table/field mapping exists."""
        return (table.strip().lower(), field.strip().lower()) in self._fields

    def get_value(self, table: str, field: str) -> Optional[str]:
        """Get the configured static value for a table and field, or None if not configured."""
        return self._fields.get((table.strip().lower(), field.strip().lower()))

    def get_pascal_literal(self, table: str, field: str) -> Optional[str]:
        """Get the value formatted as a PascalScript string literal (e.g. 'Hello')."""
        val = self.get_value(table, field)
        if val is None:
            return None
        return to_pascal_literal(val)

    def tables(self) -> list[str]:
        """Return list of configured table names."""
        return list(self._tables.keys())

    def fields_for_table(self, table: str) -> Dict[str, str]:
        """Return dict of fields and values for a given table."""
        return dict(self._tables.get(table.strip().lower(), {}))

    @property
    def raw_data(self) -> Dict[str, Any]:
        """Return the raw config dictionary."""
        return self._raw_data


def to_pascal_literal(value: str) -> str:
    """Format a string value as a PascalScript string literal, escaping single quotes."""
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def load_config(path_or_str: str | Path) -> PersonalizerConfig:
    """Load configuration from a YAML or JSON file."""
    path = Path(path_or_str).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    ext = path.suffix.lower()
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    if ext in (".yaml", ".yml"):
        try:
            import yaml
            data = yaml.safe_load(content) or {}
        except ImportError:
            raise ImportError(
                "PyYAML is required to load YAML config files. Install it with 'pip install pyyaml'."
            )
    elif ext == ".json":
        data = json.loads(content)
    else:
        # Try YAML first, then JSON
        try:
            import yaml
            data = yaml.safe_load(content) or {}
        except Exception:
            data = json.loads(content)

    if not isinstance(data, dict):
        raise ValueError(
            f"Invalid configuration format in {path}: expected a dictionary/mapping at top level."
        )

    return PersonalizerConfig(data, base_dir=path.parent)

