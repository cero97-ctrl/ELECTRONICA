# Arquitectura de Enrutamiento Multi-LLM para Agente IA

Este documento resume la estrategia de enrutamiento por niveles (Model Routing / Cascading) utilizando **OpenRouter** como pasarela de integración, integrando **opencode** como orquestador y un pool de modelos especializados (**Gemini Flash**, **Kimi K3**, **Claude Opus**).

---

## 1. Planteamiento Inicial

El agente de IA (opencode, capa de orquestación) interactúa con múltiples LLMs según la complejidad de la tarea:
- **Tareas rutinarias:** Asignadas a **Gemini Flash** (`google/gemini-3.7-flash`).
- **Contexto extenso / razonamiento intermedio:** Asignadas a **Kimi K3** (`moonshotai/kimi-k3`).
- **Tareas complejas:** Asignadas a **Claude Opus** (`anthropic/claude-opus-5`).
- **Pasarela de integración:** **OpenRouter**.
- **Orquestador:** **opencode** (agente local, capa de orquestación — este asistente).

El orquestador no es un LLM remoto dedicado: es la capa de decisión del propio agente, que
clasifica el requerimiento contra la matriz de decisión y enruta la tarea al script de
ejecución con el `--modelo` del nivel elegido.

---

## 2. Criterios de Enrutamiento para el Orquestador (opencode)

Para evitar decisiones opacas o sesgadas, el orquestador sigue reglas explícitas de
clasificación. La política de runtime vive en `.agent/enrutamiento.md` (auto-cargada por
opencode) y el SOP detallado en `directives/enrutamiento_llm.yaml`.

### Matriz de Decisión

| Criterio | Nivel 1: Gemini Flash | Nivel 2: Kimi K3 | Nivel 3: Claude Opus |
| :--- | :--- | :--- | :--- |
| **Estructura de la tarea** | Lineal, paso único, extracción, conversión de formato (JSON/YAML). | Ingesta/síntesis de contexto masivo, lectura multi-archivo, RAG extenso. | Multi-etapa, diseño arquitectónico, planificación abstracta. |
| **Tolerancia a fallos** | Alta (búsqueda de sintaxis, resúmenes, logs, parsing simple). | Media (resúmenes de datasheets, destilación de logs extensos). | Baja (lógica de compilación, cálculo formal, refactorización crítica). |
| **Ambigüedad** | Instrucciones explícitas y bien delimitadas. | Documentación densa o repetitiva con patrones claros. | Requisitos abiertos, diagnóstico de errores desconocidos. |
| **Dominio técnico** | Consultas estándar, generación de scripts plantilla. | Análisis de repositorios completos, auditorías de diseño. | Validación de restricciones cruzadas, reglas físicas o de diseño. |

---

## 3. Integración de Kimi K3 en la Arquitectura

Incorporar **Kimi K3** (Moonshot AI, ID OpenRouter `moonshotai/kimi-k3`) añade una capa de
**razonamiento intermedio económico** con **1M de contexto** (2.8T params, razonamiento
*always-on*, multimodal, $3/$15 por M tokens, cache read $0.30).

> **Nota de posicionamiento:** Kimi K3 es un modelo flagship de razonamiento, no un mero
> lector de documentos. En OpenRouter compite en el mismo tier que Claude Opus pero a un
> costo ~40-60 % menor. Su rol natural es el de **Nivel 2.5**: razonamiento y síntesis de
> contexto masivo cuando Claude Opus sería sobredimensionado, y como **fallback económico**
> de Opus ante límites de capacidad (429) o presupuesto.

### Jerarquía de 3 Niveles

| Nivel | LLM | Rol Principal y Casos de Uso |
| :--- | :--- | :--- |
| **Nivel 1: Rápido / Rutinario** | **Gemini Flash** (`google/gemini-3.7-flash`) | Formateo, parsing JSON/YAML, llamadas a herramientas simples, validación sintáctica rápida y bajo costo. RAG de rutina. |
| **Nivel 2: Contexto Extenso / Razonamiento Intermedio** | **Kimi K3** (`moonshotai/kimi-k3`) | Ingesta de documentación técnica masiva, lectura completa de múltiples archivos/código fuente, RAG extenso, destilación de logs, síntesis de datasheets. Razonamiento complejo a costo intermedio. |
| **Nivel 3: Razonamiento Crítico** | **Claude Opus** (`anthropic/claude-opus-5`) | Diseño arquitectónico, resolución de dependencias complejas, cálculos físicos/matemáticos avanzados y debugging profundo. |

### Disponibilidad y Fallback

- **Geo (desde VE):** los tres modelos se consumen vía OpenRouter (accesible sin VPN).
  Groq/OpenAI directos siguen bloqueados (403).
- **Kimi K3 es propenso a `429` de capacidad** (upstream Moonshot). La cadena de fallback
  ante 429 o errores repetidos de un nivel es: `moonshotai/kimi-k3` →
  `deepseek/deepseek-v4-pro` → `anthropic/claude-opus-5`.
- **`max_tokens` obligatorio:** sin él OpenRouter pide 65536 y con saldo bajo devuelve
  402. Kimi K3 además consume tokens de salida en razonamiento *always-on* (field
  `max_completion_tokens`).

---

## 4. Directiva para el Orquestador (opencode)

El orquestador es el agente local. Clasifica el requerimiento entrante y selecciona el
motor según estas reglas (materializadas en `.agent/enrutamiento.md` y
`directives/enrutamiento_llm.yaml`):

```markdown
Eres el router de ejecución. Clasifica el requerimiento entrante y selecciona el motor según estas reglas:

1. Selecciona 'gemini-flash' si la tarea implica:
   - Formateo/validación de datos, parsing o transformación de sintaxis.
   - Generación de scripts estándar sin lógica de control compleja.
   - Consultas con entradas directas y sin ambigüedad.

2. Selecciona 'kimi-k3' si la tarea implica:
   - Análisis de contexto largo (>50k tokens) o lectura multi-archivo/repositorio.
   - Ingesta de documentación técnica, manuales o resúmenes de logs masivos.
   - Razonamiento complejo de nivel medio donde Opus sería sobredimensionado.

3. Selecciona 'claude-opus' si la tarea implica:
   - Lógica matemática/física formal, diseño de arquitectura modular.
   - Debugging complejo o resolución de dependencias multi-archivo.
   - Generación de código que involucra algoritmos no estándar.
   - Fallos reincidentes de niveles anteriores (escalado reactivo).

Enruta la tarea al script de execution/ adecuado pasando
--api-backend openrouter y --modelo <id del nivel elegido>.
```

---

## 5. Flujos de Trabajo con Procesamiento de Contexto Pesado

1. **Pre-procesamiento y Destilación (Kimi -> Flash / Opus):**
   - Kimi extrae parámetros críticos o fragmentos relevantes de logs extensos o datasheets.
   - La salida filtrada se entrega a Flash (para estructurarla en JSON) o a Opus (para diseñar la solución lógica), reduciendo el consumo de tokens en el modelo superior.
2. **Inspección Multi-archivo:**
   - Kimi evalúa repositorios completos o scripts interconectados para detectar inconsistencias de variables, interfaces o compatibilidad.
3. **Auditoría de Cambios y Reglas de Diseño:**
   - Verificación de cumplimiento de restricciones contra manuales de diseño completos o librerías extensas.

Estos flujos se ejecutan invocando los scripts de `execution/` (vía `flujo_*` o directamente)
con el `--modelo` del nivel correspondiente. La centralización de llamadas a OpenRouter está
en `execution/llm_client.py`.

---

## 6. Implementación de Referencia en Python (OpenRouter)

Los scripts usan el cliente centralizado `execution/llm_client.py` (ver sesión
`2026-08-19_centralizar_llm_client`). La tabla de niveles vive en `MODEL_TIERS`:

```python
from execution.llm_client import openrouter_chat, load_api_key, get_max_tokens

# Fuente única de IDs por nivel (definida en execution/llm_client.py)
MODEL_TIERS = {
    "flash": "google/gemini-3.7-flash",   # Tareas rápidas y atómicas
    "kimi":  "moonshotai/kimi-k3",         # Contexto masivo / razonamiento intermedio
    "opus":  "anthropic/claude-opus-5",    # Razonamiento crítico
}

# Cadena de fallback ante 429 / errores repetidos (Kimi es propenso a 429)
FALLBACK_CHAIN = ["kimi", "opus"]

def query_tier(prompt: str, system_prompt: str, tier: str = "flash"):
    """Envía a OpenRouter usando el tier elegido, con fallback ante fallos."""
    api_key = load_api_key()
    chain = [tier] + FALLBACK_CHAIN if tier != "opus" else [tier, "kimi", "opus"]

    for i, t in enumerate(chain):
        try:
            content, tokens = openrouter_chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                model=MODEL_TIERS[t],
                api_key=api_key,
                temperature=0.2,
                max_tokens=get_max_tokens(),
                title="ELECTRONICA - Enrutamiento",
            )
            return content, t
        except Exception as e:
            if i == len(chain) - 1:
                raise RuntimeError(f"Todos los niveles fallaron: {e}") from e
            print(f"[!] Nivel '{t}' falló ({e}); escalando a '{chain[i + 1]}'")
```

Notas de implementación:

- No fijar nunca `max_tokens` por debajo del valor de `OPENROUTER_MAX_TOKENS` del `.env`
  (sin `max_tokens`, OpenRouter puede devolver 402 con saldo bajo).
- Kimi K3 (razonamiento) no soporta el rol `developer`; usar `system`/`user`. El campo de
  límite de salida para modelos de razonamiento es `max_completion_tokens`.
- Si el orquestador necesita salida estructurada (p. ej. la clasificación de un script),
  reutilizar la extracción de JSON balanceado (`_find_balanced_json`, ver
  `.agent/python.md`), nunca regex non-greedy sobre JSON anidado.
