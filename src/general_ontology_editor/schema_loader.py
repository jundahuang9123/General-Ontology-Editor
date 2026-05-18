from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_schema(schema_path: str | Path) -> dict[str, Any]:
    path = Path(schema_path)
    if not path.exists():
        raise FileNotFoundError(f'Missing LinkML schema: {path}')

    schema = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    if not isinstance(schema, dict):
        raise ValueError('LinkML schema must be a mapping')

    return normalize_schema(schema)


def save_schema(schema_path: str | Path, schema: dict[str, Any] | str) -> dict[str, Any]:
    path = Path(schema_path)
    if isinstance(schema, str):
        parsed = yaml.safe_load(schema) or {}
    else:
        parsed = schema

    if not isinstance(parsed, dict):
        raise ValueError('Schema YAML must be a mapping')

    normalized = normalize_schema(parsed)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(normalized, sort_keys=False), encoding='utf-8')
    return normalized


def normalize_schema(schema: dict[str, Any]) -> dict[str, Any]:
    schema = dict(schema)
    schema.setdefault('classes', {})
    schema.setdefault('slots', {})
    schema.setdefault('enums', {})
    schema.setdefault('prefixes', {})
    schema.setdefault('imports', ['linkml:types'])
    schema.setdefault('default_range', 'string')
    return schema
