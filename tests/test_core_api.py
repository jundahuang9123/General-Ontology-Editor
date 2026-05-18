from pathlib import Path

from fastapi.testclient import TestClient

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


def test_generic_app_starts():
    app = create_app(schema_path=SCHEMA_PATH, product_title='Test Editor')
    client = TestClient(app)
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}
