import yaml from 'js-yaml';
import { emptySchema, normalizeSchema, schemaToRdfTurtle, schemaToShaclTurtle } from './schema';
import type { SchemaModel } from '../types';
import type { ExportKind } from '../components/Toolbar';

const STORAGE_KEY = 'generalOntologyEditor.schema';

type NativeExportPayload = {
  action: 'exportText';
  filename: string;
  type: string;
  text: string;
};

declare global {
  interface Window {
    GeneralOntologyEditor?: {
      exportText?: (filename: string, type: string, text: string) => void;
    };
    webkit?: {
      messageHandlers?: {
        generalOntologyEditor?: {
          postMessage: (payload: NativeExportPayload) => void;
        };
      };
    };
  }
}

type LoadResult = {
  schema: SchemaModel;
  message: string;
};

type SaveResult = {
  message: string;
};

export function downloadText(text: string, filename: string, type: string) {
  if (exportWithNativePicker(text, filename, type)) {
    return;
  }

  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function exportWithNativePicker(text: string, filename: string, type: string) {
  try {
    const androidExporter = window.GeneralOntologyEditor?.exportText;
    if (androidExporter) {
      androidExporter(filename, type, text);
      return true;
    }

    const iosHandler = window.webkit?.messageHandlers?.generalOntologyEditor;
    if (iosHandler) {
      iosHandler.postMessage({ action: 'exportText', filename, type, text });
      return true;
    }
  } catch (error) {
    console.warn('Native export is unavailable; falling back to browser download.', error);
  }

  return false;
}

export async function loadSchemaModel(): Promise<LoadResult> {
  if (!isBundledRuntime()) {
    try {
      const res = await fetch('/api/schema/model');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return {
        schema: normalizeSchema((await res.json()) as SchemaModel),
        message: 'Loaded',
      };
    } catch (error) {
      const local = loadLocalSchema();
      if (local) {
        return {
          schema: local,
          message: `Server unavailable; loaded device copy (${errorMessage(error)}).`,
        };
      }
      return {
        schema: emptySchema(),
        message: `Server unavailable; started a local schema (${errorMessage(error)}).`,
      };
    }
  }

  const local = loadLocalSchema();
  return {
    schema: local ?? emptySchema(),
    message: local ? 'Loaded local device copy' : 'Started bundled local editor',
  };
}

export async function saveSchemaYaml(yamlText: string): Promise<SaveResult> {
  if (!isBundledRuntime()) {
    try {
      const res = await fetch('/api/schema/linkml', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ yaml: yamlText }),
      });
      if (!res.ok) throw new Error(await res.text());
      saveLocalSchema(parseLinkmlSchema(yamlText));
      return { message: 'Saved to schemas/ontology.yaml' };
    } catch (error) {
      saveLocalSchema(parseLinkmlSchema(yamlText));
      return { message: `Server save failed; saved on this device (${errorMessage(error)}).` };
    }
  }

  saveLocalSchema(parseLinkmlSchema(yamlText));
  return { message: 'Saved on this device' };
}

export async function importSchemaFile(file: File): Promise<SchemaModel> {
  if (!isBundledRuntime()) {
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch('/api/schema/import', {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) throw new Error(await res.text());
      return normalizeSchema((await res.json()) as SchemaModel);
    } catch (error) {
      if (!isLinkmlFile(file.name)) {
        throw new Error(`Server import failed: ${errorMessage(error)}`);
      }
    }
  }

  if (!isLinkmlFile(file.name)) {
    throw new Error('Bundled mode can import LinkML YAML/JSON. RDF, OWL, and SHACL import still need the backend server.');
  }

  const text = await file.text();
  return parseLinkmlSchema(text);
}

export function exportSchema(schema: SchemaModel, kind: ExportKind) {
  const text = kind === 'rdf' ? schemaToRdfTurtle(schema) : schemaToShaclTurtle(schema);
  downloadText(text, kind === 'rdf' ? 'ontology.rdf.ttl' : 'ontology.shacl.ttl', 'text/turtle');
}

function isBundledRuntime() {
  return (
    window.location.protocol === 'file:' ||
    window.location.protocol === 'goe:' ||
    window.location.hostname === 'general-ontology-editor.local'
  );
}

function loadLocalSchema() {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;

  try {
    return normalizeSchema(JSON.parse(raw) as SchemaModel);
  } catch {
    window.localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

function saveLocalSchema(schema: SchemaModel) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(normalizeSchema(schema)));
}

function parseLinkmlSchema(text: string) {
  const parsed = yaml.load(text);
  if (!isSchemaMapping(parsed)) {
    throw new Error('Schema file must be a LinkML YAML/JSON mapping with classes and slots.');
  }

  return normalizeSchema(parsed);
}

function isSchemaMapping(value: unknown): value is SchemaModel {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const record = value as Record<string, unknown>;
  return isObjectRecord(record.classes) && isObjectRecord(record.slots);
}

function isObjectRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value));
}

function isLinkmlFile(name: string) {
  return /\.(ya?ml|json)$/i.test(name);
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'unknown error';
}
