#!/usr/bin/env sh
set -eu
mkdir -p /app/generated/jsonschema /app/generated/shacl
python -m linkml.generators.jsonschemagen /app/schemas/ontology.yaml > /app/generated/jsonschema/ontology.schema.json
python -m linkml.generators.shaclgen /app/schemas/ontology.yaml > /app/generated/shacl/ontology.shacl.ttl
