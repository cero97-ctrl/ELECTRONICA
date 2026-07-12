import json

with open('arbol_familia.json', 'r', encoding='utf-8') as f:
    arbol = json.load(f)

# Hardcode candida's tree based on the numbering logic we had before
candida_children = [
  {"name": "Jesus Manuel"},
  {
    "name": "Jorge",
    "children": [
      {"name": "Jorge"},
      {"name": "Edward"},
      {"name": "Lourdes"},
      {"name": "Johan"},
      {"name": "Jhon"}
    ]
  },
  {"name": "Silvio"},
  {"name": "Franklin"}
]

def find_and_update(node, target_name, new_children):
    if node.get('name') == target_name:
        node['children'] = new_children
        return True
    for child in node.get('children', []):
        if find_and_update(child, target_name, new_children):
            return True
    return False

find_and_update(arbol, "Cándida Bravo Ramos", candida_children)

with open('arbol_familia.json', 'w', encoding='utf-8') as f:
    json.dump(arbol, f, indent=2, ensure_ascii=False)

print("Updated Candida")
