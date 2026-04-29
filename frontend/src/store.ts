import { create } from 'zustand';
import type { Connection, NodeChange } from '@xyflow/react';
import type { SchemaModel, SelectedItem } from './types';
import { emptySchema, mergeSchemas, normalizeSchema, serializeOntologySchema } from './lib/schema';

type EditorState = {
  schema: SchemaModel;
  positions: Record<string, { x: number; y: number }>;
  minimizedClasses: Record<string, boolean>;
  selected: SelectedItem;
  loadSchema: (schema: SchemaModel) => void;
  mergeSchema: (schema: SchemaModel) => void;
  setSelected: (selected: SelectedItem) => void;
  updateSchemaMetadata: (updates: Partial<Pick<SchemaModel, 'id' | 'name' | 'title' | 'default_prefix' | 'default_range' | 'prefixes' | 'imports'>>) => void;
  toggleClassMinimized: (name: string) => void;
  onNodesChange: (changes: NodeChange[]) => void;
  connectClasses: (connection: Connection) => void;
  addClass: () => void;
  updateClass: (oldName: string, updates: { name: string; description?: string; is_a?: string }) => void;
  deleteClass: (name: string) => void;
  addSlot: (className: string) => void;
  updateSlot: (oldName: string, updates: { name: string; range: string; required: boolean; multivalued: boolean }) => void;
  removeSlotFromClass: (className: string, slotName: string) => void;
  addEnum: () => void;
  updateEnum: (oldName: string, name: string, values: string[]) => void;
  deleteEnum: (name: string) => void;
  yaml: () => string;
};

function uniqueName(base: string, existing: string[]) {
  if (!existing.includes(base)) return base;
  let index = 2;
  while (existing.includes(`${base}${index}`)) index += 1;
  return `${base}${index}`;
}

export const useEditorStore = create<EditorState>((set, get) => ({
  schema: emptySchema(),
  positions: {},
  minimizedClasses: {},
  selected: null,

  loadSchema: (schema) => set({ schema: normalizeSchema(schema), positions: {}, minimizedClasses: {}, selected: null }),
  mergeSchema: (schema) => set({ schema: mergeSchemas(get().schema, schema), selected: null }),
  setSelected: (selected) => set({ selected }),
  updateSchemaMetadata: (updates) => {
    const schema = structuredClone(get().schema);
    set({
      schema: {
        ...schema,
        ...updates,
        prefixes: updates.prefixes ?? schema.prefixes,
        imports: updates.imports ?? schema.imports,
      },
    });
  },
  toggleClassMinimized: (name) =>
    set({ minimizedClasses: { ...get().minimizedClasses, [name]: !get().minimizedClasses[name] } }),

  onNodesChange: (changes) => {
    const positions = { ...get().positions };
    let didMove = false;

    changes.forEach((change) => {
      if (change.type === 'position' && change.position) {
        positions[change.id] = change.position;
        didMove = true;
      }
    });

    if (didMove) {
      set({ positions });
    }
  },

  connectClasses: (connection) => {
    if (!connection.source || !connection.target || connection.source === connection.target) return;
    const schema = structuredClone(get().schema);
    const source = schema.classes[connection.source];
    if (!source) return;
    source.is_a = connection.target;
    set({ schema, selected: { kind: 'class', id: connection.source } });
  },

  addClass: () => {
    const schema = structuredClone(get().schema);
    const name = uniqueName('OntologyClass', Object.keys(schema.classes));
    schema.classes[name] = { slots: [] };
    set({
      schema,
      positions: { ...get().positions, [name]: { x: 120, y: 120 } },
      selected: { kind: 'class', id: name },
    });
  },

  updateClass: (oldName, updates) => {
    const schema = structuredClone(get().schema);
    const requestedName = updates.name.trim() || oldName;
    const nextName =
      requestedName === oldName
        ? oldName
        : uniqueName(
            requestedName,
            Object.keys(schema.classes).filter((name) => name !== oldName),
          );
    const classDef = schema.classes[oldName];
    if (!classDef) return;

    classDef.description = updates.description || undefined;
    classDef.is_a = updates.is_a || undefined;

    if (nextName !== oldName) {
      schema.classes[nextName] = classDef;
      delete schema.classes[oldName];
      Object.values(schema.classes).forEach((item) => {
        if (item.is_a === oldName) item.is_a = nextName;
      });
      Object.values(schema.slots).forEach((slot) => {
        if (slot.range === oldName) slot.range = nextName;
      });
      const positions = { ...get().positions, [nextName]: get().positions[oldName] ?? { x: 120, y: 120 } };
      delete positions[oldName];
      const minimizedClasses = { ...get().minimizedClasses, [nextName]: get().minimizedClasses[oldName] };
      delete minimizedClasses[oldName];
      set({ schema, positions, minimizedClasses, selected: { kind: 'class', id: nextName } });
      return;
    }

    set({ schema });
  },

  deleteClass: (name) => {
    const schema = structuredClone(get().schema);
    delete schema.classes[name];
    Object.values(schema.classes).forEach((item) => {
      if (item.is_a === name) delete item.is_a;
    });
    Object.values(schema.slots).forEach((slot) => {
      if (slot.range === name) slot.range = 'string';
    });
    const positions = { ...get().positions };
    delete positions[name];
    const minimizedClasses = { ...get().minimizedClasses };
    delete minimizedClasses[name];
    set({ schema, positions, minimizedClasses, selected: null });
  },

  addSlot: (className) => {
    const schema = structuredClone(get().schema);
    const slotName = uniqueName('new_property', Object.keys(schema.slots));
    schema.slots[slotName] = { range: 'string' };
    schema.classes[className].slots = [...(schema.classes[className].slots ?? []), slotName];
    set({ schema, selected: { kind: 'slot', id: slotName, classId: className } });
  },

  updateSlot: (oldName, updates) => {
    const schema = structuredClone(get().schema);
    const requestedName = updates.name.trim() || oldName;
    const nextName =
      requestedName === oldName
        ? oldName
        : uniqueName(
            requestedName,
            Object.keys(schema.slots).filter((name) => name !== oldName),
          );
    const slot = schema.slots[oldName];
    if (!slot) return;
    slot.range = updates.range || 'string';
    slot.required = updates.required || undefined;
    slot.multivalued = updates.multivalued || undefined;

    if (nextName !== oldName) {
      schema.slots[nextName] = slot;
      delete schema.slots[oldName];
      Object.values(schema.classes).forEach((classDef) => {
        classDef.slots = (classDef.slots ?? []).map((slotName) => (slotName === oldName ? nextName : slotName));
      });
      set({ schema, selected: { kind: 'slot', id: nextName } });
      return;
    }

    set({ schema });
  },

  removeSlotFromClass: (className, slotName) => {
    const schema = structuredClone(get().schema);
    const classDef = schema.classes[className];
    if (!classDef) return;
    classDef.slots = (classDef.slots ?? []).filter((item) => item !== slotName);
    const stillUsed = Object.values(schema.classes).some((item) => (item.slots ?? []).includes(slotName));
    if (!stillUsed) delete schema.slots[slotName];
    set({ schema, selected: { kind: 'class', id: className } });
  },

  addEnum: () => {
    const schema = structuredClone(get().schema);
    const name = uniqueName('NewEnum', Object.keys(schema.enums));
    schema.enums[name] = { permissible_values: [] };
    set({ schema, selected: { kind: 'enum', id: name } });
  },

  updateEnum: (oldName, name, values) => {
    const schema = structuredClone(get().schema);
    const requestedName = name.trim() || oldName;
    const nextName =
      requestedName === oldName
        ? oldName
        : uniqueName(
            requestedName,
            Object.keys(schema.enums).filter((enumName) => enumName !== oldName),
          );
    const enumDef = { permissible_values: values.filter(Boolean) };
    schema.enums[nextName] = enumDef;
    if (nextName !== oldName) {
      delete schema.enums[oldName];
      Object.values(schema.slots).forEach((slot) => {
        if (slot.range === oldName) slot.range = nextName;
      });
    }
    set({ schema, selected: { kind: 'enum', id: nextName } });
  },

  deleteEnum: (name) => {
    const schema = structuredClone(get().schema);
    delete schema.enums[name];
    Object.values(schema.slots).forEach((slot) => {
      if (slot.range === name) slot.range = 'string';
    });
    set({ schema, selected: null });
  },

  yaml: () => serializeOntologySchema(get().schema),
}));
