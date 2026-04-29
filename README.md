# General Ontology Editor

A Docker-first visual editor for building small to medium ontology schemas with LinkML.

The app uses a React Flow diagram as the editing surface and keeps the schema model as the source of truth. LinkML YAML is generated from the schema state and can be saved back to disk.

## What You Need

1. Docker Desktop installed.
2. Docker Desktop running.
3. This repository checked out locally.

## Start The App

1. Open a terminal in this repository.

   ```bash
   cd General-Ontology-Editor
   ```

2. Build and start the app.

   ```bash
   docker compose up --build -d
   ```

3. Open the editor in your browser.

   ```text
   http://localhost:8010/
   ```

4. Check that the backend is healthy.

   ```text
   http://localhost:8010/health
   ```

   Expected response:

   ```json
   {"status":"ok"}
   ```

## Edit An Ontology

1. Open `http://localhost:8010/`.
2. Use the canvas to inspect ontology classes.
3. Drag class nodes to organize the diagram.
4. Double-click a class node to edit it directly in the diagram.
5. Add, rename, or delete properties inside the class node.
6. Change a property range with the dropdown.
7. Toggle `Req` for required properties.
8. Toggle `Multi` for multivalued properties.
9. Connect one class node to another to create an inheritance relationship.
10. Use the inspector panel for class and enum details.
11. Watch the LinkML YAML panel update automatically.
12. Click `Save` to write the generated YAML back to:

    ```text
    schemas/ontology.yaml
    ```
13. Click `RDF` or `SHACL` to download Turtle exports from the current ontology.

## Continue From Existing RDF Or SHACL

1. Open `http://localhost:8010/`.
2. Click `Upload`.
3. Select an RDF, OWL, Turtle, JSON-LD, N-Triples, N3, TriG, or SHACL file.
4. Review the imported classes and properties on the diagram.
5. Continue editing in the canvas and inspector.
6. Click `Save` to persist the imported model as LinkML YAML.

The importer reads common OWL/RDFS class and property triples, plus SHACL node shapes, property shapes, ranges, required flags, multivalued constraints, and simple enum lists.

## Generate Schema Artifacts

After saving ontology changes, regenerate derived artifacts:

1. Run the generator.

   ```bash
   docker compose run --rm generator
   ```

2. Check the generated outputs.

   ```text
   generated/jsonschema/ontology.schema.json
   generated/shacl/ontology.shacl.ttl
   ```

## Useful URLs

1. Editor: `http://localhost:8010/`
2. API docs: `http://localhost:8010/docs`
3. Health check: `http://localhost:8010/health`
4. JSON Schema: `http://localhost:8010/schema`
5. Schema model API: `http://localhost:8010/api/schema/model`
6. LinkML YAML API: `http://localhost:8010/api/schema/linkml`
7. RDF/SHACL import API: `http://localhost:8010/api/schema/import`
8. SHACL export: `http://localhost:8010/schema/export/shacl`
9. RDF export: `http://localhost:8010/schema/export/rdf`

## Developer Frontend Workflow

Use this only if you want to work on the React UI outside the Docker production build.

1. Start the FastAPI app on port 8010.

   ```bash
   docker compose up -d app
   ```

2. Open a second terminal.

3. Install frontend dependencies.

   ```bash
   cd frontend
   npm install
   ```

4. Start Vite.

   ```bash
   npm run dev
   ```

5. Open the Vite dev server.

   ```text
   http://localhost:5173/
   ```

Vite proxies API requests to the FastAPI backend on port 8010.

## iPadOS Wrapper

An optional SwiftUI wrapper app is available in:

```text
ipad-wrapper/GeneralOntologyEditor.xcodeproj
```

Open it with Xcode on a Mac, choose a signing team, and run it on an iPad or iPad simulator. On a physical iPad, set the app's server URL to the LAN address of the machine hosting this Docker app, such as `http://192.168.1.25:8010/`.

## Stop The App

1. Stop the running containers.

   ```bash
   docker compose down
   ```

## Project Structure

```text
General-Ontology-Editor/
  backend/          FastAPI application and schema export APIs
  frontend/         React + TypeScript visual ontology editor
  schemas/          LinkML source ontology schema
  scripts/          Artifact generation scripts
  generated/        Generated JSON Schema and SHACL files
  ipad-wrapper/     SwiftUI WKWebView iPadOS wrapper
  docker-compose.yml
```

## Stack

1. FastAPI backend.
2. LinkML schema files.
3. React + TypeScript frontend.
4. React Flow diagram editor.
5. Zustand schema state.
6. Monaco YAML preview.
7. RDFlib RDF and SHACL export helpers.
8. Docker Compose local runtime.

## Design Notes

1. The schema state is the source of truth.
2. React Flow is the visual editor, not the data model.
3. LinkML YAML is generated from schema state.
4. UI layout data should stay separate from LinkML schema data.
5. The seed schema in `schemas/ontology.yaml` is intentionally generic and can be replaced.
