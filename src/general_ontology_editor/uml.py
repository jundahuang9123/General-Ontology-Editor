from __future__ import annotations

from typing import Any

from .exporters import inherited_slots, schema_from_source


def generate_uml(schema_or_path: dict[str, Any] | str) -> str:
    schema = schema_from_source(schema_or_path)
    classes = schema.get('classes', {})
    slots = schema.get('slots', {})
    enums = schema.get('enums', {})

    uml = 'classDiagram\n'
    for name in classes:
        uml += f'  class {name} {{\n'
        for slot_name in inherited_slots(name, schema):
            slot_def = slots.get(slot_name, {})
            slot_range = slot_def.get('range', 'string')
            required = slot_def.get('required', False)
            multivalued = slot_def.get('multivalued', False)
            card = '[1..*]' if required and multivalued else '[1]' if required else '[*]' if multivalued else '[0..1]'
            enum = enums.get(slot_range)
            if enum:
                values = ','.join((enum.get('permissible_values') or {}).keys())
                uml += f'    {slot_name} : {slot_range} {card} [{values}]\n'
            else:
                uml += f'    {slot_name} : {slot_range} {card}\n'
        uml += '  }\n'

    for name, class_def in classes.items():
        parent = class_def.get('is_a')
        if parent in classes:
            uml += f'  {name} --|> {parent}\n'
        for slot_name in inherited_slots(name, schema):
            slot_range = slots.get(slot_name, {}).get('range')
            if slot_range in classes:
                uml += f'  {name} --> {slot_range} : {slot_name}\n'

    return uml
