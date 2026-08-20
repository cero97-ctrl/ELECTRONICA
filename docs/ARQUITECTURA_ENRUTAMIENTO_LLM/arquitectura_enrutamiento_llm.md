# Arquitectura de Enrutamiento Multi-LLM para Agente IA

Este documento resume la estrategia de enrutamiento por niveles (Model Routing / Cascading) utilizando **OpenRouter** como pasarela de integración, integrando **opencode** como orquestador y un pool de modelos especializados (**Gemini Flash**, **DeepSeek V4 Pro**, **Claude Opus**).

---

## 1. Planteamiento Inicial

El agente de IA (opencode, capa de orquestación) interactúa con múltiples LLMs según la complejidad de la tarea:
- **Tareas rutinarias:** Asignadas a **Gemini Flash** (`google/gemini-3.7-flash`).
- **Contexto extenso / razonamiento intermedio:** Asignadas a **DeepSeek V4 Pro** (`deepseek/deepseek-v4-pro`), con **GLM-5.2** de respaldo.
- **Tareas complejas:** Asignadas a **Claude Opus** (`anthropic/claude-opus-5`).
- **Pasarela de integración:** **OpenRouter**.
- **Orquestador:** **opencode** (agente local, capa de orquestación — este asistente).

El orquestador no es un LLM remoto dedicado: es la capa de decisión del propio agente, que
clasifica el requerimiento contra la matriz de decisión y enruta la tarea al script de
ejecución con el `--modelo` del nivel elegido.

> **Principio rector: decisiones DETERMINISTAS.** El orquestador NO decide el tier
> razonando en el chat. Extrae un descriptor estructurado de la petición (tipo de
> tarea, tamaño de entrada medido, criticidad, visión) y delega la elección en
> `execution/enrutador.py`, que aplica reglas puras. El mismo descriptor produce
> siempre el mismo modelo: la matriz vive en código, no en el criterio del agente.

---

## 2. Enrutamiento Determinista

El orquestador solo hace parsing de intención (mapear la petición a un descriptor).
La decisión es una función pura implementada en `execution/enrutador.py`:

| Paso | Quién | Naturaleza |
| :--- | :--- | :--- |
| Extraer descriptor `{task, tokens, critico, vision, modelo_explicito}` | opencode | Parsing (único paso no-determinista, es traducción) |
| Elegir tier/modelo por reglas | `execution/enrutador.py` | 100% determinista |
| Ejecutar script con `--modelo <id>` | opencode | Ejecución |

### Precedencia de las reglas (en `execution/enrutador.py`)

1. **Modelo explícito** del usuario → se respeta tal cual (override total).
2. **Tokens medidos > 50 000** → tier de contexto masivo (`deepseek`); si la tarea es
   crítica o de razonamiento crítico → `opus`. El tamaño se mide (bytes de archivos
   o contador), nunca se estima a ojo.
3. **Tipo de tarea** → tier según vocabulario controlado (flash/deepseek/opus).
4. **`--critico`** → escala a `opus` aunque el tipo sea de rutina.

### Matriz de Decisión (referencial; la autoridad es el código del enrutador)

| Criterio | Nivel 1: Gemini Flash | Nivel 2: DeepSeek V4 Pro | Nivel 3: Claude Opus |
| :--- | :--- | :--- | :--- |
| **Estructura de la tarea** | Lineal, paso único, extracción, conversión de formato (JSON/YAML). | Ingesta/síntesis de contexto masivo, lectura multi-archivo, RAG extenso. | Multi-etapa, diseño arquitectónico, planificación abstracta. |
| **Tolerancia a fallos** | Alta (búsqueda de sintaxis, resúmenes, logs, parsing simple). | Media (resúmenes de datasheets, destilación de logs extensos). | Baja (lógica de compilación, cálculo formal, refactorización crítica). |
| **Ambigüedad** | Instrucciones explícitas y bien delimitadas. | Documentación densa o repetitiva con patrones claros. | Requisitos abiertos, diagnóstico de errores desconocidos. |
| **Dominio técnico** | Consultas estándar, generación de scripts plantilla. | Análisis de repositorios completos, auditorías de diseño. | Validación de restricciones cruzadas, reglas físicas o de diseño. |

---

## 3. Tier Medio: DeepSeek V4 Pro (+ GLM-5.2 de respaldo)

El tier de **contexto extenso / razonamiento intermedio** lo ocupa
**DeepSeek V4 Pro** (`deepseek/deepseek-v4-pro`, $0.44/$0.87 por M tokens, 1M de
contexto, razonamiento, JSON mode, pesos abiertos, ~18 providers en OpenRouter con
uptime alto). Su respaldo es **GLM-5.2** (`z-ai/glm-5.2`, 1M de contexto, ~25 providers).

> **Kimi K3 (`moonshotai/kimi-k3`) quedó fuera del enrutamiento automático.**
> Razones: propenso a `429` de capacidad (upstream Moonshot, sin mitigación desde
> ningún gateway), costo casi premium ($2.9/$14) y solapamiento con Opus. En la web
> el failover es invisible (K3 → K2.6); en un pipeline cada 429 es latencia y riesgo
> de escalar a opus. Se mantiene disponible SOLO por petición explícita del usuario
> vía `--modelo-explicito moonshotai/kimi-k3` (`MODELOS_OPCIONALES` en `llm_client.py`).

### Jerarquía de 3 Niveles

| Nivel | LLM | Rol Principal y Casos de Uso |
| :--- | :--- | :--- |
| **Nivel 1: Rápido / Rutinario** | **Gemini Flash** (`google/gemini-3.7-flash`) | Formateo, parsing JSON/YAML, llamadas a herramientas simples, validación sintáctica rápida y bajo costo. RAG de rutina. |
| **Nivel 2: Contexto Extenso / Razonamiento Intermedio** | **DeepSeek V4 Pro** (`deepseek/deepseek-v4-pro`), respaldo **GLM-5.2** (`z-ai/glm-5.2`) | Ingesta de documentación técnica masiva, lectura completa de múltiples archivos/código fuente, RAG extenso, destilación de logs, síntesis de datasheets. Razonamiento complejo a costo intermedio. |
| **Nivel 3: Razonamiento Crítico** | **Claude Opus** (`anthropic/claude-opus-5`) | Diseño arquitectónico, resolución de dependencias complejas, cálculos físicos/matemáticos avanzados y debugging profundo. |

### Disponibilidad y Fallback

- **Geo (desde VE):** los tres niveles se consumen vía OpenRouter (accesible sin VPN).
  Groq/OpenAI directos siguen bloqueados (403).
- **Cadenas de fallback deterministas y cost-aware** (ante 429 o errores de servicio):
  - `flash` → `deepseek` → `glm`
  - `deepseek` → `glm` → `opus`
  - `opus` → `deepseek` → `glm`
- **`max_tokens` obligatorio:** sin él OpenRouter pide 65536 y con saldo bajo devuelve
  402. Kimi K3 (si se usa explícitamente) además consume tokens de salida en
  razonamiento *always-on* (field `max_completion_tokens`).

---

## 4. Directiva para el Orquestador (opencode)

El orquestador es el agente local. **No selecciona el motor razonando**: extrae el
descriptor estructurado y delega la elección en `execution/enrutador.py`. La política de
runtime está materializada en `.agent/enrutamiento.md` (auto-cargada por opencode) y el
SOP detallado en `directives/enrutamiento_llm.yaml`.

```markdown
Eres el router de ejecución. NO eliges el modelo: construyes el descriptor y ejecutas el router.

1. Extrae el descriptor de la petición:
   - --task: uno del vocabulario controlado
     * rutina: formateo, parsing, sintaxis, validacion, resumen, rag, multimodal, extraccion, conversion
     * contexto: contexto_masivo, multi_archivo, destilacion, sintesis_logs, auditoria, razonamiento_intermedio
     * crítico: arquitectura, calculo_formal, debug, examen, examen_complejo, netlist, kicad, refactor, diseño
   - --tokens o --archivos: tamaño MEDIDO (nunca estimado a ojo).
   - --critico / --vision: flags booleanos.
   - --modelo-explicito: solo si el usuario nombró un modelo.

2. Ejecuta: python3 execution/enrutador.py <descriptor>
   Usa la salida: tier, model, fallback.

3. Enruta la tarea al script de execution/ adecuado pasando
   --api-backend openrouter y --modelo <model devuelto>.

4. Si el script falla con 429/error de servicio, escala por la cadena 'fallback'
   devuelta (máx 3 intentos). No escales por calidad: solo por fallo de servicio.
```

---

## 5. Flujos de Trabajo con Procesamiento de Contexto Pesado

1. **Pre-procesamiento y Destilación (DeepSeek -> Flash / Opus):**
   - DeepSeek extrae parámetros críticos o fragmentos relevantes de logs extensos o datasheets.
   - La salida filtrada se entrega a Flash (para estructurarla en JSON) o a Opus (para diseñar la solución lógica), reduciendo el consumo de tokens en el modelo superior.
2. **Inspección Multi-archivo:**
   - DeepSeek evalúa repositorios completos o scripts interconectados para detectar inconsistencias de variables, interfaces o compatibilidad.
3. **Auditoría de Cambios y Reglas de Diseño:**
   - Verificación de cumplimiento de restricciones contra manuales de diseño completos o librerías extensas.

Estos flujos se ejecutan invocando los scripts de `execution/` (vía `flujo_*` o directamente)
con el `--modelo` del nivel correspondiente. La centralización de llamadas a OpenRouter está
en `execution/llm_client.py`.

---

## 6. Implementación de Referencia en Python (OpenRouter)

La decisión de tier/modelo vive en `execution/enrutador.py` (reglas puras); los scripts
usan el cliente centralizado `execution/llm_client.py` (ver sesión
`2026-08-19_centralizar_llm_client`). La tabla de niveles vive en `MODEL_TIERS`:

```python
# ---- Decisión (determinista) ----
# python3 execution/enrutador.py --task contexto_masivo --archivos a.tex b.md
# -> {"status": "ok", "tier": "deepseek", "model": "deepseek/deepseek-v4-pro",
#     "fallback": ["deepseek", "glm", "opus"], "reason": "...", "tokens": N}

# ---- Ejecución (cliente centralizado) ----
from execution.llm_client import openrouter_chat, load_api_key, get_max_tokens

# Fuente única de IDs por nivel (definida en execution/llm_client.py)
MODEL_TIERS = {
    "flash":    "google/gemini-3.7-flash",  # Tareas rápidas y atómicas
    "deepseek": "deepseek/deepseek-v4-pro", # Contexto masivo / razonamiento intermedio
    "glm":      "z-ai/glm-5.2",             # Respaldo del tier medio
    "opus":     "anthropic/claude-opus-5",  # Razonamiento crítico
}
# Kimi K3 vive en MODELOS_OPCIONALES: solo por petición explícita.

# Cadenas de fallback deterministas y cost-aware (en enrutador.py)
FALLBACK_CHAINS = {
    "flash":    ["flash", "deepseek", "glm"],
    "deepseek": ["deepseek", "glm", "opus"],
    "opus":     ["opus", "deepseek", "glm"],
}

def query_tier(prompt: str, system_prompt: str, tier: str):
    """Envía a OpenRouter usando el tier elegido por enrutador.py, con fallback."""
    api_key = load_api_key()
    for t in FALLBACK_CHAINS[tier]:
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
            if t == FALLBACK_CHAINS[tier][-1]:
                raise RuntimeError(f"Todos los niveles fallaron: {e}") from e
            print(f"[!] Nivel '{t}' falló ({e}); escalando en la cadena")
```

Notas de implementación:

- No fijar nunca `max_tokens` por debajo del valor de `OPENROUTER_MAX_TOKENS` del `.env`
  (sin `max_tokens`, OpenRouter puede devolver 402 con saldo bajo).
- Kimi K3 (razonamiento) no soporta el rol `developer`; usar `system`/`user`. El campo de
  límite de salida para modelos de razonamiento es `max_completion_tokens`.
- Si el orquestador necesita salida estructurada (p. ej. la clasificación de un script),
  reutilizar la extracción de JSON balanceado (`_find_balanced_json`, ver
  `.agent/python.md`), nunca regex non-greedy sobre JSON anidado.
