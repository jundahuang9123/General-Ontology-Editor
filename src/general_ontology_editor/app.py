from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from jsonschema import Draft202012Validator

from .exporters import PRIMITIVES, generate_json_schema, generate_linkml, generate_rdf, generate_shacl
from .importers import import_rdf_schema
from .schema_loader import load_schema, save_schema
from .uml import generate_uml


def create_app(
    *,
    schema_path: str | Path,
    json_schema_path: str | Path | None = None,
    frontend_dist: str | Path | None = None,
    product_title: str = 'General Ontology Editor',
    mode: str = 'ontology',
    import_defaults: dict[str, Any] | None = None,
    include_validation_route: bool = True,
) -> FastAPI:
    schema_path = Path(schema_path)
    json_schema_path = Path(json_schema_path) if json_schema_path else schema_path.with_suffix('.schema.json')
    frontend_dist = Path(frontend_dist) if frontend_dist else None

    app = FastAPI(title=product_title)

    if frontend_dist and (frontend_dist / 'assets').exists():
        app.mount('/assets', StaticFiles(directory=str(frontend_dist / 'assets')), name='assets')

    def current_schema() -> dict[str, Any]:
        return load_schema(schema_path)

    def current_json_schema() -> dict[str, Any]:
        if json_schema_path.exists():
            return json.loads(json_schema_path.read_text(encoding='utf-8'))
        return json.loads(generate_json_schema(current_schema()))

    @app.get('/', response_class=HTMLResponse)
    def index():
        react_index = frontend_dist / 'index.html' if frontend_dist else None
        if react_index and react_index.exists():
            return FileResponse(react_index)
        return HTMLResponse(f'<h1>{product_title}</h1><p>Build the frontend to use the editor.</p>')

    @app.get('/health')
    def health() -> dict[str, str]:
        return {'status': 'ok'}

    @app.get('/schema')
    def schema() -> JSONResponse:
        return JSONResponse(current_json_schema())

    @app.get('/api/schema/model')
    def schema_model() -> JSONResponse:
        return JSONResponse(current_schema())

    @app.get('/api/schema/linkml')
    def schema_linkml() -> PlainTextResponse:
        return PlainTextResponse(schema_path.read_text(encoding='utf-8'), media_type='application/yaml')

    @app.put('/api/schema/linkml')
    def save_schema_linkml(payload: dict[str, str]) -> JSONResponse:
        yaml_text = payload.get('yaml')
        if not isinstance(yaml_text, str) or not yaml_text.strip():
            raise HTTPException(status_code=400, detail='Missing yaml payload')

        try:
            parsed = yaml.safe_load(yaml_text)
        except yaml.YAMLError as exc:
            raise HTTPException(status_code=400, detail=f'Invalid YAML: {exc}') from exc

        if not isinstance(parsed, dict):
            raise HTTPException(status_code=400, detail='Schema YAML must be a mapping')

        for key in ('classes', 'slots'):
            if key not in parsed or not isinstance(parsed[key], dict):
                raise HTTPException(status_code=400, detail=f'Schema YAML must include {key}')

        save_schema(schema_path, parsed)
        return JSONResponse({'status': 'ok'})

    @app.post('/api/schema/import')
    async def import_schema(file: UploadFile = File(...)) -> JSONResponse:
        content = await file.read()
        try:
            text = content.decode('utf-8')
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail='Uploaded RDF/SHACL file must be UTF-8 text') from exc

        defaults = import_defaults or {
            'id': 'https://example.org/linkml/imported-ontology',
            'name': 'imported_ontology',
            'prefixes': {
                'linkml': 'https://w3id.org/linkml/',
                'ex': 'https://example.org/ontology/',
            },
            'imports': ['linkml:types'],
            'default_prefix': 'ex',
        }

        try:
            schema = import_rdf_schema(text, file.filename or 'uploaded.ttl', defaults)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return JSONResponse(schema)

    @app.get('/schema/options')
    def get_schema_options() -> dict[str, list[str]]:
        schema = current_schema()
        return {
            'classes': sorted(schema.get('classes', {}).keys()),
            'enums': sorted(schema.get('enums', {}).keys()),
            'primitives': PRIMITIVES,
        }

    if include_validation_route:

        @app.post('/validate')
        def validate(payload: dict[str, Any]) -> JSONResponse:
            validator = Draft202012Validator(current_json_schema())
            errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
            if errors:
                return JSONResponse(
                    status_code=422,
                    content={
                        'valid': False,
                        'errors': [
                            {
                                'path': '.'.join(str(part) for part in err.path),
                                'message': err.message,
                            }
                            for err in errors
                        ],
                    },
                )
            return JSONResponse({'valid': True, 'errors': []})

    @app.get('/schema/uml')
    def get_uml() -> dict[str, str]:
        return {'mermaid': generate_uml(current_schema())}

    @app.get('/schema/export/shacl')
    def export_schema_shacl() -> PlainTextResponse:
        return PlainTextResponse(generate_shacl(current_schema()), media_type='text/turtle')

    @app.get('/schema/export/rdf')
    def export_schema_rdf() -> PlainTextResponse:
        return PlainTextResponse(generate_rdf(current_schema()), media_type='text/turtle')

    @app.get('/schema/export/linkml')
    def export_schema_linkml() -> PlainTextResponse:
        return PlainTextResponse(generate_linkml(current_schema()), media_type='application/yaml')

    @app.get('/schema/export/jsonschema')
    def export_schema_json_schema() -> PlainTextResponse:
        return PlainTextResponse(generate_json_schema(current_schema()), media_type='application/schema+json')

    app.state.schema_path = schema_path
    app.state.json_schema_path = json_schema_path
    app.state.product_title = product_title
    app.state.mode = mode
    return app
