import json
import re
import unicodedata

def normalize(text):
    text = text.lower()
    text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('utf-8')
    return text.strip()

# Read JSON
with open('arbol_familia.json', 'r', encoding='utf-8') as f:
    arbol = json.load(f)

json_names = set()
def extract_json_names(node):
    name = node.get('name', '')
    if name:
        json_names.add(normalize(name))
    for child in node.get('children', []):
        extract_json_names(child)

extract_json_names(arbol)

# Read MD
with open('BMR.md', 'r', encoding='utf-8') as f:
    md_lines = f.readlines()

md_names = []
missing = []
for line in md_lines:
    m = re.search(r'- \*\*([0-9\.]+)\*\*\s*(.+)', line)
    if m:
        name = m.group(2).strip()
        name = name.replace('**', '')
        # Remove parenthetical notes from name like "(este hizo el testamento)" or " (tía CARMITA)"
        name = re.sub(r'\s*\(.*?\)', '', name)
        # Remove trailing dots
        if name.endswith('.'): name = name[:-1]
        
        md_names.append((m.group(1), name))
        norm_name = normalize(name)
        if norm_name not in json_names:
            # Special case for "Con Cruz del Carmen Figueroa" etc. which are in JSON as union,
            # but in MD as normal lines or spouses.
            missing.append((m.group(1), name))

if not missing:
    print("All good! No missing members found.")
else:
    print(f"Found {len(missing)} potentially missing members:")
    for num, name in missing:
        print(f"{num}: {name}")
