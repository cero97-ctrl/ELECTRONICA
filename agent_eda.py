#!/usr/bin/env python3
import os
import json
import argparse
from typing import List, Dict
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# ==========================================
# 1. DEFINICIÓN DE ESTRUCTURAS DE DATOS (Netlist)
# ==========================================
class Component(BaseModel):
    id: str = Field(description="Identificador del componente (ej. R1, C1, U1)")
    type: str = Field(description="Tipo de componente genérico (ej. Resistor, Capacitor, NPN)")
    value: str = Field(description="Valor del componente incluyendo prefijos de unidad (ej. 10k, 100uF, 2.5m). Si usa \SI{}{}, traduce el prefijo (ej. \SI{10}{\kilo\ohm} -> 10k). Dejar vacío si no aplica.")
    lcsc_part: str = Field(description="Número de parte LCSC sugerido para JLCPCB (ej. C17414). El LLM debe intentar sugerir uno genérico de montaje superficial (SMD 0805) si es posible.")
    x: int = Field(default=4000, description="Coordenada X deducida del código TikZ (se recomienda multiplicar por 100 para escalar en el canvas de EasyEDA).")
    y: int = Field(default=3000, description="Coordenada Y deducida del código TikZ (se recomienda multiplicar por 100 para escalar en el canvas de EasyEDA).")

class Connection(BaseModel):
    net_name: str = Field(description="Nombre de la red o nodo lógico (ej. GND, VCC, Net_1)")
    pins: List[str] = Field(description="Lista de pines conectados a esta red con el formato Componente-Pin (ej. ['R1-1', 'U1-3', 'C1-2'])")

class CircuitNetlist(BaseModel):
    components: List[Component] = Field(description="Lista de todos los componentes en el circuito")
    connections: List[Connection] = Field(description="Lista de todas las conexiones eléctricas (Netlist)")

# ==========================================
# 2. CONFIGURACIÓN DEL AGENTE LLM
# ==========================================
def initialize_llm():
    # Asume que GROQ_API_KEY está en las variables de entorno o en .groq_api_key
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        try:
            with open(".groq_api_key", "r") as f:
                api_key = f.read().strip()
        except FileNotFoundError:
            raise ValueError("No se encontró la API key de Groq. Configura GROQ_API_KEY o el archivo .groq_api_key")
    
    return ChatGroq(
        groq_api_key=api_key,
        model_name="llama-3.3-70b-versatile", # Se recomienda un modelo grande para razonamiento lógico
        temperature=0.1 # Baja temperatura para resultados deterministas
    )

# ==========================================
# 3. CADENA DE EXTRACCIÓN LATEX -> NETLIST
# ==========================================
def extract_netlist_from_latex(latex_code: str, llm) -> dict:
    parser = JsonOutputParser(pydantic_object=CircuitNetlist)
    
    prompt = PromptTemplate(
        template="""Eres un ingeniero electrónico experto en captura de esquemáticos.
Tu tarea es analizar el siguiente código LaTeX (circuitikz) que describe un diagrama eléctrico y extraer el Netlist y la Lista de Materiales (BOM).

Asegúrate de:
1. Identificar cada componente (R, C, Diodos, Fuentes, etc.).
2. Deducir la topología (qué pin de qué componente se conecta con cuál) basado en las coordenadas o nodos del LaTeX.
3. Asignar un número LCSC genérico para JLCPCB a componentes pasivos (ej. resistencias 0805, capacitores cerámicos 0805).
4. Extraer los valores con sus prefijos de unidades. Si el código usa el paquete siunitx (ej. \\SI{10}{\\kilo\\ohm} o \\SI{100}{\\micro\\farad}), debes interpretar el comando y extraer el valor comercial estándar (ej. "10k", "100uF"). Si usa notación plana (ej. l=10k), extrae "10k".

Código LaTeX:
{{ latex_code }}

{{ format_instructions }}""",
        input_variables=["latex_code"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
        template_format="jinja2",
    )
    
    chain = prompt | llm | parser
    return chain.invoke({"latex_code": latex_code})

# ==========================================
# 4. GENERADOR DE FORMATO EASYEDA (ESQUEMÁTICO JSON)
# ==========================================
def generate_easyeda_json(netlist_data: dict, output_file: str):
    """
    Convierte la estructura Netlist extraída a un formato JSON compatible con EasyEDA.
    Nota: EasyEDA usa un esquema interno complejo basado en diccionarios para formas y componentes.
    Esta función crea un esqueleto básico (Proof of Concept) que puede expandirse.
    """
    
    easyeda_format = {
        "head": {
            "docType": "1", # 1 = Esquemático
            "editorVersion": "6.5.34",
            "c_para": {},
            "x": "4000",
            "y": "3000"
        },
        "canvas": "CA~1000~1000~#FFFFFF~yes~#CCCCCC~10~1000~1000~line~10~none",
        "shape": [], # Aquí van los cables (Wires)
        "BOM": {},   # Lista de materiales mapeados
        "itemOrder": []
    }
    
    # Insertar componentes en el BOM de EasyEDA
    # En un sistema completo, aquí se instancian los símbolos gráficos (schLib)
    for idx, comp in enumerate(netlist_data["components"]):
        internal_id = f"gge{idx}"
        easyeda_format["BOM"][internal_id] = {
            "name": comp["type"],
            "designator": comp["id"],
            "package": "0805", # Huella por defecto
            "val": comp["value"],
            "supplierPart": comp["lcsc_part"]
        }
        easyeda_format["itemOrder"].append(internal_id)

    # Insertar cables (Wires) gráficos interconectando componentes
    for conn in netlist_data.get("connections", []):
        net_name = conn.get("net_name", "")
        points = []
        
        # Recopilar coordenadas de todos los componentes conectados a esta red
        for pin in conn.get("pins", []):
            comp_id = pin.split('-')[0]
            for c in netlist_data.get("components", []):
                if c["id"] == comp_id:
                    points.append((c.get("x", 4000), c.get("y", 3000)))
                    break
                    
        # Unir el primer componente con todos los demás en la misma red formando líneas (topología estrella básica)
        if len(points) > 1:
            x1, y1 = points[0]
            for (x2, y2) in points[1:]:
                wire_str = f"WIRE~{x1}~{y1}~{x2}~{y2}~#008800~1~solid~{net_name}"
                easyeda_format["shape"].append(wire_str)
    
    # Guardar archivo JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(easyeda_format, f, indent=4)
    
    print(f"[+] Archivo EasyEDA generado con éxito: {output_file}")
    print("[!] Para usarlo: Ve a EasyEDA > File > Open > EasyEDA... y selecciona este archivo JSON.")

# ==========================================
# 5. FUNCIÓN PRINCIPAL (FLUJO DEL AGENTE)
# ==========================================
def run_agent(latex_filepath: str, output_filepath: str):
    print(f"[*] Leyendo archivo LaTeX: {latex_filepath}")
    try:
        with open(latex_filepath, 'r', encoding='utf-8') as f:
            latex_content = f.read()
    except Exception as e:
        print(f"[x] Error al leer el archivo: {e}")
        return
        
    llm = initialize_llm()
    
    print("[*] Ejecutando análisis semántico del circuito con LLM (esto puede tardar)...")
    netlist = extract_netlist_from_latex(latex_content, llm)
    
    print("[+] Análisis completado. Componentes encontrados:")
    for comp in netlist.get("components", []):
        print(f"    - {comp['id']} ({comp['type']}, {comp['value']}) -> LCSC: {comp['lcsc_part']}")
        
    print("[*] Generando archivo compatible con EasyEDA...")
    generate_easyeda_json(netlist, output_filepath)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agente IA para extraer Netlist de LaTeX y generar JSON para EasyEDA.")
    parser.add_argument("input_file", help="Ruta al archivo LaTeX de entrada (.tex)")
    parser.add_argument("-o", "--output", help="Ruta al archivo JSON de salida (por defecto: misma carpeta y nombre base que el archivo .tex)")
    
    args = parser.parse_args()
    
    if not args.input_file.lower().endswith('.tex'):
        print(f"[x] Error: El archivo de entrada '{args.input_file}' debe tener la extensión '.tex'.")
    elif not os.path.exists(args.input_file):
        print(f"[x] Error: El archivo de entrada '{args.input_file}' no existe.")
    else:
        output_filepath = args.output
        if not output_filepath:
            base_path = os.path.splitext(args.input_file)[0]
            output_filepath = f"{base_path}_easyeda.json"
            
        run_agent(args.input_file, output_filepath)