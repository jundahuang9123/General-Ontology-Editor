from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from rdflib import BNode, Graph, OWL, RDF, RDFS, URIRef, XSD
from rdflib.collection import Collection
from rdflib.namespace import Namespace

SH = Namespace('http://www.w3.org/ns/shacl#')
SKOS = Namespace('http://www.w3.org/2004/02/skos/core#')

XSD_RANGES = {
    str(XSD.string): 'string',
    str(XSD.integer): 'integer',
    str(XSD.int): 'integer',
    str(XSD.float): 'float',
    str(XSD.double): 'float',
    str(XSD.decimal): 'float',
    str(XSD.boolean): 'boolean',
    str(XSD.anyURI): 'anyURI',
}

STANDARD_PREFIXES = {'xml', 'rdf', 'rdfs', 'xsd', 'owl', 'sh', 'skos', 'linkml'}

OWL_CLASS_AXIOMS = (RDFS.subClassOf, OWL.equivalentClass)
OWL_RANGE_PREDICATES = (OWL.someValuesFrom, OWL.allValuesFrom, OWL.onClass, OWL.onDataRange)
OWL_MIN_CARDINALITY = (OWL.minCardinality, OWL.minQualifiedCardinality)
OWL_MAX_CARDINALITY = (OWL.maxCardinality, OWL.maxQualifiedCardinality)
OWL_EXACT_CARDINALITY = (OWL.cardinality, OWL.qualifiedCardinality)


def import_rdf_schema(text: str, filename: str, defaults: dict[str, Any]) -> dict[str, Any]:
    graph = parse_graph(text, filename)
    prefixes = collect_prefixes(graph, defaults.get('prefixes', {}))

    class_uris = discover_class_uris(graph)
    property_uris = discover_property_uris(graph)

    classes: dict[str, dict[str, Any]] = {}
    slots: dict[str, dict[str, Any]] = {}
    enums: dict[str, dict[str, dict[str, None]]] = {}
    class_names: dict[str, str] = {}
    slot_names: dict[str, str] = {}

    def ensure_class(uri: URIRef) -> str:
        key = str(uri)
        if key in class_names:
            return class_names[key]
        name = unique_name(to_identifier(local_name(uri), class_name=True), classes)
        class_names[key] = name
        definition: dict[str, Any] = {
            'class_uri': curie_for(uri, prefixes),
            'slots': [],
        }
        description = first_literal(graph, uri, RDFS.comment) or first_literal(graph, uri, SKOS.definition)
        if description:
            definition['description'] = description
        classes[name] = definition
        return name

    def ensure_slot(uri: URIRef) -> str:
        key = str(uri)
        if key in slot_names:
            return slot_names[key]
        name = unique_name(to_identifier(local_name(uri), class_name=False), slots)
        slot_names[key] = name
        definition: dict[str, Any] = {
            'slot_uri': curie_for(uri, prefixes),
            'range': 'string',
        }
        description = first_literal(graph, uri, RDFS.comment) or first_literal(graph, uri, SKOS.definition)
        if description:
            definition['description'] = description
        slots[name] = definition
        return name

    for uri in sorted(class_uris, key=str):
        ensure_class(uri)
    for uri in sorted(property_uris, key=str):
        ensure_slot(uri)

    for child, parent in graph.subject_objects(RDFS.subClassOf):
        if isinstance(child, URIRef) and isinstance(parent, URIRef) and str(child) in class_names and str(parent) in class_names:
            classes[class_names[str(child)]]['is_a'] = class_names[str(parent)]

    import_shacl_shapes(graph, classes, slots, enums, class_names, slot_names, ensure_class, ensure_slot)
    import_rdfs_properties(graph, classes, slots, class_names, ensure_class, ensure_slot)
    import_owl_restrictions(graph, classes, slots, class_names, ensure_class, ensure_slot)

    remove_empty_slots(classes)

    title = defaults.get('title') or title_from_filename(filename)
    return {
        'id': defaults.get('id', 'https://example.org/linkml/imported-ontology'),
        'name': defaults.get('name', 'imported_ontology'),
        'title': title,
        'prefixes': prefixes,
        'imports': defaults.get('imports', ['linkml:types']),
        'default_prefix': choose_default_prefix(prefixes, defaults.get('default_prefix')),
        'default_range': 'string',
        'types': {
            'anyURI': {
                'uri': 'xsd:anyURI',
                'base': 'str',
            },
        },
        'classes': classes,
        'slots': slots,
        'enums': enums,
    }


def parse_graph(text: str, filename: str) -> Graph:
    formats = guessed_formats(filename)
    errors: list[str] = []
    for rdf_format in formats:
        graph = Graph()
        try:
            graph.parse(data=text, format=rdf_format)
            return graph
        except Exception as exc:  # noqa: BLE001 - rdflib raises several parser-specific exceptions
            errors.append(f'{rdf_format}: {exc}')
    raise ValueError('Could not parse RDF/SHACL file. Tried: ' + '; '.join(errors))


def guessed_formats(filename: str) -> list[str]:
    suffix = Path(filename).suffix.lower()
    by_extension = {
        '.ttl': 'turtle',
        '.shacl': 'turtle',
        '.rdf': 'xml',
        '.owl': 'xml',
        '.xml': 'xml',
        '.jsonld': 'json-ld',
        '.json': 'json-ld',
        '.nt': 'nt',
        '.n3': 'n3',
        '.trig': 'trig',
    }
    preferred = by_extension.get(suffix)
    formats = [preferred] if preferred else []
    for fallback in ['turtle', 'xml', 'json-ld', 'nt', 'n3', 'trig']:
        if fallback not in formats:
            formats.append(fallback)
    return formats


def collect_prefixes(graph: Graph, defaults: dict[str, str]) -> dict[str, str]:
    prefixes = dict(defaults)
    for prefix, namespace in graph.namespaces():
        if prefix:
            prefixes[str(prefix)] = str(namespace)
    prefixes.setdefault('linkml', 'https://w3id.org/linkml/')
    prefixes.setdefault('xsd', str(XSD))
    return prefixes


def discover_class_uris(graph: Graph) -> set[URIRef]:
    class_uris: set[URIRef] = set()
    for rdf_type in (OWL.Class, RDFS.Class):
        class_uris.update(uri for uri in graph.subjects(RDF.type, rdf_type) if isinstance(uri, URIRef))
    class_uris.update(uri for uri in graph.objects(None, SH.targetClass) if isinstance(uri, URIRef))
    for property_shape in graph.objects(None, SH.property):
        if not is_resource_node(property_shape):
            continue
        node_shape = graph.value(property_shape, SH.node)
        if is_resource_node(node_shape):
            target_class = target_class_for_shape(graph, node_shape)
            if isinstance(target_class, URIRef):
                class_uris.add(target_class)
    for restriction in discover_owl_restrictions(graph):
        range_uri = range_from_owl_restriction(graph, restriction)
        if isinstance(range_uri, URIRef) and str(range_uri) not in XSD_RANGES and range_uri != RDFS.Literal:
            class_uris.add(range_uri)
    for child, parent in graph.subject_objects(RDFS.subClassOf):
        if isinstance(child, URIRef):
            class_uris.add(child)
        if isinstance(parent, URIRef):
            class_uris.add(parent)
    for _, domain in graph.subject_objects(RDFS.domain):
        if isinstance(domain, URIRef):
            class_uris.add(domain)
    for _, range_uri in graph.subject_objects(RDFS.range):
        if isinstance(range_uri, URIRef) and str(range_uri) not in XSD_RANGES and range_uri != RDFS.Literal:
            class_uris.add(range_uri)
    return class_uris


def discover_property_uris(graph: Graph) -> set[URIRef]:
    property_uris: set[URIRef] = set()
    for rdf_type in (RDF.Property, OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty):
        property_uris.update(uri for uri in graph.subjects(RDF.type, rdf_type) if isinstance(uri, URIRef))
    property_uris.update(uri for uri in graph.subjects(RDFS.domain, None) if isinstance(uri, URIRef))
    property_uris.update(uri for uri in graph.subjects(RDFS.range, None) if isinstance(uri, URIRef))
    property_uris.update(uri for uri in graph.objects(None, SH.path) if isinstance(uri, URIRef))
    property_uris.update(uri for uri in graph.objects(None, OWL.onProperty) if isinstance(uri, URIRef))
    return property_uris


def import_shacl_shapes(
    graph: Graph,
    classes: dict[str, dict[str, Any]],
    slots: dict[str, dict[str, Any]],
    enums: dict[str, dict[str, dict[str, None]]],
    class_names: dict[str, str],
    slot_names: dict[str, str],
    ensure_class,
    ensure_slot,
) -> None:
    shape_nodes = set(graph.subjects(RDF.type, SH.NodeShape)) | set(graph.subjects(SH.targetClass, None))
    for shape in shape_nodes:
        target = graph.value(shape, SH.targetClass)
        if not isinstance(target, URIRef):
            continue
        class_name = ensure_class(target)
        for property_shape in graph.objects(shape, SH.property):
            if not is_resource_node(property_shape):
                continue
            path = graph.value(property_shape, SH.path)
            if not isinstance(path, URIRef):
                continue
            slot_name = ensure_slot(path)
            slot = slots[slot_name]
            slot['range'] = range_from_shacl(graph, property_shape, classes, enums, ensure_class, slot_name)

            min_count = numeric_literal(graph.value(property_shape, SH.minCount))
            max_count = numeric_literal(graph.value(property_shape, SH.maxCount))
            if min_count and min_count >= 1:
                slot['required'] = True
            if max_count is None or max_count > 1:
                slot['multivalued'] = True
            elif max_count == 1:
                slot.pop('multivalued', None)

            append_unique(classes[class_name].setdefault('slots', []), slot_name)
            slot_names[str(path)] = slot_name
            class_names[str(target)] = class_name


def range_from_shacl(graph: Graph, property_shape: BNode | URIRef, classes, enums, ensure_class, slot_name: str) -> str:
    class_range = graph.value(property_shape, SH['class'])
    if isinstance(class_range, URIRef):
        return ensure_class(class_range)

    node_shape = graph.value(property_shape, SH.node)
    if is_resource_node(node_shape):
        target_class = target_class_for_shape(graph, node_shape)
        if isinstance(target_class, URIRef):
            return ensure_class(target_class)

    datatype = graph.value(property_shape, SH.datatype)
    if isinstance(datatype, URIRef):
        return XSD_RANGES.get(str(datatype), 'string')

    in_list = graph.value(property_shape, SH['in'])
    if in_list is not None:
        values = [str(value) for value in Collection(graph, in_list)]
        enum_name = unique_name(to_identifier(f'{slot_name}_enum', class_name=True), enums)
        enums[enum_name] = {'permissible_values': {value: None for value in values}}
        return enum_name

    return 'string'


def import_rdfs_properties(graph: Graph, classes, slots, class_names, ensure_class, ensure_slot) -> None:
    for property_uri in discover_property_uris(graph):
        slot_name = ensure_slot(property_uri)
        slot = slots[slot_name]

        for domain in graph.objects(property_uri, RDFS.domain):
            if isinstance(domain, URIRef):
                class_name = ensure_class(domain)
                append_unique(classes[class_name].setdefault('slots', []), slot_name)

        for range_uri in graph.objects(property_uri, RDFS.range):
            if isinstance(range_uri, URIRef):
                if str(range_uri) in XSD_RANGES:
                    slot['range'] = XSD_RANGES[str(range_uri)]
                elif range_uri == RDFS.Literal:
                    slot['range'] = 'string'
                else:
                    slot['range'] = ensure_class(range_uri)


def import_owl_restrictions(graph: Graph, classes, slots, class_names, ensure_class, ensure_slot) -> None:
    for class_uri in discover_class_uris(graph):
        class_name = ensure_class(class_uri)
        for restriction in restrictions_for_class(graph, class_uri):
            property_uri = graph.value(restriction, OWL.onProperty)
            if not isinstance(property_uri, URIRef):
                continue

            slot_name = ensure_slot(property_uri)
            slot = slots[slot_name]
            range_uri = range_from_owl_restriction(graph, restriction)
            if isinstance(range_uri, URIRef):
                apply_range_uri(slot, range_uri, ensure_class)

            some_values = graph.value(restriction, OWL.someValuesFrom)
            min_count = first_numeric_literal(graph, restriction, OWL_MIN_CARDINALITY)
            max_count = first_numeric_literal(graph, restriction, OWL_MAX_CARDINALITY)
            exact_count = first_numeric_literal(graph, restriction, OWL_EXACT_CARDINALITY)
            if exact_count is not None:
                min_count = exact_count
                max_count = exact_count

            if some_values is not None or (min_count is not None and min_count >= 1):
                slot['required'] = True
            if max_count is None or max_count > 1:
                slot['multivalued'] = True
            elif max_count == 1:
                slot.pop('multivalued', None)

            append_unique(classes[class_name].setdefault('slots', []), slot_name)


def apply_range_uri(slot: dict[str, Any], range_uri: URIRef, ensure_class) -> None:
    if str(range_uri) in XSD_RANGES:
        slot['range'] = XSD_RANGES[str(range_uri)]
    elif range_uri == RDFS.Literal:
        slot['range'] = 'string'
    else:
        slot['range'] = ensure_class(range_uri)


def curie_for(uri: URIRef, prefixes: dict[str, str]) -> str:
    text = str(uri)
    for prefix, namespace in sorted(prefixes.items(), key=lambda item: len(item[1]), reverse=True):
        if text.startswith(namespace):
            return f'{prefix}:{text[len(namespace):]}'

    namespace, local = split_namespace(text)
    prefix = unique_prefix(prefixes)
    prefixes[prefix] = namespace
    return f'{prefix}:{local}'


def split_namespace(uri: str) -> tuple[str, str]:
    if '#' in uri:
        namespace, local = uri.rsplit('#', 1)
        return namespace + '#', local
    namespace, local = uri.rstrip('/').rsplit('/', 1)
    return namespace + '/', local


def local_name(uri: URIRef) -> str:
    return split_namespace(str(uri))[1]


def to_identifier(value: str, class_name: bool) -> str:
    value = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', value)
    value = re.sub(r'[^0-9A-Za-z_]+', '_', value).strip('_')
    if not value:
        value = 'ImportedClass' if class_name else 'imported_property'
    if class_name:
        value = ''.join(part[:1].upper() + part[1:] for part in value.split('_') if part)
    else:
        value = value.lower()
    if value[:1].isdigit():
        value = ('Class' if class_name else 'slot') + value
    return value


def unique_name(base: str, existing: dict[str, Any]) -> str:
    if base not in existing:
        return base
    index = 2
    while f'{base}{index}' in existing:
        index += 1
    return f'{base}{index}'


def unique_prefix(prefixes: dict[str, str]) -> str:
    index = 1
    while f'ns{index}' in prefixes:
        index += 1
    return f'ns{index}'


def choose_default_prefix(prefixes: dict[str, str], preferred: str | None) -> str:
    if preferred and preferred in prefixes:
        return preferred
    for prefix in prefixes:
        if prefix not in STANDARD_PREFIXES:
            return prefix
    return 'ex'


def title_from_filename(filename: str) -> str:
    stem = Path(filename).stem or 'Imported ontology'
    return stem.replace('_', ' ').replace('-', ' ').title()


def first_literal(graph: Graph, subject: URIRef, predicate: URIRef) -> str | None:
    value = graph.value(subject, predicate)
    return str(value) if value is not None else None


def numeric_literal(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def first_numeric_literal(graph: Graph, subject: BNode | URIRef, predicates: tuple[URIRef, ...]) -> int | None:
    for predicate in predicates:
        value = numeric_literal(graph.value(subject, predicate))
        if value is not None:
            return value
    return None


def append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def remove_empty_slots(classes: dict[str, dict[str, Any]]) -> None:
    for class_def in classes.values():
        if not class_def.get('slots'):
            class_def.pop('slots', None)


def is_resource_node(value: Any) -> bool:
    return isinstance(value, (BNode, URIRef))


def target_class_for_shape(graph: Graph, shape: BNode | URIRef) -> URIRef | None:
    target = graph.value(shape, SH.targetClass)
    return target if isinstance(target, URIRef) else None


def discover_owl_restrictions(graph: Graph) -> set[BNode | URIRef]:
    restrictions: set[BNode | URIRef] = set()
    restrictions.update(node for node in graph.subjects(RDF.type, OWL.Restriction) if is_resource_node(node))
    restrictions.update(node for node in graph.subjects(OWL.onProperty, None) if is_resource_node(node))
    return restrictions


def restrictions_for_class(graph: Graph, class_uri: URIRef) -> set[BNode | URIRef]:
    restrictions: set[BNode | URIRef] = set()
    for predicate in OWL_CLASS_AXIOMS:
        for axiom_node in graph.objects(class_uri, predicate):
            for member in owl_axiom_members(graph, axiom_node):
                if is_owl_restriction(graph, member):
                    restrictions.add(member)
    return restrictions


def owl_axiom_members(graph: Graph, node, seen: set[Any] | None = None):
    if not is_resource_node(node):
        return

    seen = seen or set()
    if node in seen:
        return
    seen.add(node)
    yield node

    intersection = graph.value(node, OWL.intersectionOf)
    if intersection is None:
        return

    for member in Collection(graph, intersection):
        yield from owl_axiom_members(graph, member, seen)


def is_owl_restriction(graph: Graph, node) -> bool:
    return is_resource_node(node) and (
        (node, RDF.type, OWL.Restriction) in graph or graph.value(node, OWL.onProperty) is not None
    )


def range_from_owl_restriction(graph: Graph, restriction: BNode | URIRef) -> URIRef | None:
    for predicate in OWL_RANGE_PREDICATES:
        range_uri = graph.value(restriction, predicate)
        if isinstance(range_uri, URIRef):
            return range_uri
    return None
