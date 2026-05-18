from pathlib import Path

from general_ontology_editor import create_app

BASE_DIR = Path('/app') if Path('/app').exists() else Path(__file__).resolve().parents[2]

app = create_app(
    schema_path=BASE_DIR / 'schemas' / 'ontology.yaml',
    json_schema_path=BASE_DIR / 'generated' / 'jsonschema' / 'ontology.schema.json',
    frontend_dist=BASE_DIR / 'frontend-dist',
    product_title='General Ontology Editor',
    mode='ontology',
)
