import json
import re
import unicodedata

def normalize(text):
    text = text.lower()
    text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('utf-8')
    return text.strip()

# Read MD and build nodes
with open('BMR.md', 'r', encoding='utf-8') as f:
    md_lines = f.readlines()

nodes = {}
for line in md_lines:
    m = re.search(r'- \*\*([0-9\.]+)\*\*\s*(.+)', line)
    if m:
        num = m.group(1).strip()
        if num.endswith('.'): num = num[:-1]
        raw_name = m.group(2).strip()
        name = raw_name.replace('**', '')
        
        # Extract nota
        nota = None
        nota_m = re.search(r'\((.*?)\)', name)
        if nota_m:
            nota = nota_m.group(1).strip()
            name = re.sub(r'\s*\(.*?\)', '', name).strip()
            
        if name.endswith('.'): name = name[:-1]
        
        node = {"name": name}
        if nota:
            node["_nota"] = nota
        nodes[num] = node

# Build tree
for num in sorted(nodes.keys()):
    parts = num.split('.')
    parent_num = '.'.join(parts[:-1])
    if parent_num in nodes:
        if 'children' not in nodes[parent_num]:
            nodes[parent_num]['children'] = []
        nodes[parent_num]['children'].append(nodes[num])

with open('arbol_familia.json', 'r', encoding='utf-8') as f:
    arbol = json.load(f)

def find_and_update(node, target_name, new_children):
    if normalize(node.get('name', '')) == normalize(target_name):
        node['children'] = new_children
        return True
    for child in node.get('children', []):
        if find_and_update(child, target_name, new_children):
            return True
    return False

# List of nodes that need their children updated
targets = {
    "1.5.2.2.3": "Ramón", # Actually Ramon is a leaf, but let's check
    "1.5.2.3.3": "Fausto Bravo Ramos",
    "1.5.2.3.7": "Petra María Bravo Ramos",
    "1.5.2.3.1.2": "Olga Guevara Bravo",
    "1.5.2.3.1.3": "Cristóbal Guevara Bravo",
    "1.5.2.3.1.4": "Angélica Guevara Bravo",
    "1.5.2.3.1.4.6": "Nohelis Medina Guevara"
}

for num, name in targets.items():
    if num in nodes and 'children' in nodes[num]:
        find_and_update(arbol, name, nodes[num]['children'])

# Special check for Ramón (1.5.2.2.3) - he might just need to be added to Vicente Bravo Marín (1.5.2.2)
vicente_children = nodes.get("1.5.2.2", {}).get("children", [])
if vicente_children:
    find_and_update(arbol, "Vicente Bravo Marín", vicente_children)

with open('arbol_familia.json', 'w', encoding='utf-8') as f:
    json.dump(arbol, f, indent=2, ensure_ascii=False)

print("Fixed missing subtrees.")
