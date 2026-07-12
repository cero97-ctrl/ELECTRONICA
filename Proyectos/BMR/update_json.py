import json
import re

with open('BMR.md', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Extract nodes
nodes = {}
for line in lines:
    m = re.search(r'- \*\*([0-9\.]+)\*\*\s*(.+)', line)
    if m:
        num = m.group(1).strip()
        if num.endswith('.'): num = num[:-1]
        name = m.group(2).strip()
        # Clean name from bold etc if any
        name = name.replace('**', '')
        nodes[num] = {"name": name}

# Build tree from nodes
tree = {}
for num in sorted(nodes.keys()):
    parts = num.split('.')
    parent_num = '.'.join(parts[:-1])
    if parent_num in nodes:
        if 'children' not in nodes[parent_num]:
            nodes[parent_num]['children'] = []
        nodes[parent_num]['children'].append(nodes[num])
        
# Now we load arbol_familia.json
with open('arbol_familia.json', 'r', encoding='utf-8') as f:
    arbol = json.load(f)
    
# We want to replace the node for Maria Eugenia in arbol_familia.json
# Wait, Maria Eugenia is 1.5.2.3.2. Let's find it in arbol.
def find_and_update(node, target_name_prefix, new_children):
    if node.get('name', '').startswith(target_name_prefix):
        node['children'] = new_children
        return True
    for child in node.get('children', []):
        if find_and_update(child, target_name_prefix, new_children):
            return True
    return False

# Maria Eugenia
maria = nodes.get("1.5.2.3.2")
if maria and 'children' in maria:
    find_and_update(arbol, "María Eugenia Bravo", maria['children'])

# Petra Bravo 1.5.2.3.4
petra = nodes.get("1.5.2.3.4")
if petra and 'children' in petra:
    find_and_update(arbol, "Petra Bravo Ramos", petra['children'])

# Candida Bravo 1.5.2.3.5
candida = nodes.get("1.5.2.3.5")
if candida and 'children' in candida:
    find_and_update(arbol, "Candida Bravo Ramos", candida['children'])

# Natividad 1.5.2.3.6
natividad = nodes.get("1.5.2.3.6")
if natividad and 'children' in natividad:
    find_and_update(arbol, "Natividad del Valle Bravo Ramos", natividad['children'])

# Petra Maria 1.5.2.3.7
petram = nodes.get("1.5.2.3.7")
if petram and 'children' in petram:
    find_and_update(arbol, "Petra María Bravo Ramos", petram['children'])
    
# Fausto 1.5.2.3.3
fausto = nodes.get("1.5.2.3.3")
if fausto and 'children' in fausto:
    find_and_update(arbol, "Fausto Bravo Ramos", fausto['children'])
    
# Jose Tomas 1.5.2.3.8
jt = nodes.get("1.5.2.3.8")
if jt and 'children' in jt:
    find_and_update(arbol, "José Tomás Bravo Ramos", jt['children'])
    
with open('arbol_familia.json', 'w', encoding='utf-8') as f:
    json.dump(arbol, f, indent=2, ensure_ascii=False)

print("Updated arbol_familia.json")
