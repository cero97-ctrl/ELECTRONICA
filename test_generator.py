#!/usr/bin/env python3
"""Test standalone del generador EasyEDA - sin dependencias externas."""
import json
import os

# ====== Copiar las funciones del generador directamente ======
class _IdCounter:
    def __init__(self, start=1):
        self._n = start
    def next(self):
        uid = f"gge{self._n}"
        self._n += 1
        return uid

def _build_pin(pin_num, dot_x, dot_y, body_edge_x, body_edge_y, idc):
    pin_id = idc.next()
    h_len = dot_x - body_edge_x
    rotation = "180" if h_len < 0 else "0"
    config = f"P~show~0~{pin_num}~{dot_x}~{dot_y}~{rotation}~{pin_id}"
    dot_seg = f"{dot_x}~{dot_y}"
    path_seg = f"M {body_edge_x} {body_edge_y} h {h_len}~#880000"
    name_seg = f"0~{dot_x}~{dot_y + 3}~0~{pin_num}~start~~"
    num_seg = f"0~{dot_x}~{dot_y - 4}~0~{pin_num}~end~~"
    return f"{config}^^{dot_seg}^^{path_seg}^^{name_seg}^^{num_seg}^^^^"

def _build_resistor_lib(designator, value, lcsc, cx, cy, idc):
    lib_id = idc.next()
    attrs = f"package`{lcsc}`nameAlias`Value`Value`{value}`spicePre`R`spiceSymbolName`Resistor`"
    header = f"LIB~{cx}~{cy}~{attrs}~~0~{lib_id}"
    t_name = f"T~N~{cx - 6}~{cy - 15}~0~#000080~Arial~~~~~comment~{value}~1~start~{idc.next()}"
    t_prefix = f"T~P~{cx - 6}~{cy - 25}~0~#000080~Arial~~~~~comment~{designator}~1~start~{idc.next()}"
    body = f"R~{cx - 15}~{cy - 5}~0~0~30~10~#A00000~1~0~none~{idc.next()}"
    pin1 = _build_pin(1, cx - 30, cy, cx - 15, cy, idc)
    pin2 = _build_pin(2, cx + 30, cy, cx + 15, cy, idc)
    return "#@$".join([header, t_name, t_prefix, body, pin1, pin2])

_PIN_OFFSETS = {"1": (-30, 0), "2": (30, 0)}

# ====== Test ======
test_netlist = {
    "components": [
        {"id": "R1", "type": "Resistor", "value": "5", "lcsc_part": "C17414", "x": 100, "y": 300},
        {"id": "R2", "type": "Resistor", "value": "20", "lcsc_part": "C17414", "x": 400, "y": 400},
        {"id": "R3", "type": "Resistor", "value": "20", "lcsc_part": "C17414", "x": 400, "y": 200},
        {"id": "R4", "type": "Resistor", "value": "15", "lcsc_part": "C17414", "x": 100, "y": 100},
        {"id": "R5", "type": "Resistor", "value": "2.5", "lcsc_part": "C17414", "x": 800, "y": 0},
    ],
    "connections": [
        {"net_name": "Net_1", "pins": ["R1-1", "R4-1"]},
        {"net_name": "Net_2", "pins": ["R1-2", "R2-1", "R3-1"]},
        {"net_name": "Net_3", "pins": ["R2-2", "R3-2", "R4-2", "R5-1"]},
        {"net_name": "Net_4", "pins": ["R5-2"]},
        {"net_name": "GND", "pins": ["R5-2"]},
    ]
}

idc = _IdCounter()
shapes = []
pin_positions = {}

for comp in test_netlist["components"]:
    cx, cy = int(comp["x"]), int(comp["y"])
    lib_str = _build_resistor_lib(comp["id"], comp["value"], comp["lcsc_part"], cx, cy, idc)
    shapes.append(lib_str)
    for pin_num, (dx, dy) in _PIN_OFFSETS.items():
        pin_positions[f"{comp['id']}-{pin_num}"] = (cx + dx, cy + dy)

junction_points = {}
for conn in test_netlist["connections"]:
    points = [(pin_positions[p]) for p in conn["pins"] if p in pin_positions]
    if len(points) > 1:
        hx, hy = points[0]
        junction_points[(hx, hy)] = junction_points.get((hx, hy), 0) + len(points) - 1
        for (px, py) in points[1:]:
            shapes.append(f"W~{hx} {hy} {px} {py}~#008800~1~0~none~{idc.next()}")

for conn in test_netlist["connections"]:
    net_name = conn.get("net_name", "")
    first_pin = next((p for p in conn["pins"] if p in pin_positions), None)
    if first_pin and net_name:
        nx, ny = pin_positions[first_pin]
        shapes.append(f"N~{nx}~{ny - 12}~0~#0000FF~{net_name}~{idc.next()}~start~{nx + 2}~{ny - 12}~~")

for (jx, jy), count in junction_points.items():
    if count >= 2:
        shapes.append(f"J~{jx}~{jy}~2.5~#CC0000~{idc.next()}")

result = {
    "head": "1~6.5.54~",
    "canvas": "CA~1200~1200~#FFFFFF~yes~#CCCCCC~10~1200~1200~line~10~pixel~5~400~300",
    "shape": shapes,
}

out = os.path.join(os.path.dirname(__file__), "Agente_EDA", "circuito_prueba", "circuito_prueba_easyeda.json")
with open(out, 'w', encoding='utf-8') as f:
    json.dump(result, f, indent=4, ensure_ascii=False)

# Verificación
print("=== Verificación del JSON EasyEDA ===")
print(f"head es string: {'✓' if isinstance(result['head'], str) else '✗'}")
print(f"Total shape[]: {len(shapes)}")
lib_c = sum(1 for s in shapes if s.startswith('LIB~'))
wire_c = sum(1 for s in shapes if s.startswith('W~'))
nl_c = sum(1 for s in shapes if s.startswith('N~'))
j_c = sum(1 for s in shapes if s.startswith('J~'))
print(f"  LIB: {lib_c} | W: {wire_c} | N: {nl_c} | J: {j_c}")
print(f"Sin BOM: {'✓' if 'BOM' not in result else '✗'}")
print(f"Sin BBox: {'✓' if 'BBox' not in result else '✗'}")
print(f"Sin docType wrapper: {'✓' if 'docType' not in result else '✗'}")
print(f"\nPrimer LIB (truncado):\n{shapes[0][:150]}...")
print(f"\nPrimer Wire:\n{next(s for s in shapes if s.startswith('W~'))}")
print(f"\n✓ JSON guardado en: {out}")
