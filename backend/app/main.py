from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from jsonschema import Draft202012Validator
from rdflib import BNode, Graph, Literal, Namespace, RDF, RDFS, URIRef, XSD
from rdflib.collection import Collection

BASE_DIR = Path('/app') if Path('/app').exists() else Path(__file__).resolve().parents[2]
FRONTEND_DIST = BASE_DIR / 'frontend-dist'
LINKML_SCHEMA_PATH = BASE_DIR / 'schemas' / 'ontology.yaml'
JSON_SCHEMA_PATH = BASE_DIR / 'generated' / 'jsonschema' / 'ontology.schema.json'

PRIMITIVES = ['string', 'anyURI', 'integer', 'float', 'boolean']

app = FastAPI(title='General Ontology Editor')

if (FRONTEND_DIST / 'assets').exists():
    app.mount('/assets', StaticFiles(directory=str(FRONTEND_DIST / 'assets')), name='assets')


def load_linkml_schema() -> dict[str, Any]:
    if not LINKML_SCHEMA_PATH.exists():
        raise FileNotFoundError(f'Missing LinkML schema: {LINKML_SCHEMA_PATH}')
    schema = yaml.safe_load(LINKML_SCHEMA_PATH.read_text(encoding='utf-8')) or {}
    if not isinstance(schema, dict):
        raise ValueError('LinkML schema must be a mapping')
    schema.setdefault('classes', {})
    schema.setdefault('slots', {})
    schema.setdefault('enums', {})
    schema.setdefault('prefixes', {})
    return schema


def load_json_schema() -> dict[str, Any]:
    if not JSON_SCHEMA_PATH.exists():
        raise FileNotFoundError(f'Missing generated JSON Schema: {JSON_SCHEMA_PATH}')
    return json.loads(JSON_SCHEMA_PATH.read_text(encoding='utf-8'))


def get_validator() -> Draft202012Validator:
    return Draft202012Validator(load_json_schema())


def expand_curie(value: str | None, prefixes: dict[str, Any]) -> URIRef | None:
    if not value:
        return None
    if value.startswith(('http://', 'https://')):
        return URIRef(value)
    if ':' in value:
        prefix, local = value.split(':', 1)
        namespace = prefixes.get(prefix)
        if isinstance(namespace, str):
            return URIRef(namespace + local)
    return None


def fallback_uri(name: str, schema: dict[str, Any]) -> URIRef:
    prefixes = schema.get('prefixes', {})
    default_prefix = schema.get('default_prefix')
    if default_prefix and isinstance(prefixes.get(default_prefix), str):
        return URIRef(prefixes[default_prefix] + name)
    return URIRef(f'https://example.org/ontology/{name}')


def class_uri(class_name: str, class_def: dict[str, Any], schema: dict[str, Any]) -> URIRef:
    return expand_curie(class_def.get('class_uri'), schema.get('prefixes', {})) or fallback_uri(class_name, schema)


def slot_uri(slot_name: str, slot_def: dict[str, Any], schema: dict[str, Any]) -> URIRef:
    return expand_curie(slot_def.get('slot_uri'), schema.get('prefixes', {})) or fallback_uri(slot_name, schema)


def datatype_for_range(range_name: str) -> URIRef | None:
    return {
        'string': XSD.string,
        'integer': XSD.integer,
        'float': XSD.float,
        'boolean': XSD.boolean,
        'anyURI': XSD.anyURI,
    }.get(range_name)


def inherited_slots(class_name: str, schema: dict[str, Any]) -> list[str]:
    classes = schema.get('classes', {})
    class_def = classes.get(class_name, {})
    parent = class_def.get('is_a')
    parent_slots = inherited_slots(parent, schema) if parent in classes else []
    return parent_slots + list(class_def.get('slots', []))


@app.get('/', response_class=HTMLResponse)
def index():
    react_index = FRONTEND_DIST / 'index.html'
    if react_index.exists():
        return FileResponse(react_index)
    return HTMLResponse('<h1>General Ontology Editor</h1><p>Build the frontend to use the editor.</p>')


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.get('/schema')
def schema() -> JSONResponse:
    return JSONResponse(load_json_schema())


@app.get('/api/schema/model')
def schema_model() -> JSONResponse:
    return JSONResponse(load_linkml_schema())


@app.get('/api/schema/linkml')
def schema_linkml() -> PlainTextResponse:
    return PlainTextResponse(
        LINKML_SCHEMA_PATH.read_text(encoding='utf-8'),
        media_type='application/yaml',
    )


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

    LINKML_SCHEMA_PATH.write_text(yaml.safe_dump(parsed, sort_keys=False), encoding='utf-8')
    return JSONResponse({'status': 'ok'})


@app.get('/schema/options')
def get_schema_options() -> dict[str, list[str]]:
    schema = load_linkml_schema()
    return {
        'classes': sorted(schema.get('classes', {}).keys()),
        'enums': sorted(schema.get('enums', {}).keys()),
        'primitives': PRIMITIVES,
    }


@app.post('/validate')
def validate(payload: dict[str, Any]) -> JSONResponse:
    validator = get_validator()
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    if errors:
        return JSONResponse(
            status_code=422,
            content={
                'valid': False,
                'errors': [
                    {
                        'path': '.'.join(str(x) for x in err.path),
                        'message': err.message,
                    }
                    for err in errors
                ],
            },
        )
    return JSONResponse({'valid': True, 'errors': []})


@app.get('/schema/uml')
def get_uml() -> dict[str, str]:
    schema = load_linkml_schema()
    classes = schema.get('classes', {})
    slots = schema.get('slots', {})
    enums = schema.get('enums', {})

    uml = 'classDiagram\n'
    for name, class_def in classes.items():
        uml += f'  class {name} {{\n'
        for slot_name in inherited_slots(name, schema):
            slot_def = slots.get(slot_name, {})
            slot_range = slot_def.get('range', 'string')
            required = slot_def.get('required', False)
            multivalued = slot_def.get('multivalued', False)
            card = '[1..*]' if required and multivalued else '[1]' if required else '[*]' if multivalued else '[0..1]'
            enum = enums.get(slot_range)
            if enum:
                values = ','.join((enum.get('permissible_values') or {}).keys())
                uml += f'    {slot_name} : {slot_range} {card} [{values}]\n'
            else:
                uml += f'    {slot_name} : {slot_range} {card}\n'
        uml += '  }\n'

    for name, class_def in classes.items():
        parent = class_def.get('is_a')
        if parent in classes:
            uml += f'  {name} --|> {parent}\n'
        for slot_name in inherited_slots(name, schema):
            slot_range = slots.get(slot_name, {}).get('range')
            if slot_range in classes:
                uml += f'  {name} --> {slot_range} : {slot_name}\n'

    return {'mermaid': uml}


@app.get('/schema/export/shacl')
def export_schema_shacl() -> PlainTextResponse:
    schema = load_linkml_schema()
    classes = schema.get('classes', {})
    slots = schema.get('slots', {})
    enums = schema.get('enums', {})

    SH = Namespace('http://www.w3.org/ns/shacl#')
    graph = Graph()
    graph.bind('sh', SH)
    graph.bind('rdf', RDF)
    graph.bind('rdfs', RDFS)
    graph.bind('xsd', XSD)

    for prefix, uri in schema.get('prefixes', {}).items():
        if isinstance(uri, str):
            graph.bind(prefix, Namespace(uri))

    for name, definition in classes.items():
        target = class_uri(name, definition, schema)
        shape = URIRef(str(target) + 'Shape')
        graph.add((shape, RDF.type, SH.NodeShape))
        graph.add((shape, SH.targetClass, target))

        for slot_name in inherited_slots(name, schema):
            slot_def = slots.get(slot_name, {})
            prop = BNode()
            graph.add((shape, SH.property, prop))
            graph.add((prop, SH.path, slot_uri(slot_name, slot_def, schema)))

            if slot_def.get('required'):
                graph.add((prop, SH.minCount, Literal(1)))
            if not slot_def.get('multivalued', False):
                graph.add((prop, SH.maxCount, Literal(1)))

            slot_range = slot_def.get('range', 'string')
            if slot_range in classes:
                graph.add((prop, SH['class'], class_uri(slot_range, classes[slot_range], schema)))
            elif slot_range in enums:
                values = list((enums[slot_range].get('permissible_values') or {}).keys())
                list_node = BNode()
                Collection(graph, list_node, [Literal(value) for value in values])
                graph.add((prop, SH['in'], list_node))
            else:
                datatype = datatype_for_range(slot_range)
                if datatype is not None:
                    graph.add((prop, SH.datatype, datatype))

    return PlainTextResponse(graph.serialize(format='turtle'), media_type='text/turtle')


@app.get('/schema/export/rdf')
def export_schema_rdf() -> PlainTextResponse:
    schema = load_linkml_schema()
    classes = schema.get('classes', {})
    slots = schema.get('slots', {})

    OWL = Namespace('http://www.w3.org/2002/07/owl#')
    graph = Graph()
    graph.bind('rdf', RDF)
    graph.bind('rdfs', RDFS)
    graph.bind('owl', OWL)
    graph.bind('xsd', XSD)

    for prefix, uri in schema.get('prefixes', {}).items():
        if isinstance(uri, str):
            graph.bind(prefix, Namespace(uri))

    for name, definition in classes.items():
        uri = class_uri(name, definition, schema)
        graph.add((uri, RDF.type, OWL.Class))
        parent = definition.get('is_a')
        if parent in classes:
            graph.add((uri, RDFS.subClassOf, class_uri(parent, classes[parent], schema)))

    for slot_name, slot_def in slots.items():
        uri = slot_uri(slot_name, slot_def, schema)
        graph.add((uri, RDF.type, RDF.Property))

        for class_name, class_def in classes.items():
            if slot_name in inherited_slots(class_name, schema):
                graph.add((uri, RDFS.domain, class_uri(class_name, class_def, schema)))

        slot_range = slot_def.get('range', 'string')
        if slot_range in classes:
            graph.add((uri, RDFS.range, class_uri(slot_range, classes[slot_range], schema)))
        else:
            datatype = datatype_for_range(slot_range)
            if datatype is not None:
                graph.add((uri, RDFS.range, datatype))
            else:
                graph.add((uri, RDFS.range, RDFS.Literal))

    return PlainTextResponse(graph.serialize(format='turtle'), media_type='text/turtle')
