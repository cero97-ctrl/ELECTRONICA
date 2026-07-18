import json
import re

with open('BMR.md', 'r', encoding='utf-8') as f:
    lines = f.readlines()

nodes = {}
for line in lines:
    m = re.search(r'^-\s*(?:\*\*)?([0-9\.]+)(?:\*\*)?\s*(.+)', line)
    if m:
        num = m.group(1).strip()
        if num.endswith('.'): num = num[:-1]
        name = m.group(2).strip()
        name = name.replace('**', '')
        nodes[num] = {"name": name}

for num in sorted(nodes.keys(), key=lambda x: [int(p) for p in x.split('.')]):
    parts = num.split('.')
    parent_num = '.'.join(parts[:-1])
    if parent_num in nodes:
        if 'children' not in nodes[parent_num]:
            nodes[parent_num]['children'] = []
        nodes[parent_num]['children'].append(nodes[num])

with open('arbol_familia.json', 'r', encoding='utf-8') as f:
    arbol = json.load(f)

def find_and_update(node, target_name_prefix, new_children):
    if node.get('name', '').startswith(target_name_prefix):
        node['children'] = new_children
        return True
    for child in node.get('children', []):
        if find_and_update(child, target_name_prefix, new_children):
            return True
    return False

updates = [
    ("1.5.1", "Andrés Marín Rojas"),
    ("1.5.2.1", "Carmen Marín"),
    ("1.5.2.2", "Vicente Bravo Marín"),
    ("1.5.2.4", "Plácida Bravo Marín"),
    ("1.5.2.5", "Elena Bravo Marín"),
    ("1.5.2.3.1.1", "Luisa Inés Guevara Bravo"),
    ("1.5.2.3.1.2", "Olga Guevara Bravo"),
    ("1.5.2.3.1.3", "Cristóbal Guevara Bravo"),
    ("1.5.2.3.1.4", "Angélica Guevara Bravo"),
    ("1.5.2.3.2", "María Eugenia Bravo"),
    ("1.5.2.3.4", "Petra Bravo Ramos"),
    ("1.5.2.3.5", "Cándida Bravo Ramos"),
    ("1.5.2.3.5", "Candida Bravo Ramos"),
    ("1.5.2.3.6", "Natividad del Valle Bravo Ramos"),
    ("1.5.2.3.7", "Petra María Bravo Ramos"),
    ("1.5.2.3.8", "José Tomás Bravo Ramos")
]

for num, name_prefix in updates:
    if num in nodes and 'children' in nodes[num]:
        found = find_and_update(arbol, name_prefix, nodes[num]['children'])
        if not found:
            print(f"Not found in JSON: {name_prefix}")

with open('arbol_familia.json', 'w', encoding='utf-8') as f:
    json.dump(arbol, f, indent=2, ensure_ascii=False)

print("arbol_familia.json updated successfully.")
