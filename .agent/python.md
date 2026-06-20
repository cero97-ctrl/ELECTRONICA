# Registro de Errores en Scripts Python

Este archivo documenta errores comunes encontrados al ejecutar scripts Python en este espacio de trabajo, junto con sus respectivas soluciones para evitar regresiones.

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
