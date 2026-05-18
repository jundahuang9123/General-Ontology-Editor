from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .exporters import generate_json_schema, schema_from_source


def validate_schema(schema_or_path: dict[str, Any] | str | Path, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    schema = schema_from_source(schema_or_path)
    structural_errors = structural_schema_errors(schema)
    if payload is None:
        return {'valid': not structural_errors, 'errors': structural_errors}

    json_schema = json.loads(generate_json_schema(schema))
    validator = Draft202012Validator(json_schema)
    payload_errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    return {
        'valid': not structural_errors and not payload_errors,
        'errors': structural_errors
        + [
            {
                'path': '.'.join(str(part) for part in err.path),
                'message': err.message,
            }
            for err in payload_errors
        ],
    }


def structural_schema_errors(schema: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if not isinstance(schema.get('classes'), dict):
        errors.append({'path': 'classes', 'message': 'classes must be a mapping'})
    if not isinstance(schema.get('slots'), dict):
        errors.append({'path': 'slots', 'message': 'slots must be a mapping'})
    for class_name, class_def in (schema.get('classes') or {}).items():
        for slot_name in class_def.get('slots', []) or []:
            if slot_name not in schema.get('slots', {}):
                errors.append({'path': f'classes.{class_name}.slots', 'message': f'Undefined slot: {slot_name}'})
    return errors
