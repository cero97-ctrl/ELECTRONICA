#!/usr/bin/env python3
import os
import re
import json
import argparse
from typing import List, Dict
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

# ==========================================
# 1. DEFINICIÓN DE ESTRUCTURAS DE DATOS (Netlist)
# ==========================================
class Component(BaseModel):
    id: str = Field(description="Identificador del componente (ej. R1, C1, U1)")
    type: str = Field(description="Tipo de componente genérico (ej. Resistor, Capacitor, NPN)")
    value: str = Field(description=r"Valor del componente incluyendo prefijos de unidad (ej. 10k, 100uF, 2.5m). Si usa \SI{}{}, traduce el prefijo (ej. \SI{10}{\kilo\ohm} -> 10k). Dejar vacío si no aplica.")
    lcsc_part: str = Field(description="Número de parte LCSC sugerido para JLCPCB (ej. C17414). El LLM debe intentar sugerir uno genérico de montaje superficial (SMD 0805) si es posible.")
    x: int = Field(description="Coordenada X deducida del código TikZ (se recomienda multiplicar por 100 para escalar en el canvas de EasyEDA).")
    y: int = Field(description="Coordenada Y deducida del código TikZ (se recomienda multiplicar por 100 para escalar en el canvas de EasyEDA).")

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
    # Asume que OPENROUTER_API_KEY está en las variables de entorno o en .env
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        try:
            from dotenv import load_dotenv
            load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
            api_key = os.environ.get("OPENROUTER_API_KEY")
        except Exception:
            pass
    if not api_key:
        raise ValueError("No se encontró OPENROUTER_API_KEY. Configúrala en el archivo .env o como variable de entorno.")

    try:
        return ChatOpenAI(
            api_key=api_key,
            model="qwen/qwen3.6-27b", # Se recomienda un modelo grande para razonamiento lógico (Qwen 3.6 27B)
            temperature=0.1,          # Baja temperatura para resultados deterministas
            max_tokens=4096,          # Presupuesto explícito (OpenRouter cobra por max_tokens solicitado)
            base_url="https://openrouter.ai/api/v1",
        )
    except Exception as e:
        print(f"[-] Advertencia: El modelo 'qwen/qwen3.6-27b' no está disponible o fue depreciado.")
        print(f"    Detalle del error: {e}")
        print("[*] Intentando inicializar con el modelo de respaldo 'openai/gpt-oss-20b'...")
        return ChatOpenAI(
            api_key=api_key,
            model="openai/gpt-oss-20b", # Modelo de respaldo seguro
            temperature=0.1,
            max_tokens=4096,
            base_url="https://openrouter.ai/api/v1",
        )

# ==========================================
# 3. CADENA DE EXTRACCIÓN LATEX -> NETLIST
# ==========================================
def _is_rate_limit(exception: Exception) -> bool:
    """Comprueba si la excepción generada es por límite de cuota (HTTP 429)."""
    err_str = str(exception).lower()
    return "429" in err_str or "rate limit" in err_str

@retry(
    stop=stop_after_attempt(5), # Reintenta hasta 5 veces
    wait=wait_exponential(multiplier=2, min=3, max=30), # Espera 3s, luego 6s, 12s... hasta un tope de 30s
    retry=retry_if_exception(_is_rate_limit), # Solo reintenta si es error 429
    before_sleep=lambda retry_state: print(f"[-] Rate limit de API (HTTP 429). Esperando para reintentar... (Intento {retry_state.attempt_number}/5)"),
    reraise=True # Propaga la excepción original si se agotan los reintentos
)
def _invoke_chain_with_retry(chain, inputs):
    return chain.invoke(inputs)

def extract_netlist_from_latex(latex_code: str, llm, debug_log_path: str = None) -> dict:
    parser = JsonOutputParser(pydantic_object=CircuitNetlist)
    
    prompt = PromptTemplate(
        template="""Eres un ingeniero electrónico experto en captura de esquemáticos.
Tu tarea es analizar el siguiente código LaTeX (circuitikz) que describe un diagrama eléctrico y extraer el Netlist y la Lista de Materiales (BOM).

Asegúrate de:
1. Identificar cada componente (R, C, Diodos, Fuentes, etc.).
2. Deducir la topología (qué pin de qué componente se conecta con cuál) basado en las coordenadas o nodos del LaTeX.
3. Asignar un número LCSC genérico para JLCPCB a componentes pasivos (ej. resistencias 0805, capacitores cerámicos 0805).
4. Extraer los valores con sus prefijos de unidades. Si el código usa el paquete siunitx (ej. \\SI{10}{\\kilo\\ohm} o \\SI{100}{\\micro\\farad}), debes interpretar el comando y extraer el valor comercial estándar (ej. "10k", "100uF"). Si usa notación plana (ej. l=10k), extrae "10k".

INSTRUCCIONES DE RAZONAMIENTO ESPACIAL (Chain of Thought):
Antes de generar el bloque JSON, debes escribir tu proceso de razonamiento paso a paso:
1. Enumera cada coordenada (x,y) del código TikZ donde ocurra una convergencia de componentes o líneas de cableado.
2. Identifica exactamente qué componente y cuál de sus pines se conecta a esa coordenada (asume pin 1 de entrada, pin 2 de salida).
3. Agrupa los pines que comparten las mismas coordenadas espaciales o están conectados por un `to[short]` para formar las redes (Nets) definitivas.

Código LaTeX:
{{ latex_code }}

{{ format_instructions }}""",
        input_variables=["latex_code"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
        template_format="jinja2",
    )
    
    # Separar el parser de la cadena para interceptar el texto crudo
    chain_llm = prompt | llm
    try:
        response = _invoke_chain_with_retry(chain_llm, {"latex_code": latex_code})
        raw_text = response.content
        if debug_log_path:
            with open(debug_log_path, "w", encoding="utf-8") as f:
                f.write(raw_text)

        # Parseo robusto: extraer el bloque JSON y limpiar trailing commas
        # que los LLM producen con frecuencia (ej. {"key": "val",} o [1, 2,])
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if not json_match:
            print("[x] No se encontró un bloque JSON válido en la respuesta del LLM.")
            if debug_log_path:
                print(f"    Revisa el log crudo en: {debug_log_path}")
            return {}

        json_str = json_match.group(0)
        # Eliminar trailing commas antes de ] o }
        json_str = re.sub(r',\s*([}\]])', r'\1', json_str)

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as je:
            print(f"[x] Error de parseo JSON después de limpieza: {je}")
            if debug_log_path:
                print(f"    Revisa el log crudo en: {debug_log_path}")
            return {}

    except Exception as e:
        print(f"[x] Error al comunicarse con la API: {e}")
        return {}

# ==========================================
# 4. GENERADOR DE FORMATO EASYEDA (ESQUEMÁTICO JSON)
# ==========================================

class _IdCounter:
    """Generador de IDs únicos para elementos EasyEDA (gge1, gge2, ...)."""
    def __init__(self, start=1):
        self._n = start
    def next(self):
        uid = f"gge{self._n}"
        self._n += 1
        return uid


def _build_pin(pin_num, dot_x, dot_y, body_edge_x, body_edge_y, idc):
    """
    Construye un string de Pin EasyEDA (7 segmentos unidos por ^^).
    El pin se dibuja horizontalmente desde body_edge hasta dot.
    """
    pin_id = idc.next()
    h_len = dot_x - body_edge_x  # negativo = izquierda, positivo = derecha
    rotation = "180" if h_len < 0 else "0"

    config = f"P~show~0~{pin_num}~{dot_x}~{dot_y}~{rotation}~{pin_id}"
    dot_seg = f"{dot_x}~{dot_y}"
    path_seg = f"M {body_edge_x} {body_edge_y} h {h_len}~#880000"
    name_seg = f"0~{dot_x}~{dot_y + 3}~0~{pin_num}~start~~"
    num_seg = f"0~{dot_x}~{dot_y - 4}~0~{pin_num}~end~~"
    return f"{config}^^{dot_seg}^^{path_seg}^^{name_seg}^^{num_seg}^^^^"


def _build_resistor_lib(designator, value, lcsc, cx, cy, idc):
    """Genera string LIB~ para un símbolo de Resistor horizontal."""
    lib_id = idc.next()
    attrs = f"package`{lcsc}`nameAlias`Value`Value`{value}`spicePre`R`spiceSymbolName`Resistor`"
    header = f"LIB~{cx}~{cy}~{attrs}~~0~{lib_id}"

    # Texto del valor (Name) y designador (Prefix)
    t_name = f"T~N~{cx - 6}~{cy - 15}~0~#000080~Arial~~~~~comment~{value}~1~start~{idc.next()}"
    t_prefix = f"T~P~{cx - 6}~{cy - 25}~0~#000080~Arial~~~~~comment~{designator}~1~start~{idc.next()}"

    # Cuerpo: rectángulo 30x10 centrado en (cx, cy)
    body = f"R~{cx - 15}~{cy - 5}~0~0~30~10~#A00000~1~0~none~{idc.next()}"

    # Pines: pin1 a la izquierda, pin2 a la derecha (15px de lead cada uno)
    pin1 = _build_pin(1, cx - 30, cy, cx - 15, cy, idc)
    pin2 = _build_pin(2, cx + 30, cy, cx + 15, cy, idc)

    return "#@$".join([header, t_name, t_prefix, body, pin1, pin2])


def _build_capacitor_lib(designator, value, lcsc, cx, cy, idc):
    """Genera string LIB~ para un símbolo de Capacitor horizontal."""
    lib_id = idc.next()
    attrs = f"package`{lcsc}`nameAlias`Value`Value`{value}`spicePre`C`spiceSymbolName`Capacitor`"
    header = f"LIB~{cx}~{cy}~{attrs}~~0~{lib_id}"

    t_name = f"T~N~{cx - 6}~{cy - 15}~0~#000080~Arial~~~~~comment~{value}~1~start~{idc.next()}"
    t_prefix = f"T~P~{cx - 6}~{cy - 25}~0~#000080~Arial~~~~~comment~{designator}~1~start~{idc.next()}"

    # Placas del capacitor: dos líneas verticales paralelas con gap de 4px
    plate_l = f"PL~{cx - 2} {cy - 8} {cx - 2} {cy + 8}~#A00000~1~0~none~{idc.next()}"
    plate_r = f"PL~{cx + 2} {cy - 8} {cx + 2} {cy + 8}~#A00000~1~0~none~{idc.next()}"

    # Líneas de conexión placa -> inicio del pin path
    line_l = f"PL~{cx - 2} {cy} {cx - 15} {cy}~#A00000~1~0~none~{idc.next()}"
    line_r = f"PL~{cx + 2} {cy} {cx + 15} {cy}~#A00000~1~0~none~{idc.next()}"

    pin1 = _build_pin(1, cx - 30, cy, cx - 15, cy, idc)
    pin2 = _build_pin(2, cx + 30, cy, cx + 15, cy, idc)

    return "#@$".join([header, t_name, t_prefix, plate_l, plate_r, line_l, line_r, pin1, pin2])


def _build_generic_lib(designator, comp_type, value, lcsc, cx, cy, idc):
    """Genera string LIB~ genérico (rectángulo) para componentes de 2 pines."""
    lib_id = idc.next()
    prefix_letter = designator[0] if designator else "X"
    attrs = f"package`{lcsc}`nameAlias`Value`Value`{value}`spicePre`{prefix_letter}`spiceSymbolName`{comp_type}`"
    header = f"LIB~{cx}~{cy}~{attrs}~~0~{lib_id}"

    t_name = f"T~N~{cx - 6}~{cy - 15}~0~#000080~Arial~~~~~comment~{value}~1~start~{idc.next()}"
    t_prefix = f"T~P~{cx - 6}~{cy - 25}~0~#000080~Arial~~~~~comment~{designator}~1~start~{idc.next()}"
    body = f"R~{cx - 15}~{cy - 5}~0~0~30~10~#A00000~1~0~none~{idc.next()}"
    pin1 = _build_pin(1, cx - 30, cy, cx - 15, cy, idc)
    pin2 = _build_pin(2, cx + 30, cy, cx + 15, cy, idc)

    return "#@$".join([header, t_name, t_prefix, body, pin1, pin2])


# Mapa de posiciones de pines por tipo de componente (relativas al centro)
_PIN_OFFSETS = {
    "1": (-30, 0),   # Pin 1: 30px a la izquierda del centro
    "2": (30, 0),    # Pin 2: 30px a la derecha del centro
}


def generate_easyeda_json(netlist_data: dict, output_file: str):
    """
    Convierte la estructura Netlist extraída a un JSON EasyEDA Standard válido.
    Genera símbolos LIB para cada componente, cables (W), netlabels (N) y junctions (J).
    """
    idc = _IdCounter()
    shapes = []
    pin_positions = {}  # "R1-1" -> (x, y)

    # --- 1. Generar símbolos LIB para cada componente ---
    for comp in netlist_data.get("components", []):
        cx, cy = int(comp.get("x", 100)), int(comp.get("y", 100))
        designator = comp.get("id", "U?")
        value = comp.get("value", "")
        lcsc = comp.get("lcsc_part", "")
        comp_type = comp.get("type", "Generic").lower()

        if comp_type == "resistor":
            lib_str = _build_resistor_lib(designator, value, lcsc, cx, cy, idc)
        elif comp_type == "capacitor":
            lib_str = _build_capacitor_lib(designator, value, lcsc, cx, cy, idc)
        else:
            lib_str = _build_generic_lib(designator, comp.get("type", "Generic"), value, lcsc, cx, cy, idc)

        shapes.append(lib_str)

        # Registrar posiciones absolutas de los pines
        for pin_num, (dx, dy) in _PIN_OFFSETS.items():
            pin_positions[f"{designator}-{pin_num}"] = (cx + dx, cy + dy)

    # --- 2. Generar cables (Wires) entre pines de la misma red ---
    junction_points = {}  # (x,y) -> conteo de cables que llegan
    for conn in netlist_data.get("connections", []):
        points = []
        for pin in conn.get("pins", []):
            if pin in pin_positions:
                points.append(pin_positions[pin])

        # Topología estrella: hub en el primer punto, cables hacia los demás
        if len(points) > 1:
            hx, hy = points[0]
            junction_points[(hx, hy)] = junction_points.get((hx, hy), 0) + len(points) - 1
            for (px, py) in points[1:]:
                wire_id = idc.next()
                shapes.append(f"W~{hx} {hy} {px} {py}~#008800~1~0~none~{wire_id}")

    # --- 3. Generar netlabels (N) para identificar cada red ---
    for conn in netlist_data.get("connections", []):
        net_name = conn.get("net_name", "")
        first_pin = next((p for p in conn.get("pins", []) if p in pin_positions), None)
        if first_pin and net_name:
            nx, ny = pin_positions[first_pin]
            nl_id = idc.next()
            shapes.append(
                f"N~{nx}~{ny - 12}~0~#0000FF~{net_name}~{nl_id}~start~{nx + 2}~{ny - 12}~~"
            )

    # --- 4. Generar junctions (J) donde convergen 3+ cables ---
    for (jx, jy), count in junction_points.items():
        if count >= 2:
            j_id = idc.next()
            shapes.append(f"J~{jx}~{jy}~2.5~#CC0000~{j_id}")

    # --- 5. Construir JSON EasyEDA Standard (estructura plana) ---
    easyeda_schematic = {
        "head": "1~6.5.54~",
        "canvas": "CA~1200~1200~#FFFFFF~yes~#CCCCCC~10~1200~1200~line~10~pixel~5~400~300",
        "shape": shapes,
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(easyeda_schematic, f, indent=4, ensure_ascii=False)

    print(f"[+] Archivo EasyEDA generado con éxito: {output_file}")
    print(f"    Componentes: {len(netlist_data.get('components', []))}")
    print(f"    Elementos en shape[]: {len(shapes)}")
    print("[!] Para usarlo: EasyEDA Std > File > Open > EasyEDA... > selecciona este .json")

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
    debug_log_path = os.path.splitext(output_filepath)[0] + "_raw_llm.log"
    netlist = extract_netlist_from_latex(latex_content, llm, debug_log_path)
    
    if not netlist:
        print("[x] No se pudo obtener el Netlist. Abortando generación de JSON.")
        return
        
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