#!/usr/bin/env python3
"""
generar_kicad_sch.py — Generador de esquemáticos KiCAD 8.0.9 (Layer 3: Execution)

Toma como entrada el JSON generado por `extraer_netlist_imagen.py` y construye
un archivo `.kicad_sch` válido usando formato S-Expression.

Uso:
    python3 execution/generar_kicad_sch.py --json .tmp/analisis_netlist.json --output docs/KICAD/esquematico.kicad_sch
"""

import argparse
import json
import sys
import uuid
from pathlib import Path
from datetime import datetime

# Mapeo de tipos simplificados a símbolos de KiCAD 8 de la librería "Device"
TYPE_MAP = {
    "R": "Device:R",
    "C": "Device:C",
    "CP": "Device:C_Polarized",
    "L": "Device:L",
    "D": "Device:D",
    "LED": "Device:LED",
    "Q_NPN_BCE": "Device:Q_NPN_BCE",
    "Q_PNP_BCE": "Device:Q_PNP_BCE",
    "Battery": "Device:Battery",
    "GND": "power:GND",
    "VCC": "power:VCC",
    "IC_555": "Timer:NE555P",
    "555_Timer": "Timer:NE555P",
}

def generate_uuid() -> str:
    """Genera un UUID válido para nodos KiCAD."""
    return str(uuid.uuid4())

def get_symbol_lib_id(comp_type: str) -> str:
    return TYPE_MAP.get(comp_type, "Device:R") # Fallback a resistor

def extract_symbol_from_lib(lib_id: str) -> str:
    """Extrae el bloque S-Expression completo de un símbolo desde la librería del sistema."""
    if ":" not in lib_id:
        return f'    (symbol "{lib_id}" (pin_names (offset 1.016)) (in_bom yes) (on_board yes))'
        
    lib_name, part_name = lib_id.split(":", 1)
    lib_path = Path(f"/usr/share/kicad/symbols/{lib_name}.kicad_sym")
    
    if not lib_path.exists():
        return f'    (symbol "{lib_id}" (pin_names (offset 1.016)) (in_bom yes) (on_board yes))'
        
    try:
        with open(lib_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        start_str = f'(symbol "{part_name}"'
        start_idx = content.find(start_str)
        if start_idx == -1:
            return f'    (symbol "{lib_id}" (pin_names (offset 1.016)) (in_bom yes) (on_board yes))'
            
        depth = 0
        end_idx = -1
        in_string = False
        escape = False
        
        for i in range(start_idx, len(content)):
            char = content[i]
            if escape:
                escape = False
                continue
            if char == '\\':
                escape = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if not in_string:
                if char == '(':
                    depth += 1
                elif char == ')':
                    depth -= 1
                    if depth == 0:
                        end_idx = i + 1
                        break
                        
        if end_idx != -1:
            sym_block = content[start_idx:end_idx]
            sym_block = sym_block.replace(start_str, f'(symbol "{lib_id}"', 1)
            
            lines = sym_block.split("\n")
            first_line_indent = len(lines[0]) - len(lines[0].lstrip())
            indented = []
            for line in lines:
                if line.startswith(" " * first_line_indent):
                    stripped = line[first_line_indent:]
                else:
                    stripped = line.lstrip()
                indented.append("    " + stripped)
            return "\n".join(indented)
    except Exception:
        pass
        
    return f'    (symbol "{lib_id}" (pin_names (offset 1.016)) (in_bom yes) (on_board yes))'

def generate_kicad_sch(netlist: dict, output_file: Path) -> dict:
    try:
        components = netlist.get("components", [])
        connections = netlist.get("connections", [])
        
        # Iniciar S-Expression para KiCAD 8
        lines = []
        lines.append(f'(kicad_sch (version 20231120) (generator "Antigravity_Netlist_Gen")')
        lines.append(f'  (uuid "{generate_uuid()}")')
        lines.append(f'  (paper "A4")')
        
        # Registrar librerías usadas
        used_lib_ids = set([get_symbol_lib_id(c.get("type", "")) for c in components])
        
        if used_lib_ids:
            lines.append(f'  (lib_symbols')
            for lib_id in sorted(used_lib_ids):
                # Extraemos el dibujo completo del símbolo
                lines.append(extract_symbol_from_lib(lib_id))
            lines.append(f'  )')
        
        pin_positions = {}
        
        # Colocar componentes
        for comp in components:
            cid = comp.get("id", "U?")
            ctype = comp.get("type", "R")
            cval = comp.get("value", "")
            # KiCAD coords están en mm (generalmente espaciados cada 2.54 o 1.27 mm)
            # Escalamos las coordenadas dadas (ej. 100 -> 100 mm)
            cx = float(comp.get("x", 100))
            cy = float(comp.get("y", 100))
            
            lib_id = get_symbol_lib_id(ctype)
            comp_uuid = generate_uuid()
            
            # Símbolo
            lines.append(f'  (symbol (lib_id "{lib_id}") (at {cx} {cy} 0) (unit 1)')
            lines.append(f'    (in_bom yes) (on_board yes) (dnp no) (uuid "{comp_uuid}")')
            
            # Propiedad Reference (ID)
            lines.append(f'    (property "Reference" "{cid}" (at {cx} {cy-5} 0)')
            lines.append(f'      (effects (font (size 1.27 1.27)))')
            lines.append(f'    )')
            
            # Propiedad Value
            lines.append(f'    (property "Value" "{cval}" (at {cx} {cy+5} 0)')
            lines.append(f'      (effects (font (size 1.27 1.27)))')
            lines.append(f'    )')
            
            lines.append(f'  )')
            
            # Registrar posiciones de los pines (aproximación para dibujar alambres)
            # En KiCad real, los pines están a cierta distancia del centro
            # Usaremos una heurística muy simple: pin 1 a cx-5, pin 2 a cx+5
            pin_positions[f"{cid}-1"] = (cx - 5.08, cy)
            pin_positions[f"{cid}-2"] = (cx + 5.08, cy)
            if "Q_" in ctype: # Transistor
                pin_positions[f"{cid}-3"] = (cx, cy + 5.08)

        # Colocar Conexiones (Wires)
        for conn in connections:
            pins = conn.get("pins", [])
            if len(pins) < 2:
                continue
            
            # Topología estrella: conectamos todos los pines al primero
            first_pin = pins[0]
            if first_pin not in pin_positions:
                continue
                
            p1_x, p1_y = pin_positions[first_pin]
            
            for other_pin in pins[1:]:
                if other_pin not in pin_positions:
                    continue
                p2_x, p2_y = pin_positions[other_pin]
                
                # Wire directo de p1 a p2
                lines.append(f'  (wire (pts (xy {p1_x} {p1_y}) (xy {p2_x} {p2_y}))')
                lines.append(f'    (stroke (width 0) (type default))')
                lines.append(f'    (uuid "{generate_uuid()}")')
                lines.append(f'  )')

        lines.append(f')')
        
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines) + "\n")
            
        return {"status": "ok", "file": str(output_file)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def main():
    parser = argparse.ArgumentParser(description="Genera archivo .kicad_sch desde Netlist JSON.")
    parser.add_argument("--json", required=True, help="Ruta al JSON del Netlist")
    parser.add_argument("--output", required=True, help="Ruta de salida para el .kicad_sch")
    args = parser.parse_args()

    json_path = Path(args.json)
    out_path = Path(args.output)

    if not json_path.exists():
        print(json.dumps({"status": "error", "message": f"Archivo no encontrado: {json_path}"}))
        sys.exit(1)

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            netlist = json.load(f)
            
        # Si el netlist viene del analizador de imagenes
        if "analisis" in netlist:
            netlist = netlist["analisis"]
            
        result = generate_kicad_sch(netlist, out_path)
        print(json.dumps(result))
        if result["status"] == "error":
            sys.exit(1)
        sys.exit(0)
    except json.JSONDecodeError as e:
        print(json.dumps({"status": "error", "message": f"Error parseando JSON: {str(e)}"}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
