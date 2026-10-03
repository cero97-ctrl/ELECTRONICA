# Registro de Errores en Scripts Python

Este archivo documenta errores comunes encontrados al ejecutar scripts Python en este espacio de trabajo, junto con sus respectivas soluciones para evitar regresiones.

> **Alcance:** es un registro **histórico** de fallos reales y sus arreglos, no una descripción del estado actual del código. Entradas que mencionan `langchain_groq`, `ChatGroq` o "Llama 3.3 vía Groq" (p. ej. las 3 y 4) describen un stack que **ya no existe**: la migración a OpenRouter se aplicó y commiteó el 2026-08-15 (`c672c27`). Sus soluciones (venv/conda, `jinja2` en `PromptTemplate`, raw strings, llaves balanceadas para JSON) siguen siendo válidas y fueron aplicadas; lo que caducó fue el proveedor. `agent_eda.py` ya no importa `langchain_groq`: usa `get_chat_openai()` de `execution/llm_client.py`.

---

## 1. `PromptTemplate` de LangChain Falla con Contenido LaTeX que Contiene Llaves Numéricas

### Síntoma / Mensaje de Error

Al ejecutar un script que usa `PromptTemplate` de LangChain para procesar contenido LaTeX, el script falla con el siguiente error:

```text
pydantic_core._pydantic_core.ValidationError: 1 validation error for PromptTemplate
  Value error, Invalid variable name '10' in f-string template. Variable names
  cannot be all digits as they are interpreted as positional arguments.
  [type=value_error, input_value={'template': '...', 'template_format': 'f-string'}, input_type=dict]
```

### Causa

Por defecto, `PromptTemplate` de LangChain usa `template_format='f-string'`, que interpreta cualquier contenido entre llaves simples `{...}` como una variable. Cuando el contenido LaTeX inyectado contiene comandos del paquete `siunitx` como `\SI{10}{\kilo\ohm}`, `\SI{100}{\micro\farad}`, o cualquier otra llave con números (`{20}`, `{2.5}`, etc.), Python los interpreta como argumentos posicionales de f-string, lo cual es inválido y lanza un `ValidationError` de Pydantic.

El problema se manifiesta al pasar el código LaTeX como variable al template:

```python
# El contenido LaTeX contiene cosas como: \SI{10}{\kilo\ohm}
# Python ve {10} y lo interpreta como un argumento posicional de f-string
prompt = PromptTemplate(
    template="Analiza esto: {latex_code}",  # f-string por defecto
    input_variables=["latex_code"],
)
chain.invoke({"latex_code": contenido_con_llaves_numericas})  # ← ERROR
```

### Solución

Cambiar el formato del template a **jinja2**, que usa dobles llaves `{{ variable }}` para las variables. De esta forma, las llaves simples `{10}` del código LaTeX se tratan como texto literal sin conflicto:

```python
# Antes (incorrecto — f-string por defecto):
prompt = PromptTemplate(
    template="""Analiza el siguiente código LaTeX:
{latex_code}

{format_instructions}""",
    input_variables=["latex_code"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
)

# Después (correcto — jinja2):
prompt = PromptTemplate(
    template="""Analiza el siguiente código LaTeX:
{{ latex_code }}

{{ format_instructions }}""",
    input_variables=["latex_code"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
    template_format="jinja2",
)
```

### Puntos Clave

- Las variables cambian de `{variable}` a `{{ variable }}` (dobles llaves con espacios).
- Se agrega explícitamente `template_format="jinja2"` al constructor de `PromptTemplate`.
- Esto aplica a **cualquier** `PromptTemplate` que reciba contenido con llaves literales (LaTeX, JSON crudo, código fuente con diccionarios, etc.), no solo LaTeX con `siunitx`.

> **Archivo afectado:** `agent_eda.py`

---

## 2. `SyntaxWarning: invalid escape sequence` en Strings con Comandos LaTeX

### Síntoma / Mensaje de Error

Al ejecutar un script Python que contiene strings con comandos LaTeX (como `\SI`, `\kilo`, `\ohm`), Python emite una advertencia:

```text
SyntaxWarning: invalid escape sequence '\S'
  value: str = Field(description="... Si usa \SI{}{}, traduce el prefijo (ej. \SI{10}{\kilo\ohm} -> 10k)...")
```

A partir de Python 3.12, estas advertencias se convertirán en errores (`SyntaxError`), lo que romperá el script completamente.

### Causa

Python interpreta las barras invertidas (`\`) dentro de strings regulares como **secuencias de escape**. Cuando se escriben comandos LaTeX como `\SI`, `\kilo`, `\ohm` dentro de un string normal, Python intenta interpretar `\S`, `\k`, `\o` como secuencias de escape, las cuales no existen, generando la advertencia.

```python
# Incorrecto — Python intenta interpretar \S, \k, \o como escape sequences
description = "Si usa \SI{10}{\kilo\ohm}, traduce el valor"
```

### Solución

Usar un **raw string** anteponiendo `r` antes de las comillas. Esto le indica a Python que no interprete las barras invertidas como secuencias de escape:

```python
# Antes (incorrecto):
value: str = Field(description="... Si usa \SI{}{}, traduce el prefijo (ej. \SI{10}{\kilo\ohm} -> 10k)...")

# Después (correcto — raw string):
value: str = Field(description=r"... Si usa \SI{}{}, traduce el prefijo (ej. \SI{10}{\kilo\ohm} -> 10k)...")
```

### Puntos Clave

- Anteponer `r` antes del string: `r"..."` o `r'...'`.
- Esto aplica a **cualquier string** que contenga barras invertidas literales (LaTeX, rutas de Windows, expresiones regulares, etc.).
- Alternativa: escapar manualmente cada barra invertida duplicándola (`\\SI{10}{\\kilo\\ohm}`), pero los raw strings son más legibles.
- En Python ≥ 3.12, estas advertencias se convierten en `SyntaxError`, haciendo que el script falle directamente.

> **Archivo afectado:** `agent_eda.py` (línea 18, campo `value` de la clase `Component`)

---

## 3. `ModuleNotFoundError` en Entorno Externamente Administrado (PEP 668)

### Síntoma / Mensaje de Error

Al ejecutar un script que importa un módulo instalable vía pip (por ejemplo, `langchain_groq`), Python lanza:

```text
ModuleNotFoundError: No module named 'langchain_groq'
```

Y al intentar instalar con `pip install`, el sistema rechaza la instalación:

```text
error: externally-managed-environment
× This environment is externally managed
```

### Causa

A partir de PEP 668 (implementado en Debian/Ubuntu 23.04+, Fedora 38+, y distribuciones modernas), el Python del sistema está marcado como **externamente administrado** para evitar conflictos entre `pip` y el gestor de paquetes del sistema (`apt`, `dnf`, etc.). Esto impide instalar paquetes con `pip install` directamente.

### Solución

**Opción A — Usar entorno conda existente (recomendado si ya usas Anaconda):**

```bash
conda activate base   # o el entorno que corresponda
pip install langchain-groq
```

**Opción B — Crear un entorno virtual dedicado:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install langchain-groq tenacity langchain-core pydantic
```

**Opción C — Forzar instalación en el sistema (no recomendado):**

```bash
pip install --break-system-packages langchain-groq
```

### Puntos Clave

- Siempre verificar qué entorno Python está activo antes de ejecutar scripts con dependencias externas (`which python`, `conda info --envs`).
- Para este proyecto, las dependencias del script `agent_eda.py` son: `langchain-groq`, `langchain-core`, `pydantic`, `tenacity`.
- Si usas conda, asegúrate de que el entorno correcto esté activado con `conda activate <nombre>` antes de instalar y ejecutar.

> **Archivo afectado:** `agent_eda.py` (importación de `langchain_groq` en línea 7)

---

## 4. `Invalid json output` al Parsear Respuesta JSON de un LLM (Trailing Commas)

### Síntoma / Mensaje de Error

Al usar `JsonOutputParser` de LangChain para parsear la salida JSON de un LLM (ej. Llama 3.3 vía Groq), el parser falla con:

```text
[x] Error al comunicarse con la API de Groq o parsear la respuesta: Invalid json output: {"components": [
{"id": "R1", ...},
{"id": "R5", ...},    ← coma final (trailing comma)
], 
"connections": [...]}
For troubleshooting, visit: https://docs.langchain.com/oss/python/langchain/errors/OUTPUT_PARSING_FAILURE
```

### Causa

Los LLMs frecuentemente generan JSON con **trailing commas** (comas después del último elemento de un array u objeto), como `[1, 2, 3,]` o `{"key": "val",}`. Esto es válido en JavaScript pero **inválido en JSON estricto** según la RFC 8259. El `JsonOutputParser` de LangChain usa parseo estricto y rechaza este JSON.

### Solución

No depender del `JsonOutputParser.parse()` para el parseo final. En su lugar, interceptar el texto crudo del LLM, extraer el bloque JSON con regex, limpiar las trailing commas, y parsear con `json.loads()`:

```python
import re
import json

# Antes (incorrecto — parseo estricto):
return parser.parse(raw_text)

# Después (correcto — parseo robusto):
json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
if not json_match:
    return {}

json_str = json_match.group(0)
# Eliminar trailing commas antes de ] o }
json_str = re.sub(r',\s*([}\]])', r'\1', json_str)

return json.loads(json_str)
```

### Puntos Clave

- El `JsonOutputParser` se puede seguir usando para generar las `format_instructions` del prompt, pero no para el parseo final.
- La regex `re.sub(r',\s*([}\]])', r'\1', json_str)` convierte `,]` → `]` y `,}` → `}`.
- Este problema es común en todos los LLMs (Llama, Mixtral, GPT), no solo en Groq.
- Guardar el texto crudo del LLM en un archivo `.log` facilita el debug.

> **Archivo afectado:** `agent_eda.py` (función `extract_netlist_from_latex`)

---

## 5. JSON Generado Incompatible con EasyEDA Standard (Estructura Incorrecta)

### Síntoma / Mensaje de Error

El archivo `.json` generado por el script se importa en EasyEDA Standard (File > Open > EasyEDA) pero no muestra componentes ni conexiones, o EasyEDA rechaza el archivo.

### Causa

La estructura JSON generada no cumplía con el [formato de archivos esquemáticos de EasyEDA Standard](https://github.com/EasyEDA/EasyEDA-Documents/blob/master/Open-File-Format/schematic.md). Los errores eran:

| Campo | Error | Formato correcto |
|-------|-------|-------------------|
| `head` | Objeto JSON `{"docType": "1", ...}` | String tilde-delimited: `"1~6.5.54~"` |
| Componentes | Campo `BOM` inventado con metadata | Strings `LIB~x~y~attrs~~0~id` en el array `shape[]` con símbolo gráfico (cuerpo + pines + textos) |
| Wires | Net name como último campo: `W~...~net_name` | ID único como último campo: `W~points~#008800~1~0~none~ggeXX` |
| Campos | `BOM`, `BBox`, `itemOrder` | No existen en el formato; eliminarlos |
| Wrapper | `{"docType": "5", "schematics": [...]}` | JSON plano: `{"head": "...", "canvas": "...", "shape": [...]}` |

### Solución

Reescribir el generador para producir el formato correcto:

1. **Componentes como `LIB~...`** — cada componente es un string en `shape[]` con sub-elementos unidos por `#@$`:
   ```
   LIB~x~y~package`0805`nameAlias`Value`Value`10k`spicePre`R`spiceSymbolName`Resistor`~~0~gge1
   #@$T~N~x~y~0~#000080~Arial~~~~~comment~10k~1~start~gge2
   #@$T~P~x~y~0~#000080~Arial~~~~~comment~R1~1~start~gge3
   #@$R~x~y~0~0~30~10~#A00000~1~0~none~gge4
   #@$P~show~0~1~x~y~180~gge5^^x~y^^M x y h -15~#880000^^...^^^^
   #@$P~show~0~2~x~y~0~gge6^^x~y^^M x y h 15~#880000^^...^^^^
   ```

2. **Wires con IDs**: `"W~x1 y1 x2 y2~#008800~1~0~none~gge20"`

3. **Netlabels**: `"N~x~y~0~#0000FF~Net_1~gge30~start~x~y~~"` para identificar redes visualmente.

4. **Junctions**: `"J~x~y~2.5~#CC0000~gge40"` donde convergen 3+ cables.

5. **Pines con 7 segmentos** unidos por `^^`: config, pin dot, path, name, number, dot, clock.

### Puntos Clave

- EasyEDA Standard usa strings compactos delimitados por `~` (tilde) para cada elemento gráfico.
- Los componentes (`LIB`) contienen sub-elementos delimitados por `#@$`.
- Los pines (`P`) contienen sub-segmentos delimitados por `^^`.
- Todo va en el array `shape[]`; no existen campos separados para BOM o componentes.
- La especificación completa está en: `Agente_EDA/circuito_prueba/schema_easyeda.txt`

> **Archivo afectado:** `agent_eda.py` (función `generate_easyeda_json` y helpers `_build_resistor_lib`, `_build_capacitor_lib`, `_build_generic_lib`, `_build_pin`)

---

## 6. `No se pudo extraer un JSON válido` por Regex Non-Greedy (`\{.*?\}`) en JSON Anidado

### Síntoma / Mensaje de Error

Al intentar extraer un JSON devuelto por un modelo (como Gemini u OpenRouter), el script falla con código 4 y el mensaje:

```text
Falló elaborar_examen.py (código 4): No se pudo extraer un JSON válido de la respuesta del modelo.
```

O internamente se lanza:
```text
ValueError: No se pudo extraer un JSON válido de la respuesta del modelo.
```

A pesar de que la inspección directa (raw text) demuestra que el modelo sí generó un JSON válido y completo de varios kilobytes.

### Causa

La función extractora usaba expresiones regulares con coincidencia *non-greedy* (no codiciosa) para capturar el JSON:

```python
# Incorrecto — el modificador .*? es non-greedy
match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
```

En objetos JSON simples (`{"clave": "valor"}`) funciona, pero si el JSON contiene **objetos anidados** (como múltiples preguntas de examen, o contenido LaTeX con llaves), el motor regex se detiene en la **primera llave de cierre `}`** que encuentra. 

Esto trunca el string prematuramente (ej. `{"examen": {"titulo": "...", "preguntas": [{"numero": 1}`), lo que hace que `json.loads()` falle por un `JSONDecodeError`, resultando en el fallo total de la extracción.

### Solución

Abandonar el uso de expresiones regulares puras para capturar bloques con llaves anidadas (un lenguaje libre de contexto no se captura bien con regex regulares). En su lugar, usar un **algoritmo de escaneo de llaves balanceadas** que respete las cadenas de texto y secuencias de escape:

```python
def _find_balanced_json(text: str) -> str | None:
    """Encuentra el primer objeto JSON balanceado en el texto, respetando strings."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            if in_string:
                escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1] # JSON completo extraído
    return None
```

Y usarlo como base en la función extractora principal, buscando primero dentro de un bloque de código y luego como fallback general.

### Puntos Clave

- Nunca usar `\{.*?\}` (non-greedy) para capturar JSON a menos que se tenga la certeza absoluta de que no habrá llaves anidadas ni contenido estructurado.
- El algoritmo `_find_balanced_json` avanza caracter por caracter saltando lo que hay dentro de strings (`"..."`) para no confundir llaves literales con estructurales.
- Maneja correctamente caracteres escapados (`\"`, `\\`) que pueden romper el detector de strings.

> **Archivos afectados:** 
> - `execution/elaborar_examen.py`
> - `execution/evaluar_examen.py`
> - `execution/analizar_imagen.py`

---

## 17. JSON Truncado en gemini-3.x por `thoughts` Internos (`FinishReason` STOP pero JSON cortado)

### Síntoma / Mensaje de Error

Al evaluar exámenes con `gemini-3.5-flash` vía el SDK nuevo `google-genai`, el script `execution/evaluar_examen.py` falla repetidamente con:

```text
{"status": "error", "code": 4, "message": "No se pudo extraer un JSON válido de la respuesta del modelo."}
```

Al inspeccionar la respuesta cruda se observa que el JSON termina **a mitad de estructura** (ej. cortado justo en `"errores_conceptuales": [`), sin llaves de cierre y sin `finish_reason` en el nivel superior de la respuesta.

### Causa

Desde gemini-3.x en adelante, el modelo consume una porción grande del presupuesto de tokens de salida en **pensamiento interno** (`usage_metadata.thoughts_token_count`, típicamente 5000-6500 tokens de los 8192 `max_output_tokens`). Al sumar el `thoughts` + el JSON final, el JSON queda truncado y `json.loads()` (y a veces hasta `_find_balanced_json`) fallan porque el texto nunca se cierra balanceado.

Evidencia: `tokens p/r/t: 9788 1090 17965` y `thoughts_token_count: 6411`.

### Solución

Desactivar el pensamiento interno con `ThinkingConfig` en el **SDK nuevo** (`google.genai`, el único que soporta la clave):

```python
config=genai_types.GenerateContentConfig(
    system_instruction=system_instruction,
    temperature=0.2,
    max_output_tokens=8192,
    response_mime_type="application/json",
    # Imprescindible en gemini-3.x: sin budget 0 el JSON final se trunca.
    thinking_config=genai_types.ThinkingConfig(
        thinking_budget=0,
        include_thoughts=False,
    ),
)
```

Con `thinking_budget=0` el modelo solo produce el JSON final (sin thoughts), el finish pasa a `FinishReason.STOP` y el JSON es estable.

### Puntos Clave

- El SDK **legacy** (`google.generativeai`, deprecated) NO tiene `ThinkingConfig`; no aplicarlo ahí (se reventaría). Solo afectar la rama `_GENAI_SDK == "new"`.
- Aun con budget 0, gemini-3.x puede fallar intermitentemente (a veces duplica llaves de cierre o corta). Por eso `evaluar_examen.py` ahora llama al modelo dentro de un **bucle de reintentos (máx 3)** que relanza `extract_json_from_response` — si falla `ValueError`, reintenta hasta agotar el budget de la directiva.
- Al inspeccionar respuestas crudas, revisar el objeto completo `response.model_dump()`: el `finish_reason` correcto vive en `candidates[0].finish_reason` (no en el nivel superior de la respuesta, que suele ser `None`).
- Cuota gratuita: la API free tier de Gemini tiene límite diario **20 requests por modelo por proyecto**. El mayor consumo de llamadas de debug puede agotarla y devolver `429 RESOURCE_EXHAUSTED` incluso en peticiones mínimas; no intentar reintentar sin verificar el límite.

> **Archivos afectados:**
> - `execution/evaluar_examen.py` (función `evaluar_con_nuevo_sdk` y bucle de reintentos en `evaluar_examen`)

---

## 18. Errores HTTP 403 / Bloqueos Anti-Bot en Scraping Web (`requests`)

### Síntoma / Mensaje de Error

Al scrapear páginas web con `execution/scrape_single_site.py` (o cualquier script con `requests`), el servidor responde `403 Forbidden`, o el texto descargado llega corrupto/ilegible a pesar de una respuesta 200.

### Causa

El 403 es un bloqueo intencional: los sistemas anti-bot (Cloudflare, Akamai, Datadome) detectan que la petición no proviene de un navegador real. Las causas típicas y los errores de implementación asociados son:

1. **User-Agent por defecto de la librería:** `python-requests/2.31.0` está en listas negras.
2. **Petición "desnuda":** un navegador envía ~una docena de headers (`Accept-Language`, `Sec-Fetch-*`, `Upgrade-Insecure-Requests`, etc.). Un GET con solo 2-3 headers delata al bot.
3. **`Accept-Encoding: ... br` sin `brotli` instalado:** `requests` solo descomprime gzip/deflate automáticamente. Si el servidor responde comprimido en Brotli (`br`) y no existe el paquete `brotli`/`brotlicffi`, `response.text` es basura ilegible.
4. **Rate limiting:** muchas peticiones al mismo dominio en poco tiempo disparan anti-DDoS y bloquean la IP.
5. **Headers `Sec-Fetch-*` inconsistentes:** son *forbidden headers* que el navegador genera solo. Enviarlos con valores contradictorios (ej. `Sec-Fetch-Site: cross-site` en una navegación directa) puede aumentar la detección en validadores estrictos.
6. **Desafíos JavaScript (SPA/Cloudflare):** los headers no bastan; se necesita renderizado real o suplantación de huella TLS.

### Solución (implementada en `execution/scrape_single_site.py`)

1. **Paquete completo de headers de navegador** en `_browser_headers()`: `Accept`, `Accept-Language` (`es-ES,es;q=0.8,...`), `Connection: keep-alive`, `Upgrade-Insecure-Requests`, y `Sec-Fetch-*` consistentes con navegación directa (`Site: none`, `Mode: navigate`, `Dest: document`, `User: ?1`).
2. **`Accept-Encoding` dinámico:** solo se añade `br` si `brotli`/`brotlicffi` es importable; si no, se queda en `gzip, deflate` para que `requests` descomprima bien.
3. **Reintentos con backoff exponencial + jitter** (`RETRY_ATTEMPTS = 3`, respetando el retry budget del framework) en `fetch_html()`: ante 403/429/5xx o fallos de red rota entre 3 user-agents distintos y espera `2^intento + jitter` segundos. El 403 persistente sigue reportándose con código de salida 2.
4. **`requests.Session`** para conservar cookies entre redirecciones y minimizar sospechas.

### Puntos Clave

- **Nunca declarar `br` en `Accept-Encoding` si no está instalado `brotli`/`brotlicffi`** — la respuesta llegará corrupta sin error visible.
- Los headers `Sec-Fetch-*` deben ser **coherentes con el tipo de navegación**; para acceso directo a una URL usar `Site: none` + `Mode: navigate` + `Dest: document` + `User: ?1`.
- Reintentar con backoff es más efectivo y más "cortés" (evita auto-causar rate limiting) que fallar al primer 403.
- Si incluso con headers el sitio usa Cloudflare Turnstile o desafíos JS complejos, evaluar en orden de consumo de RAM: `curl_cffi` (suplantación TLS, ligero) → `cloudscraper` (desafíos JS medios) → Playwright/undetected-chromedriver (alto consumo, cerrar con `browser.quit()` inmediatamente) → API de scraping externa (ScraperAPI/ScrapingBee). **Límite estricto del workspace: 4 GB de RAM.**
- Código de salida 2 de `scrape_single_site.py` = acceso denegado persistente; código 3 = SPA/contenido insuficiente.

> **Archivos afectados:**
> - `execution/scrape_single_site.py` (funciones `fetch_html`, `_browser_headers`, `_sleep_backoff`)
> - `directives/scrape_website.yaml` (edge case 403)

---

## 19. FastMCP v1: `@mcp.tool` sin Paréntesis Lanza `TypeError` en Registro (`@mcp.tool()` correcto)

### Síntoma / Mensaje de Error

Al registrar una herramienta en un servidor FastMCP (paquete `mcp` v1.x), el script muere al arrancar con:

```text
TypeError: The @tool decorator was used incorrectly. Did you forget to call it? Use @tool() instead of @tool
```

### Causa

FastMCP v1 (mcp 1.30, API `from mcp.server.fastmcp import FastMCP`) exige el decorador **invocado**: `@mcp.tool()` (con paréntesis). Usar `@mcp.tool` sin paréntesis se interpreta como pasar la función como argumento de configuración y el registro falla en runtime.

### Solución

```python
# Incorrecto:
@mcp.tool
def mi_tool(...): ...

# Correcto:
@mcp.tool()
def mi_tool(...): ...
```

### Puntos Clave

- Aplica a `@mcp.tool()`, `@mcp.prompt()`, `@mcp.resource()` — todos llevan paréntesis en v1.
- mcp 2.x renombró `FastMCP` → `MCPServer`; el proyecto usa mcp 1.30 (pin `mcp<2`) y sigue con la API v1.

> **Archivo afectado:** `execution/servidor_sismico.py`

---

## 20. FastMCP v1: `host`/`port` NO van en `run()`; van en el Constructor `FastMCP(...)`

### Síntoma / Mensaje de Error

Al lanzar el servidor en modo `streamable-http`, el script falla con:

```text
ERROR al ejecutar el servidor: FastMCP.run() got an unexpected keyword argument 'host'
```

### Causa

En mcp 1.30 la firma es `run(transport, mount_path=None)` — `run()` SOLO recibe el transporte. Los parámetros de red (`host`, `port`, `streamable_http_path`, etc.) son argumentos del **constructor** `FastMCP(name, host=..., port=..., streamable_http_path='/mcp')`.

### Solución

```python
# Incorrecto (falla en mcp 1.30):
mcp = FastMCP("MiServidor")
mcp.run(transport="streamable-http", host="127.0.0.1", port=8000)

# Correcto:
mcp = FastMCP("MiServidor", host="127.0.0.1", port=8000)
mcp.run(transport="streamable-http")
```

### Puntos Clave

- URL por defecto del endpoint HTTP: `http://HOST:PORT/mcp` (`streamable_http_path`).
- Stdio no usa host/port; solo se aplican en streamable-http/sse.

> **Archivo afectado:** `execution/servidor_sismico.py`

---

## 21. Colisión de Nombres: Parámetro `lista` Sombreado por una Tool Decorada → `'function' object is not iterable`

### Síntoma / Mensaje de Error

Una tool FastMCP registrada dentro de una función que recibe la lista de datos como parámetro, y cuyo nombre coincide con esa lista, falla al invocarla:

```text
Error executing tool eventos: 'function' object is not iterable
```

### Causa

El decorador `@mcp.tool()` reasigna el **mismo nombre local** de la función decorada (ej. `eventos`) al objeto Tool, sombreando el parámetro de la función contenedora que tenía ese nombre (ej. `registrar_tools(mcp, eventos)`). Dentro del closure, `eventos` ya no es la lista sino el objeto Tool decorado → al iterar, `'function' object is not iterable`.

### Solución

Renombrar el parámetro de la función contenedora para que **no** coincida con ningún nombre de tool/parámetro de tool:

```python
# Incorrecto — 'eventos' (lista) colisiona con la tool 'eventos':
def registrar_tools(mcp, eventos):
    @mcp.tool()
    def eventos(...):           # ← reasigna el local 'eventos'
        filtrados = _filtra(eventos, ...)   # ← 'eventos' es ahora el Tool

# Correcto:
def registrar_tools(mcp, catalogo):
    @mcp.tool()
    def eventos(...):
        filtrados = _filtra(catalogo, ...)  # ← nombre no colisiona
```

### Puntos Clave

- Regla general: el parámetro del closure (los datos) debe tener un nombre DISTINTO de todas las tools/parámetros que se registren dentro.
- Chequear el código de la tool que falla: si su cuerpo itera una variable y el error es `'function' object is not iterable`, casi seguro es sombreado por el decorador.

> **Archivo afectado:** `execution/servidor_sismico.py` (función `registrar_tools`)

---

## 22. Un LLM Puede Respetar el FORMATO de un JSON y Aun Así Mentir en el Total

### Síntoma / Mensaje de Error

Una evaluación devuelve `status: ok` y un JSON bien formado, pero la nota no cuadra
con la suma de sus propios ítems:

```text
evaluacion.puntaje_sugerido      = "5.5/10"
evaluacion.nivel_desempeno       = "Bueno"
suma de observaciones_por_item  = 5.00
```

Peor: la rúbrica de origen ni siquiera permitía ese resultado (los pesos sumaban
11.5 sobre una base declarada de 10), y ningún test lo detectó.

### Causa

El prompt pedía «el total es la suma de los parciales». El modelo cumplió la forma
(salida JSON válida, campos correctos, cada ítem con su denominador) y aun así
reportó un total que no era su suma: la aritmética la hacía el LLM, y la aritmética
es justo lo que un modelo de lenguaje no garantiza. Peor todavía, un JSON
estructurado da una falsa sensación de verificación: `json.loads()` no tiene nada
que decir sobre si 5.5 es coherente con 5.0.

Cambiar la prosa («sé más explícito con la suma») **no** lo arregla: se probó y los
denominadores pasaron a ser correctos mientras el total seguía sin cuadrar. Un LLM
no es una calculadora.

### Solución (implementada en `execution/evaluar_examen.py`)

Dejar al modelo **una sola** tarea — puntuar ítems — y hacer que el programa sume:

```python
# 1) El prompt/schema NO pide el total (SCHEMA_SALIDA)
"No emitas `puntaje_sugerido` ni `nivel_desempeno`: el programa los calcula sumando
 tus `puntaje_parcial`."

# 2) La suma es una función pura, testeable y sin red (calcular_nota)
datos, avisos = calcular_nota(evaluacion["observaciones_por_item"])
evaluacion.update(datos)
if avisos:
    evaluacion["nota_para_el_profesor"] += " " + " ".join(avisos)

# 3) Y por si el modelo los emite igual, se descartan ANTES de calcular
evaluacion.pop("puntaje_sugerido", None)
evaluacion.pop("nivel_desempeno", None)
```

Reglas que debe cumplir la función pura:

- **El máximo es una invariante, no una consecuencia.** Si la suma se pasa, se
  recorta al tope y se avisa. Un `min(10.0, suma)` es barato y elimina de raíz la
  clase de bug «nota mayor que 10».
- **Cada parcial se limita a su propio peso.** Un `3.0/1.0` se recorta a `1.0` y
  deja aviso, en vez de inflar el total.
- **Lo ilegible se cuenta y se dice.** Un ítem sin parcial (`N/A`, `""`) genera un
  aviso; ignorarlo en silencio hace creer que el alumno contestó lo que no contestó.
- **El denominador solo existe si hay separador explícito** (`0.5/1.7`, `0.7 de
  1.7`, `8 out of 20`). Un número suelto (`0.5`) **no** tiene denominador:
  interpretarlo como su propio máximo hace que el chequeo de «parcial por encima del
  peso» se dispare solo, sobre datos correctos. Este bug existió en la primera
  versión y lo detectó un caso de prueba, no la producción.
- **El nivel es una función del total**, no una decisión del modelo.

### Puntos Clave

- «El modelo cumple el contrato» **no** significa «el modelo cumplió la aritmética».
  Son dos contratos distintos; solo uno es verificable por parseo.
- El síntoma de esta familia es siempre el mismo: **el campo agregado no cuadra con
  los campos que lo componen**. Añadir un test que compare `total == sum(partials)`
  es lo que convierte un JSON bien formado en un JSON verificable.
- Cuando el valor lo decide el programa, el prompt debe **dejar de pedirlo**. Pedirlo
  y sobrescribirlo produce un JSON con un campo que miente sobre quién lo decidió, y
  desperdicia tokens del modelo en un campo que se tira.
- Los avisos de cálculo van al campo que el humano lee (`nota_para_el_profesor`), no
  a un canal paralelo: un recorte silencioso es peor que una nota baja.

> **Archivos afectados:**
> - `execution/evaluar_examen.py` (`calcular_nota`, `nivel_para_nota`, `_parsear_parcial`, y el punto de integración tras la llamada al modelo)
> - `execution/test_evaluar_rubrica.py` (`test_nota_la_calcula_el_programa`, `test_el_prompt_no_pide_la_nota`)
> - `directives/evaluar_examen_estudiante.yaml`, `directives/evaluar_practica_laboratorio.yaml` (contrato + edge case)
> - `directives/rubricas/rubrica_practica_lab.yaml` (pesos normalizados a 10.0, niveles con clave explícita)

## 23. Una Escala que No Suma 10: Sumar en Crudo Reprobaba al Alumno Correcto

### Síntoma / Mensaje de Error

Tras la corrección del total (ver entrada 22) la aritmética ya era del programa, pero la
nota seguía siendo falsa, y esto solo se veía leyendo el caso, no el JSON:

```text
observaciones_por_pregunta: 3 ítems -> "0.5/1", "0.7/1", "0.3/1"
puntaje_sugerido            = "1.5/10"
nivel_desempeno             = "Insuficiente"      # el alumno sacaba el 50 %
```

El alumno contestaba la mitad de lo que se le pedía y quedaba reprobado. Peor: cuando el
modelo omitía el denominador (`"0.5"`, `"0.7"`, `"0.3"`), el programa no detectaba nada
—`maximo_alcanzable=0` no disparaba aviso porque el chequeo solo miraba los ítems con
denominador— y publicaba `1.5/10` **en silencio**.

### Causa

La escala de un examen **no es 10**. Es lo que diga el examen: 3 preguntas a 1 punto
escalan a 3, 20 preguntas a 0.5 escalan a 10, un parcial sobre 20 escala a 20. La nota
institucional es siempre sobre 10, así que hace falta una conversión:

```
nota = 10 · (Σ obtenidos) / (Σ denominadores)
```

Sumar los parciales en crudo solo es correcto si esa escala ya es 10, y ese caso
concreto (una rúbrica de laboratorio) es la excepción, no la regla.

### Solución (implementada en `execution/evaluar_examen.py`)

1. **Normalizar contra la escala conocida, siempre.** La suma cruda solo sobrevive cuando
   `Σ denominadores == 10`, y en ese caso normalizar da el mismo número.
2. **Avisar cuando se normaliza.** Una nota normalizada sin aviso parece una nota directa;
   el profesor tiene que saber que hubo conversión.
3. **Si no hay escala, no hay nota.** Sin rúbrica y sin denominadores la base es
   indescifrable, y publicar un número inventado es peor que no publicar nada:

   ```python
   elif suma_pesos <= 0:
       fiable = False
       nota = 0.0
       escala = 0.0   # 0 = escala desconocida, que es justo el problema
       avisos.append("Cálculo automático: SIN ESCALA FIABLE. ...")
   ```
   Sale `nota_fiable=false`, `puntaje_numerico=null`, `puntaje_sugerido="No publicable"`
   y `nivel_desempeno="No publicable"`. En el PDF cabe en una celda; "No publicable
   (revisar a mano)" la partía en dos líneas, así que el detalle vive en
   `nota_para_el_profesor`.
4. **El invariante correcto no es `0 <= nota <= 10`, es `si hay nota, 0 <= nota <= 10`.**
   `None` no es una nota fuera de rango: es la ausencia de nota. Comparar `None` con `<=`
   lanza `TypeError` y hace caer el test que respaldaba toda la aritmética. Por eso el
   test comprueba la invariante *condicional* y, cuando el valor es `None`, exige que
   además la nota esté marcada como no publicable.

### El bug espejo: omitir un criterio **subía** la nota

Al principio, con rúbrica, la escala se armaba con los denominadores **que devolvió el
modelo**. Si el modelo se comía un criterio, su peso desaparecía del denominador y todo
lo demás se normalizaba hacia arriba:

```text
informe con montaje = 0.0/1.3 (el modelo lo omitió)  ->  4.3/10 correcto
el mismo informe, omitiendo "montaje" del JSON     ->  4.9/10   # bonificación
```

El alumno cobraba por un fallo del modelo. Con rúbrica la escala la **fija la rúbrica**
(sus pesos se validan al cargar y deben sumar 10) y un criterio ausente vale 0 sobre esa
escala, sin renormalizar nada. La lista de ausentes va en `items_ausentes` para
distinguir "el alumno no respondió" de "el modelo se lo comió".

### Puntos Clave

- **La escala la declara el instrumento, no el instrumento superior.** `Σ denominadores`
  es un dato de la rúbrica/examen; la nota es una conversión a 10, siempre.
- **Ausencia de dato ≠ dato.** Sin escala no se publica nota; se publica el motivo y la
  suma observada, que es información útil para el humano.
- **Un denominador faltante y un criterio faltante son el mismo agujero visto desde dos
  lados.** Uno impide calcular la nota; el otro hacía subir la nota. Ambos se avisan.
- **La fuente de verdad de un peso es el archivo de configuración**, no la cadena que un
  modelo pueda haber generado: si divergen, gana el YAML y se avisa (ver entrada 22, y
  `cargar_rubrica()` valida que los pesos cierren a 10 antes de que el modelo los vea).
- **Una rúbrica es configuración y se valida al cargar.** Pesos que no cierran a 10, clave
  de peso mal escrita (`pesos:` en vez de `peso:`), peso no numérico, `criterios:` que no
  es un mapa o YAML roto: todos lanzan `ValueError` con el motivo. Sin ese chequeo, una
  clave mal escrita significaba que el modelo nunca veía los pesos y se inventaba la
  escala, y una evaluación sobre una rúbrica inexistente era indistinguible de una real.

> **Archivos afectados:**
> - `execution/evaluar_examen.py` (`calcular_nota`, `cargar_rubrica`, `_normalizar_nombre`,
>   `leer_rubrica`, `evaluar_documento` y el punto de integración tras la llamada al modelo)
> - `execution/test_evaluar_rubrica.py` (`test_escala_se_normaliza_no_se_suma_en_crudo`,
>   `test_la_rubrica_manda_en_los_pesos`, `test_rubrica_invalida_falla_ruidosamente`)
> - `directives/evaluar_examen_estudiante.yaml`, `directives/evaluar_practica_laboratorio.yaml`
