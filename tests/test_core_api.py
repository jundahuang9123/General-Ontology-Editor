from pathlib import Path

from fastapi.testclient import TestClient
from rdflib import Graph, Namespace, RDF, RDFS, OWL

from general_ontology_editor import create_app, generate_rdf, generate_shacl, load_schema


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / 'schemas' / 'ontology.yaml'


def test_package_loads_schema():
    schema = load_schema(SCHEMA_PATH)
    assert schema['classes']
    assert schema['slots']


def test_exports_generic_artifacts():
    shacl = generate_shacl(SCHEMA_PATH)
    rdf = generate_rdf(SCHEMA_PATH)
    assert 'sh:NodeShape' in shacl
    assert 'owl:Class' in rdf


def test_rdf_export_supports_explicit_domain_range_annotations():
    schema = {
        'id': 'https://example.org/minimal-profile',
        'name': 'minimal_profile',
        'prefixes': {
            'dcat': 'http://www.w3.org/ns/dcat#',
            'cx': 'https://w3id.org/cx#',
            'owl': 'http://www.w3.org/2002/07/owl#',
        },
        'default_prefix': 'cx',
        'annotations': {'emit_profile_metadata': {'value': False}},
        'classes': {
            'DcatDataset': {
                'class_uri': 'dcat:Dataset',
                'slots': ['describesAssetType'],
                'annotations': {'emit_rdf': {'value': False}},
            },
            'BIMDataset': {
                'class_uri': 'cx:BIMDataset',
                'is_a': 'DcatDataset',
            },
        },
        'slots': {
            'describesAssetType': {
                'slot_uri': 'cx:describesAssetType',
                'range': 'owl:Class',
                'annotations': {
                    'rdf_property_type': {'value': 'owl:ObjectProperty'},
                    'rdf_domain': {'value': 'dcat:Dataset'},
                    'rdf_range': {'value': 'owl:Class'},
                },
            },
        },
    }
    graph = Graph().parse(data=generate_rdf(schema), format='turtle')
    CX = Namespace('https://w3id.org/cx#')
    DCAT = Namespace('http://www.w3.org/ns/dcat#')

    assert set(graph) == {
        (CX.BIMDataset, RDF.type, OWL.Class),
        (CX.BIMDataset, RDFS.subClassOf, DCAT.Dataset),
        (CX.describesAssetType, RDF.type, OWL.ObjectProperty),
        (CX.describesAssetType, RDFS.domain, DCAT.Dataset),
        (CX.describesAssetType, RDFS.range, OWL.Class),
    }


def test_generic_app_starts():
    app = create_app(schema_path=SCHEMA_PATH, product_title='Test Editor')
    client = TestClient(app)
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}
