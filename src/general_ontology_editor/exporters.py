from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import yaml
from rdflib import BNode, Graph, Literal, Namespace, RDF, RDFS, URIRef, XSD
from rdflib.collection import Collection

from .schema_loader import load_schema, normalize_schema

PRIMITIVES = ['string', 'anyURI', 'integer', 'float', 'boolean']


def schema_from_source(schema_or_path: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(schema_or_path, (str, Path)):
        return load_schema(schema_or_path)
    return normalize_schema(schema_or_path)


def generate_linkml(schema_or_path: dict[str, Any] | str | Path) -> str:
    return yaml.safe_dump(schema_from_source(schema_or_path), sort_keys=False)


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


def inherited_slots(class_name: str, schema: dict[str, Any], seen: set[str] | None = None) -> list[str]:
    seen = seen or set()
    if class_name in seen:
        return []
    seen.add(class_name)

    classes = schema.get('classes', {})
    class_def = classes.get(class_name, {})
    parent = class_def.get('is_a')
    parent_slots = inherited_slots(parent, schema, seen) if parent in classes else []
    return parent_slots + list(class_def.get('slots', []))


def generate_shacl(schema_or_path: dict[str, Any] | str | Path) -> str:
    schema = schema_from_source(schema_or_path)
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

            min_count = annotation_int(slot_def, 'min_count')
            max_count = annotation_int(slot_def, 'max_count')

            if slot_def.get('required') or (min_count is not None and min_count >= 1):
                graph.add((prop, SH.minCount, Literal(min_count or 1)))
            if max_count is not None:
                graph.add((prop, SH.maxCount, Literal(max_count)))
            elif not slot_def.get('multivalued', False):
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

    return graph.serialize(format='turtle')


def generate_rdf(schema_or_path: dict[str, Any] | str | Path) -> str:
    schema = schema_from_source(schema_or_path)
    classes = schema.get('classes', {})
    slots = schema.get('slots', {})

    OWL = Namespace('http://www.w3.org/2002/07/owl#')
    PROF = Namespace('http://www.w3.org/ns/dx/prof/')
    DCTERMS = Namespace('http://purl.org/dc/terms/')
    graph = Graph()
    graph.bind('rdf', RDF)
    graph.bind('rdfs', RDFS)
    graph.bind('owl', OWL)
    graph.bind('prof', PROF)
    graph.bind('dcterms', DCTERMS)
    graph.bind('xsd', XSD)

    for prefix, uri in schema.get('prefixes', {}).items():
        if isinstance(uri, str):
            graph.bind(prefix, Namespace(uri))

    schema_id = schema.get('id')
    if annotation_bool(schema, 'emit_profile_metadata') is not False and isinstance(schema_id, str) and schema_id.startswith(('http://', 'https://')):
        profile_uri = URIRef(schema_id)
        graph.add((profile_uri, RDF.type, PROF.Profile))
        if schema.get('title'):
            graph.add((profile_uri, DCTERMS.title, Literal(schema['title'])))
        if schema.get('description'):
            graph.add((profile_uri, DCTERMS.description, Literal(schema['description'])))

    for name, definition in classes.items():
        if annotation_bool(definition, 'emit_rdf') is False:
            continue
        uri = class_uri(name, definition, schema)
        graph.add((uri, RDF.type, OWL.Class))
        parent = definition.get('is_a')
        if parent in classes:
            graph.add((uri, RDFS.subClassOf, class_uri(parent, classes[parent], schema)))

    for slot_name, slot_def in slots.items():
        uri = slot_uri(slot_name, slot_def, schema)
        slot_range = slot_def.get('range', 'string')
        explicit_type = explicit_property_type(slot_def, schema)
        property_type = explicit_type or (OWL.ObjectProperty if slot_range in classes else OWL.DatatypeProperty)
        if explicit_type is not None:
            graph.add((uri, RDF.type, property_type))
        else:
            graph.add((uri, RDF.type, RDF.Property))
            graph.add((uri, RDF.type, property_type))

        explicit_domain = annotation_uri(slot_def, 'rdf_domain', schema)
        if explicit_domain is not None:
            graph.add((uri, RDFS.domain, explicit_domain))
        else:
            for class_name, class_def in classes.items():
                if slot_name in inherited_slots(class_name, schema):
                    graph.add((uri, RDFS.domain, class_uri(class_name, class_def, schema)))

        explicit_range = annotation_uri(slot_def, 'rdf_range', schema)
        if explicit_range is not None:
            graph.add((uri, RDFS.range, explicit_range))
        elif slot_range in classes:
            graph.add((uri, RDFS.range, class_uri(slot_range, classes[slot_range], schema)))
        else:
            datatype = datatype_for_range(slot_range)
            graph.add((uri, RDFS.range, datatype if datatype is not None else RDFS.Literal))

    return graph.serialize(format='turtle')


def generate_json_schema(schema_or_path: dict[str, Any] | str | Path) -> str:
    if isinstance(schema_or_path, (str, Path)):
        try:
            from linkml.generators.jsonschemagen import JsonSchemaGenerator

            return JsonSchemaGenerator(str(schema_or_path)).serialize()
        except Exception:
            pass

    schema = schema_from_source(schema_or_path)
    try:
        from linkml.generators.jsonschemagen import JsonSchemaGenerator

        with tempfile.NamedTemporaryFile('w', suffix='.yaml', delete=False, encoding='utf-8') as handle:
            yaml.safe_dump(schema, handle, sort_keys=False)
            temp_path = handle.name
        try:
            return JsonSchemaGenerator(temp_path).serialize()
        finally:
            Path(temp_path).unlink(missing_ok=True)
    except Exception:
        return json.dumps(minimal_json_schema(schema), indent=2)


def minimal_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    definitions: dict[str, Any] = {}
    for class_name, class_def in schema.get('classes', {}).items():
        properties: dict[str, Any] = {}
        required: list[str] = []
        for slot_name in inherited_slots(class_name, schema):
            slot_def = schema.get('slots', {}).get(slot_name, {})
            properties[slot_name] = json_schema_for_range(slot_def.get('range', 'string'), schema)
            if slot_def.get('required'):
                required.append(slot_name)
        class_schema: dict[str, Any] = {'type': 'object', 'properties': properties}
        if required:
            class_schema['required'] = required
        definitions[class_name] = class_schema
    return {'$schema': 'https://json-schema.org/draft/2020-12/schema', '$defs': definitions}


def json_schema_for_range(range_name: str, schema: dict[str, Any]) -> dict[str, Any]:
    if range_name in schema.get('classes', {}):
        return {'$ref': f'#/$defs/{range_name}'}
    if range_name in schema.get('enums', {}):
        values = list((schema['enums'][range_name].get('permissible_values') or {}).keys())
        return {'type': 'string', 'enum': values}
    return {
        'integer': {'type': 'integer'},
        'float': {'type': 'number'},
        'boolean': {'type': 'boolean'},
        'anyURI': {'type': 'string', 'format': 'uri'},
    }.get(range_name, {'type': 'string'})


def annotation_value(definition: dict[str, Any], key: str) -> Any:
    annotations = definition.get('annotations') or {}
    value = annotations.get(key)
    if isinstance(value, dict):
        return value.get('value')
    return value


def annotation_bool(definition: dict[str, Any], key: str) -> bool | None:
    value = annotation_value(definition, key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'true', 'yes', '1'}:
            return True
        if normalized in {'false', 'no', '0'}:
            return False
    return None


def annotation_uri(definition: dict[str, Any], key: str, schema: dict[str, Any]) -> URIRef | None:
    value = annotation_value(definition, key)
    return expand_curie(value, schema.get('prefixes', {})) if isinstance(value, str) else None


def explicit_property_type(slot_def: dict[str, Any], schema: dict[str, Any]) -> URIRef | None:
    value = annotation_value(slot_def, 'rdf_property_type')
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if normalized.lower() == 'object':
        return URIRef('http://www.w3.org/2002/07/owl#ObjectProperty')
    if normalized.lower() == 'datatype':
        return URIRef('http://www.w3.org/2002/07/owl#DatatypeProperty')
    return expand_curie(normalized, schema.get('prefixes', {}))


def annotation_int(definition: dict[str, Any], key: str) -> int | None:
    value = annotation_value(definition, key)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
