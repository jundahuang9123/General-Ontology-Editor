import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  type Connection,
  type NodeMouseHandler,
} from '@xyflow/react';
import Editor from '@monaco-editor/react';
import '@xyflow/react/dist/style.css';
import { ClassNode } from './components/ClassNode';
import { Inspector } from './components/Inspector';
import { Toolbar, type ExportKind } from './components/Toolbar';
import { schemaToFlow } from './lib/schema';
import { useEditorStore } from './store';
import type { SchemaModel } from './types';
import './styles.css';

const nodeTypes = { classNode: ClassNode };

type ImportMode = 'override' | 'merge';

const MIN_YAML_WIDTH = 260;
const MAX_YAML_WIDTH = 640;

type EditorCanvasProps = {
  yamlVisible: boolean;
};

function EditorCanvas({ yamlVisible }: EditorCanvasProps) {
  const workspaceRef = useRef<HTMLDivElement>(null);
  const schema = useEditorStore((state) => state.schema);
  const positions = useEditorStore((state) => state.positions);
  const selected = useEditorStore((state) => state.selected);
  const setSelected = useEditorStore((state) => state.setSelected);
  const onNodesChange = useEditorStore((state) => state.onNodesChange);
  const connectClasses = useEditorStore((state) => state.connectClasses);
  const yaml = useEditorStore((state) => state.yaml());
  const flow = useMemo(() => schemaToFlow(schema, positions), [schema, positions]);
  const [yamlWidth, setYamlWidth] = useState(() => {
    const storedWidth = Number(window.localStorage.getItem('yamlPanelWidth'));
    return Number.isFinite(storedWidth) ? Math.min(MAX_YAML_WIDTH, Math.max(MIN_YAML_WIDTH, storedWidth)) : 380;
  });
  const [resizingYaml, setResizingYaml] = useState(false);

  const onNodeClick: NodeMouseHandler = useCallback(
    (_event, node) => {
      setSelected({ kind: 'class', id: node.id });
    },
    [setSelected],
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      connectClasses(connection);
    },
    [connectClasses],
  );

  useEffect(() => {
    window.localStorage.setItem('yamlPanelWidth', String(yamlWidth));
  }, [yamlWidth]);

  useEffect(() => {
    if (!resizingYaml) return;

    function onPointerMove(event: PointerEvent) {
      const bounds = workspaceRef.current?.getBoundingClientRect();
      if (!bounds) return;

      const nextWidth = event.clientX - bounds.left;
      setYamlWidth(Math.min(MAX_YAML_WIDTH, Math.max(MIN_YAML_WIDTH, nextWidth)));
    }

    function onPointerUp() {
      setResizingYaml(false);
    }

    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
    return () => {
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
    };
  }, [resizingYaml]);

  const workspaceStyle = { '--yaml-width': `${yamlWidth}px` } as CSSProperties;

  return (
    <div
      className={`workspace ${yamlVisible ? '' : 'workspace--yaml-hidden'} ${resizingYaml ? 'workspace--resizing' : ''}`}
      ref={workspaceRef}
      style={workspaceStyle}
    >
      {yamlVisible ? (
        <section className="yaml-panel">
          <div className="yaml-panel__header">
            <h2>Live LinkML YAML</h2>
            <span>{selected ? `${selected.kind}: ${selected.id}` : 'Schema output'}</span>
          </div>
          <Editor
            height="100%"
            language="yaml"
            theme="vs-dark"
            value={yaml}
            options={{
              readOnly: true,
              minimap: { enabled: false },
              fontSize: 12,
              wordWrap: 'on',
              scrollBeyondLastLine: false,
            }}
          />
          <div
            aria-label="Resize live YAML panel"
            aria-orientation="vertical"
            className="yaml-panel__resizer"
            onKeyDown={(event) => {
              if (event.key === 'ArrowLeft') {
                event.preventDefault();
                setYamlWidth((width) => Math.max(MIN_YAML_WIDTH, width - 24));
              }
              if (event.key === 'ArrowRight') {
                event.preventDefault();
                setYamlWidth((width) => Math.min(MAX_YAML_WIDTH, width + 24));
              }
            }}
            onPointerDown={(event) => {
              event.preventDefault();
              setResizingYaml(true);
            }}
            role="separator"
            tabIndex={0}
            title="Drag to resize live YAML"
          />
        </section>
      ) : null}
      <section className="canvas">
        <ReactFlow
          nodes={flow.nodes}
          edges={flow.edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          onPaneClick={() => setSelected(null)}
          nodesDraggable
          fitView
        >
          <Background color="#d4dbe8" gap={18} />
          <Controls />
          <MiniMap pannable zoomable />
        </ReactFlow>
      </section>
      <Inspector />
    </div>
  );
}

export default function App() {
  const loadSchema = useEditorStore((state) => state.loadSchema);
  const mergeSchema = useEditorStore((state) => state.mergeSchema);
  const yaml = useEditorStore((state) => state.yaml);
  const [status, setStatus] = useState('Loading schema...');
  const [yamlVisible, setYamlVisible] = useState(true);
  const [pendingUpload, setPendingUpload] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    fetch('/api/schema/model')
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((schema) => {
        loadSchema(schema);
        setStatus('Loaded');
      })
      .catch((err) => {
        setStatus(`Load failed: ${err.message}`);
      });
  }, [loadSchema]);

  const saveSchema = useCallback(async () => {
    setStatus('Saving...');
    const res = await fetch('/api/schema/linkml', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ yaml: yaml() }),
    });
    if (!res.ok) {
      const detail = await res.text();
      setStatus(`Save failed: ${detail}`);
      return;
    }
    setStatus('Saved to schemas/ontology.yaml');
  }, [yaml]);

  const exportSchema = useCallback(async (kind: ExportKind) => {
    const label = kind === 'rdf' ? 'RDF' : 'SHACL';
    setStatus(`Exporting ${label}...`);
    const res = await fetch(`/schema/export/${kind}`);
    if (!res.ok) {
      const detail = await res.text();
      setStatus(`${label} export failed: ${detail}`);
      return;
    }

    const text = await res.text();
    const blob = new Blob([text], { type: 'text/turtle' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = kind === 'rdf' ? 'ontology.rdf.ttl' : 'ontology.shacl.ttl';
    link.click();
    URL.revokeObjectURL(url);
    setStatus(`${label} exported`);
  }, []);

  const selectImportFile = useCallback((file: File) => {
    setPendingUpload(file);
  }, []);

  const importSchema = useCallback(
    async (mode: ImportMode) => {
      if (!pendingUpload) return;

      setImporting(true);
      setStatus(`Importing ${pendingUpload.name}...`);
      const formData = new FormData();
      formData.append('file', pendingUpload);

      try {
        const res = await fetch('/api/schema/import', {
          method: 'POST',
          body: formData,
        });
        if (!res.ok) {
          const detail = await res.text();
          setStatus(`Import failed: ${detail}`);
          return;
        }

        const schema = (await res.json()) as SchemaModel;
        if (mode === 'merge') {
          mergeSchema(schema);
          setStatus(`Merged ${pendingUpload.name} into the current diagram.`);
        } else {
          loadSchema(schema);
          setStatus(`Imported ${pendingUpload.name}. Review the diagram, then Save to persist YAML.`);
        }
        setPendingUpload(null);
      } catch (err) {
        setStatus(`Import failed: ${err instanceof Error ? err.message : 'unknown error'}`);
      } finally {
        setImporting(false);
      }
    },
    [loadSchema, mergeSchema, pendingUpload],
  );

  const provider = useMemo(
    () => (
      <ReactFlowProvider>
        <Toolbar
          onExport={exportSchema}
          onImport={selectImportFile}
          onSave={saveSchema}
          onToggleYaml={() => setYamlVisible((visible) => !visible)}
          status={status}
          yamlVisible={yamlVisible}
        />
        <EditorCanvas yamlVisible={yamlVisible} />
        {pendingUpload ? (
          <div className="modal-backdrop" role="presentation">
            <section aria-labelledby="import-modal-title" aria-modal="true" className="import-modal" role="dialog">
              <div>
                <h2 id="import-modal-title">Import {pendingUpload.name}</h2>
                <p>Replace the current diagram, or merge this ontology into what is already open.</p>
              </div>
              <div className="import-modal__actions">
                <button disabled={importing} onClick={() => setPendingUpload(null)} type="button">
                  Cancel
                </button>
                <button disabled={importing} onClick={() => void importSchema('merge')} type="button">
                  Merge
                </button>
                <button className="primary" disabled={importing} onClick={() => void importSchema('override')} type="button">
                  Override
                </button>
              </div>
            </section>
          </div>
        ) : null}
      </ReactFlowProvider>
    ),
    [exportSchema, importSchema, importing, pendingUpload, saveSchema, selectImportFile, status, yamlVisible],
  );

  return provider;
}
