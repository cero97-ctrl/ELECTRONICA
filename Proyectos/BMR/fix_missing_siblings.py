import json

with open('arbol_familia.json', 'r', encoding='utf-8') as f:
    arbol = json.load(f)

with open('BMR.md', 'r', encoding='utf-8') as f:
    md_lines = f.readlines()
    
# Basic parsing just for the 3 missing siblings and their children
def get_node_by_id(target_id):
    import re
    nodes = {}
    for line in md_lines:
        m = re.search(r'- \*\*([0-9\.]+)\*\*\s*(.+)', line)
        if m:
            num = m.group(1).strip()
            if num.endswith('.'): num = num[:-1]
            raw_name = m.group(2).strip()
            name = raw_name.replace('**', '')
            nota = None
            nota_m = re.search(r'\((.*?)\)', name)
            if nota_m:
                nota = nota_m.group(1).strip()
                name = re.sub(r'\s*\(.*?\)', '', name).strip()
            if name.endswith('.'): name = name[:-1]
            node = {"name": name}
            if nota: node["_nota"] = nota
            nodes[num] = node
            
    for num in sorted(nodes.keys()):
        parts = num.split('.')
        parent_num = '.'.join(parts[:-1])
        if parent_num in nodes:
            if 'children' not in nodes[parent_num]:
                nodes[parent_num]['children'] = []
            nodes[parent_num]['children'].append(nodes[num])
    
    return nodes.get(target_id)

fausto = get_node_by_id("1.5.2.3.3")
petra_maria = get_node_by_id("1.5.2.3.7")
jose_tomas = get_node_by_id("1.5.2.3.8")

def find_union_and_add(node, union_name, new_children):
    if node.get('name') == union_name:
        for child in new_children:
            # check if not already there
            if not any(c.get('name') == child['name'] for c in node.get('children', [])):
                node['children'].append(child)
        return True
    for child in node.get('children', []):
        if find_union_and_add(child, union_name, new_children):
            return True
    return False

find_union_and_add(arbol, "Con Lourdes Ramos", [fausto, petra_maria, jose_tomas])

with open('arbol_familia.json', 'w', encoding='utf-8') as f:
    json.dump(arbol, f, indent=2, ensure_ascii=False)
