# Cuestionario — 2026-09-13

Revisión del ensamblaje del workspace ELECTRONICA. Preguntas y respuestas.

---

## P1. ¿Cuál es la principal razón por la cual `session_log_<run>.jsonl` se considera la fuente de verdad en lugar de `run_state.json`?

**Respuesta:** El log es **append-only e inmutable**; `run_state.json` es una **vista derivada regenerable**.

1. **Inmutabilidad con integridad** — `session_log_<run>.jsonl` es append-only. Cada evento lleva un hash encadenado (`prev`), de modo que cualquier edición o borrado rompe la cadena y es detectado por `sesion_log.py integrity`. En cambio, `run_state.json` es un snapshot mutable que cualquiera puede reescribir.

2. **run_state puede sobrevivir a su corrida (huérfano)** — una vista derivada puede "quedar viva" tras terminar el flujo (o tras un crash) y envenenar las respuestas MCP al tratar estado viejo como vigente. Por eso `estado_sesion.py` usa el log como **autoridad para decidir**:
   - último evento `flujo/fin` → corrida terminada → run_state es **huérfano** → candidato a `clean`
   - último evento no-fin (en curso/error) → run_state **vigente**, jamás se borra
   - sin log → **no verificable**, no se borra (no hay certeza)

3. **El log nunca se borra** — `clean` solo elimina run_state*, que son regenerables vía `sesion_log.py state`. El log es la traza histórica; la vista es solo un checkpoint derivado.

En una frase: **depender de run_state como verdad rompería con un solo estado obsoleto; el log encadenado da certeza del ciclo de vida de cada corrida y permite purgar vistas sin riesgo.**

Referencias: `execution/estado_sesion.py:8`, `execution/sesion_log.py:6-7`, `AGENTS.md` (State hygiene).

---

## P2. ¿Qué significa el "mecanismo de Guardia MCP"?

**Respuesta:** Es la **guardia de comparación de mtime antes/después de la corrida** implementada de forma idéntica en los 5 servidores MCP que ejecutan un flujo por `subprocess` y luego leen `run_state.json` (`mcp_analizar_server.py`, `mcp_elaborar_server.py`, `mcp_evaluar_server.py`, `mcp_diagnostico_server.py`, `mcp_docs_server.py`).

- **Problema que resuelve:** el MCP corre el flujo y, al terminar, quiere reportar el estado final. Si lee `run_state.json` sin verificar, puede leer una **vista huérfana** (archivo que sobrevivió de una corrida anterior o que esta corrida nunca llegó a reescribir porque falló antes). Esa vista envenenaría la respuesta como si fuera el resultado actual.
- **Mecanismo** (`mcp_evaluar_server.py:72-96`):

```python
mtime_before = os.path.getmtime(state_file) if os.path.exists(state_file) else None
resultado = subprocess.run(cmd, ...)
if os.path.exists(state_file):
    if mtime_before is not None and os.path.getmtime(state_file) <= mtime_before:
        pass  # NO modificado por esta corrida → vista huérfana, no usar
    else:
        state_data = json.load(open(state_file))
```

- **Veredicto por señal temporal:**
  - `mtime_ahora > mtime_before` → el flujo lo reescribió → pertenece a esta corrida → se lee.
  - `mtime_ahora <= mtime_before` → conserva mtime de otra corrida → huérfano → `state_data` queda vacío (no se reporta).
  - Es la **única señal que vincula temporalmente el archivo al subproceso sin conocer el `run_id` de antemano**.

Referencias: `docs/AGENTE_IA/faq_higiene_estado_sesion.md:75-97`, cualquiera de los 5 `mcp_*_server.py`.

---

## P3. ¿Qué sucede si `mtime_before` es `None` antes de ejecutar el flujo?

**Respuesta:** Significa que **`run_state.json` no existía antes de ejecutar la corrida** (no quedó ninguna vista de un flujo previo).

En la guardia, al ser `None` la condición `mtime_before is not None and ...` se **corta por cortocircuito (siempre falsa)**, así que la rama de "no usar" nunca se ejecuta. El comportamiento resultante:

- Si al terminar el flujo el archivo **ahora existe** → se asume que fue **creado por esta corrida** → se lee como estado vigente y se reporta.
- Si el flujo falló antes de crear el archivo (o no lo genera por diseño) → sigue sin existir → `state_data` queda vacío, como corresponde.

Es el caso grabado en la FAQ: *"Si no existía antes (`mtime_before = None`), se lee si ahora existe (si el flujo lo creó, es de esta corrida)"* (`faq_higiene_estado_sesion.md:93-94`).

Referencias: `mcp_*_server.py` (línea de captura de `mtime_before`), `docs/AGENTE_IA/faq_higiene_estado_sesion.md:91-94`.

---

## P4. ¿`mtime` lleva un registro cronológico de las corridas efectuadas?

**Respuesta:** No. `mtime` es **un único escalar**: la marca de tiempo de la *última* escritura del archivo (campo del inodo, se sobrescribe en cada escritura). No guarda historial alguno.

- Solo responde "¿cuándo se modificó el archivo **por última vez**?" — el dato de corridas anteriores se pierde en cuanto el archivo se reescribe.
- Por eso la guardia MCP no puede contar corridas ni saber cuántas hubo: solo hace una **comparación puntual** `mtime_ahora vs mtime_before` capturado en un instante dado, suficiente para decidir si *esta única* escritura pertenece al subproceso recién lanzado.
- El **registro cronológico real** vive en los logs append-only (`session_log_<run>.jsonl`): cada evento lleva su timestamp, un `run_id` y hash encadenado (`prev`), y ahí sí se puede reconstruir el histórico de corridas e inspeccionar el orden. `mtime` es solo una señal auxiliar instantánea para vincular una escritura a un subproceso sin conocer el `run_id` (`faq_higiene_estado_sesion.md:96-97`).

Referencias: `execution/estado_sesion.py`, `execution/sesion_log.py`, `faq_higiene_estado_sesion.md:91-97`.

---

## P5. ¿Qué valores puede tener `mtime`?

**Respuesta:** En el contexto de la guardia MCP, `os.path.getmtime()` devuelve un **`float`** (segundos de época Unix, usualmente con fracción, p. ej. `1757734290.123456`) o `None` cuando el archivo no existe antes de la corrida:

- **`None`** → el archivo no existía al capturar `mtime_before` (no hay vista previa). Caso P3: cortocircuito que asume que el archivo que aparezca es de esta corrida.
- **`float >= 0`** → marca de tiempo de la *última* modificación (epoch seconds, con precisión subsegunda según el sistema de archivos). En Linux ext4 la resolución es de nanosegundos, pero `getmtime()` la expresa como float.

En la comparación solo hay tres resultados posibles:
- `mtime_posterior > mtime_before` → reescrito por esta corrida → vigente.
- `mtime_posterior <= mtime_before` → mtime de otra corrida → huérfano → no se usa.
- `mtime_before = None` (y ahora existe) → creado por esta corrida → se usa.

No hay otros valores: nunca es cadena, ni lista, ni timestamp "legible"; es un número de segundos de época (o ausencia). El valor concreto no importa para la guardia, solo su **relación de orden** contra el `mtime_before`.

Referencias: `os.path.getmtime` (stdlib), código de captura en los 5 `mcp_*_server.py`.

---

## P6. ¿A qué archivo te refieres cuando dices "el archivo no existía al capturar `mtime_before`"?

**Respuesta:** Al **`.tmp/run_state.json`** — el archivo de estado cuyo mtime mide la guardia MCP. La línea exacta que define esa ruta en los 5 servidores es:

```python
state_file = os.path.join(project_root, ".tmp", "run_state.json")
mtime_before = os.path.getmtime(state_file) if os.path.exists(state_file) else None
```

Ver `mcp_evaluar_server.py:72-73` (y sus equivalentes en `mcp_analizar_server.py:63`, `mcp_elaborar_server.py:72`, `mcp_diagnostico_server.py:57`, `mcp_docs_server.py:72`).

Es el run_state "global" (sin sufijo de run_id) que el flujo reescribe durante la corrida; la guardia captura su mtime **antes** de lanzar el `subprocess` y lo compara **después** para decidir si esa escritura pertenece a la corrida actual. Si no existe al capturarlo (primer uso tras `clean`, o flujo que nunca lo generó), `mtime_before = None`.

Referencias: cualquiera de los 5 `mcp_*_server.py`, `docs/AGENTE_IA/faq_higiene_estado_sesion.md:81`.

---

## P7. ¿Qué es "la guardia" que mencionas?

**Respuesta:** "La guardia" es **el patrón de protección por mtime que viven dentro de cada MCP server** — el bloque de código que decide si un `run_state.json` leído tras la corrida pertenece a esta ejecución o es una vista huérfana de otra. Es exactamente el bloque:

```python
mtime_before = os.path.getmtime(state_file) if os.path.exists(state_file) else None
resultado = subprocess.run(cmd, ...)
state_data = {}
if os.path.exists(state_file):
    if mtime_before is not None and os.path.getmtime(state_file) <= mtime_before:
        pass  # NO modificado por esta corrida → vista huérfana, no usar
    else:
        state_data = json.load(open(state_file))
```

- Su "oficio" es actuar como un **centinela antes de leer**: si el archivo conserva un mtime de otra corrida, impide que ese estado viejo "se cuele" como resultado actual del MCP.
- Está **duplicado idéntico** en los 5 servidores que corren flujos por subprocess y leen el estado global (`analizar`, `elaborar`, `evaluar`, `diagnostico`, `docs`), por lo que en la documentación se designa como **"Guard MCP"** (`faq_higiene_estado_sesion.md:228`) y en la bitácora se le llama "guardia MCP".
- Complementa a `estado_sesion.py`: mientras ese script diagnostica *a posteriori* los huérfanos en `.tmp/`, la guardia actúa *en línea* dentro del flujo MCP para no reportar jamás una vista que no le pertenece.

Referencias: `mcp_evaluar_server.py:72-96`, `docs/AGENTE_IA/faq_higiene_estado_sesion.md:75-97` y `:228`.

---

## P8. ¿Cierto que la limpieza de memoria del agente la hacen `estado_sesion.py` y `bitacoras.py`, ambos en la capa de execution?

**Respuesta:** **Cierto en lo esencial** — ambos son scripts de la capa de ejecución (`execution/`, Layer 3) y ambos cuidan la "memoria" del robot. Pero conviene precisar que **gestionan dos capas de memoria distintas** (así lo documenta el propio `bitacoras.py:5-10`), y que en realidad conforman una **tríada**:

| Script | Capa de memoria que gestiona | Qué hace |
| :--- | :--- | :--- |
| `estado_sesion.py` | **Bajo nivel (datos)** — `session_log_*.jsonl` + `run_state*.json` | Diagnostica y purga (`check`/`clean`) vistas huérfanas/obsoletas en `.tmp/`; nunca toca los logs. **No escribe la traza**: eso lo hace `sesion_log.py` (append-only con hash encadenado). |
| `bitacoras.py` | **Alto nivel (significado)** — `Sessions/YYYY-MM-DD_<tema>.md` | Crea y valida (`nueva`/`check`) la bitácora canónica que guarda el *porqué* (contexto, decisiones del usuario, pendientes), eslabón semántico de la continuidad. |
| `sesion_log.py` *(compañero)* | Bajo nivel (datos) — el log mismo | Escribe los eventos append-only (fuente de verdad) y regenera las vistas (`state`) — es el productor que `estado_sesion.py` inspecciona. |

La distinción clave (del docstring de `bitacoras.py`): lo de bajo nivel es *reproducible e inmutable*; lo de alto nivel guarda la intención del usuario que **no vive en ningún log de ejecución**. Y según `AGENTS.md`, ambos se invocan en el ritual de sesión: `estado_sesion.py check` al abrir, `bitacoras.py nueva --tema` al crear la bitácora del día, y `bitacoras.py check` al cerrar.

Referencias: `execution/bitacoras.py:3-10`, `execution/estado_sesion.py:3-9`, `AGENTS.md` (Know before you act → Session logs / State hygiene).

---

## P9. ¿Cuando el robot termina una tarea guarda información en `.tmp/`?

**Respuesta:** Sí, en la mayoría de los flujos — pero solo **intermedios**, no entregables. Al terminar un flujo quedan en `.tmp/`:

- `run_state.json` (y `run_state_<id>.json`) — vista de progreso multi-paso del flujo.
- `session_log_<run>.jsonl` — traza append-only, fuente de verdad.
- JSONs de análisis específicos por flujo (`analisis_*.json`, `evaluacion_*.json`, `descriptor_*.json`, etc.).

Lo que **no** va a `.tmp/`: los entregables (LaTeX/PDF, informes → `docs/` o `cursos/`), datasets curados (`datasets/curated/`), paquetes HF (`datasets/paquetes/`). Es el principio *"si Python lo necesita temporalmente → `.tmp/`; si el usuario lo necesita → a la nube/deliverable"* (regla de oro del marco). El timing real en los MCP: el propio flujo escribe `run_state.json`, y la guardia MCP decide después si esa escritura es de la corrida actual.

No es automático para *toda* tarea del chat (ediciones, compilaciones puntuales no multi-paso no escriben estado), pero todo flujo orquestado deja su traza.

Referencias: `AGENTS.md` (Output conventions / Intermediates), `docs/AGENTE_IA/faq_higiene_estado_sesion.md`.

---

## P10. ¿Los intermedios de `.tmp/` y los entregables son "la información que llamo archivos"?

**Respuesta:** Sí — y algo más amplio. Tanto `.tmp/` como las carpetas de entregables almacenan **archivos** (secuencias de bytes con nombre y ruta en el filesystem). La división `.tmp/` vs `docs/`/`cursos/` **no es de naturaleza, es de ciclo de vida**:

| | Archivos intermedios (`.tmp/`) | Archivos entregables (`docs/`, `cursos/`, ...) |
| :--- | :--- | :--- |
| Naturaleza | Son archivos | Son archivos |
| Propósito | Regenerables, insumo de paso | Resultado final para el usuario |
| Ciclo de vida | Efímeros (purgables, huérfanos) | Persistentes (se versionan y se comparten) |
| Recreables | Sí (a partir de inputs/directiva) | Generalmente sí, pero son el *deliverable* |

El término genérico **"archivo" en el workspace abarca a todos y a más**: scripts (`execution/*.py`, `flujo_*`), directivas (`*.yaml`), fuentes `.tex`, config (`.env`, `.groq_api_key`), datasets crudos/`curated`, logs, y por supuesto los intermedios y entregables.

Matiz importante: cuando una herramienta del repo dice "archivos" con contexto específico, no se refiere a esto ni a `.tmp/` — por ejemplo `enrutador.py --archivos <rutas>` mide **archivos de entrada** (fuentes a procesar), no los intermedios. La regla de oro del marco sintetiza el destino: *"Si el usuario lo necesita → a la nube; si Python lo necesita temporalmente → `.tmp/`"*.

Referencias: `AGENTS.md` (File Organization → Deliverables vs Intermediates), `.agent/enrutamiento.md` (`--archivos`).

---

## P11. De acuerdo con `estado_sesion.py`, ¿cuál es el único veredicto que permite que `clean` elimine una vista derivada?

**Respuesta:** **`"huerfano"`** — el único. En `estado_sesion.py:245`:

```python
if v["veredicto"] == "huerfano":
    # se borra
```

Los otros veredictos **jamás** se eliminan:

| Veredicto | Significado | `clean` actúa |
| :--- | :--- | :--- |
| `huerfano` | La corrida terminó (`flujo/fin` en el log); la vista sobrevivió. | **Se borra** |
| `vigente` | Corrida sin `flujo/fin` (reanudable o en curso). | No — podría reanudarse |
| `no_verificable` | Sin log append-only; no hay certeza. | No — conserva el archivo por prudencia |
| `corrupto` | run_state sin run_id o JSON inválido (escritura a medias). | No — se reporta como anomalía |

La lógica de por qué solo `huerfano`: el log con `flujo/fin` **certifica** que la corrida terminó y que el run_state ya no es útil; es el único caso con certeza suficiente para borrar sin riesgo. Los otros dos que también cuentan anomalías (`corrupto`, `no_verificable`) se **reportan** pero no se borran porque no hay certeza absoluta.

Referencias: `execution/estado_sesion.py:145-153` (clasificación), `execution/estado_sesion.py:245` (delete), `execution/estado_sesion.py:205-206` (anomalías).

---

## P12. ¿Las memorias de bajo y alto nivel se usan para **cualquier** tarea del workspace?

**Respuesta:** **No.** Ni la de bajo ni la de alto nivel cubren toda tarea. Evidencia del código:

| Memoria | Alcance real |
| :--- | :--- |
| **Bajo nivel — `run_state.json`** | Solo los **flujos orquestados multi-paso**: 13 `flujo_*` lo escriben (`flujo_evaluar_examen.py:34`, `flujo_elaborar_examen.py:34`, `flujo_analizar_imagen.py:39`, `flujo_consultar_docs.py:30`, `flujo_imagen_a_kicad.py:38`, `flujo_libro_a_skill.py:49`, `flujo_repo_a_skill.py:51`, `flujo_curar/empaquetar/publicar_hf`, `flujo_diagnostico.py:33`, `flujo_elaborar_ejercicios.py:32`, `flujo_resolver_skill.py:37`). Ediciones, compilaciones puntuales o comandos one-off del chat **no** escriben estado. |
| **Bajo nivel — `session_log_<run>.jsonl`** | Trazabilidad append-only **no es universal**: solo `flujo_repo_a_skill.py:48` la invoca hoy (`.tmp/` contiene exactamente 1 log, del 2026-09-09). El resto de flujos escriben run_state **sin log** → para `estado_sesion.py` esas vistas serían `no_verificable`. Es una brecha de trazabilidad conocida: los 5 MCP servers leen run_state con la guardia de mtime, pero pocos flujos registran su propio log. |
| **Alto nivel — bitácora** | Granularidad de **sesión**, no de tarea: una `Sessions/<fecha>_<tema>.md` resume todo el día (actividades + decisiones del usuario). Cubre muchas tareas de golpe y solo existe si el orquestador ejecuta el ritual de AGENTS.md (`bitacoras.py nueva` al abrir, `check` al cerrar). |

Conclusión: la memoria automática de bajo nivel está **ligada a flujos orquestados** (y aun así, su log traceable solo lo implementa 1 flujo); la de alto nivel es un **resumen por sesión** que depende de que el agente invoque el ritual. Las tareas simples del chat quedan fuera de ambas capas por diseño.

Referencias: `AGENTS.md` (Session logs / State hygiene), `flujo_repo_a_skill.py:48-71`, `execution/bitacoras.py:5-10`, `.tmp/session_log_*.jsonl` (solo 1 log existente).

---

## P13. ¿Los servidores MCP usan esas memorias?

**Respuesta:** Solo parcialmente, y cada capa de memoria recibe trato distinto:

- **Bajo nivel — `run_state.json`: SÍ la consumen.** Los 5 MCP servers que lanzan su propio flujo (`mcp_analizar`, `mcp_elaborar`, `mcp_evaluar`, `mcp_diagnostico`, `mcp_docs`) **leen** `.tmp/run_state.json` después del `subprocess` **solo si** la guardia de mtime certifica que la escritura es de esta corrida. La usan como insumo para **reportar al caller** el resultado del flujo (puntaje, nivel, `archivo_tex`, `json_tmp`, etc. — p. ej. `mcp_evaluar_server.py:99-109`). No la escriben ellos: la escribe `flujo_*` y el MCP la consume a través de la guardia.
- **Bajo nivel — `session_log_<run>.jsonl`: NO la usan directamente.** La guardia decide por **mtime**, no consultando el log append-only (no conocen el `run_id`). Son la razón de que el log exista como verdad para `estado_sesion.py` *a posteriori*, pero el servidor en sí no lo lee ni lo escribe.
- **Alto nivel — bitácora: NO la tocan.** Los MCP servers jamás escriben ni leen `Sessions/*.md`; ese ritual es exclusivo del orquestador (opencode). El MCP solo ejecuta el flujo y devuelve su resultado.
- **Fuera del circuito:** `mcp_latex_server` y `mcp_sistema_server` no aparecen en el grepping de `run_state` — son herramientas deterministas (compilar/control) sin estado multi-paso; no usan ninguna de las dos memorias.

En una frase: los MCP servers son **consumidores puntuales de la vista de bajo nivel (run_state), mediados por la guardia de mtime**, y están **fuera** de la trazabilidad append-only y de la memoria semántica de alto nivel.

Referencias: `mcp_evaluar_server.py:72-109` (+ equivalentes en los otros 4), `grep run_state → solo 5 mcp_*`, `AGENTS.md` (Session logs).

---

## P14. ¿Qué criterio define a una bitácora como 'Legado' en el sistema de gestión de sesiones?

**Respuesta:** Dos condiciones, la principal es cronológica (`execution/bitacoras.py`):

1. **Fecha anterior a `FECHA_PLANTILLA = date(2026, 9, 11)`** (línea 51). Desde esa fecha las bitácoras deben seguir la plantilla canónica (`PLANTILLA` con `## Tema` / `## Decisiones (usuario)` / `## Actividades` / `## Pendientes`); toda bitácora cuyo nombre comienza con una fecha **anterior** a ese día es "legado transicional" que respetaba otra convención.
2. **Nombre fuera de convención** — si el archivo no matchea `YYYY-MM-DD_<tema>.md`, `periodo` tampoco se mueve de su valor inicial `"legado"`.

Cómo se calcula en `_validar_bitacora` (líneas 120-155):

```python
periodo = "legado"                                # valor inicial
m = re.match(...)                                   # fecha extraída del nombre
if fecha > hoy:  periodo = "reciente" (y se marca "fecha en el futuro")
elif fecha >= FECHA_PLANTILLA:
    periodo = "hoy" if fecha == hoy else "reciente"
# menor que FECHA_PLANTILLA → se queda en "legado"
```

Efecto práctico: las `legado` se **listan informativamente** pero **nunca cuentan como anomalía accionable** (`ok = (not problemas) or periodo == "legado"`), aunque les falten secciones o tengan problemas estructurales. Solo las `hoy`/`reciente` alimentan el veredicto de atención.

Referencias: `execution/bitacoras.py:49-51`, `execution/bitacoras.py:120-155`, `execution/bitacoras.py:154`.

---

## P15. En la arquitectura de sincronización automática, ¿cuál es la responsabilidad de la Capa 2 (Orquestación)?

**Respuesta:** En este flujo específico, la Capa 2 es **`flujo_sync_faq_flujo.py`** (docstring: *"Orquestador... (Layer 2)"*). Su responsabilidad es **decidir cuándo y cuál paso ejecutar**, jamás ejecutar el trabajo determinista ella misma. Concretamente:

1. **Detección del cambio**: compara el hash SHA-256 del `.md` contra `.tmp/faq_flujo_sync.json`; sin cambios termina (código 0); con cambios, continúa la cadena.
2. **Clasificación del diff** (delega en `execution/regenerar_faq_flujo.py --plan`): campos conocidos → vía **determinista**; cualquier otro cambio → vía **semántica** (LLM), con **aviso previo de consumo de créditos OpenRouter**.
3. **Enrutamiento del LLM**: si toca la vía semántica, el tier lo decide `execution/enrutador.py` (descriptor `--task conversion`, tokens medidos), **no el chat** — decisión determinista.
4. **Encadenamiento de la cadena**: `regenerar_faq_flujo.py` (edits quirúrgicos validados) → `compile_latex.py` (2 pasadas a `.tmp/latex_build`) → copia del `.pdf` a `docs/AGENTE_IA/` → `verificar_pdf.py` (guardrail post-compilación).
5. **Guardia de errores**: retry budget máx 3 con fallback cost-aware del enrutador; si se agota → código 5 **sin escribir el `.tex` a medias**; si `--no-llm` y hay cambio estructural → código 3 (aborta, `.tex` intacto).
6. **Estado y cierre**: actualiza `.tmp/faq_flujo_sync.json` (hashes, vía usada, secciones, edits), reescribe el snapshot del `.md` y alerta audible (`alert_user.py`). No modifica (sincroniza, no crea diagramas desde cero).

Resumen: la Capa 2 es el **director de la cadena** (detecta → clasifica → enruta → orquesta → valida → registra), y el *"cómo"* (regex, edits JSON, compilación, verificación bbox) vive en scripts de Capa 3 (`execution/`).

Referencias: `flujo_sync_faq_flujo.py:2-24`, `directives/sync_faq_a_flujo.yaml:19-65`, `directives/sync_faq_a_flujo.yaml:72-96` (edge cases).

---

## P16. ¿Podría decirse que la Capa 2 toma las decisiones de alto nivel: comparar hashes, planear y encadenar ejecución?

**Respuesta:** **Sí** — esa es exactamente la esencia. En el framework (`.agent/AGENT_FRAMEWORK.md`): "Tú decides *cuándo y cuál* ejecutar". La Capa 2 toma las decisiones de alto nivel:

- **Comparar hashes** → *detectar* si hay cambio y decidir continuar o detener.
- **Planear** → clasificar el diff (determinista vs semántico) y decidir qué vía tomar.
- **Enrutar** → decidir el tier del LLM (vía `enrutador.py`, no en el chat).
- **Encadenar** → decidir el orden de ejecución de las herramientas de Capa 3 y validar transferencia entre pasos.
- **Fallar** → aplicar retry budget / abortar sin corromper estado, y registrar.

El matiz de diseño clave (no puntillismo): **comparar hashes es la señal, no la decisión** — el cálculo SHA-256 es determinista y podría vivir en Capa 3; lo que hace de alto nivel la comparación es la *decisión* sobre su resultado (¿continúo? ¿tomo vía determinista o LLM? ¿aborto?). Esa frontera (señal en ejecución, decisión en orquestación) es la que mantiene la fiabilidad: la lógica de negocio no se razona en el chat, se decide en código y se ejecuta en scripts.

Referencias: `.agent/AGENT_FRAMEWORK.md` (Mental Model), `directives/sync_faq_a_flujo.yaml:20-32`.

---

## P17. ¿Al recibir la señal "comparar hashes", el orquestador decide cosas como llamar al LLM o cuándo compilar el PDF?

**Respuesta:** **Sí, exactamente** — y son decisiones visibles en el código (`flujo_sync_faq_flujo.py`). La señal del hash dispara una cascada de decisiones:

1. **¿Hay cambio o no?** (`:96-97`) — hash idéntico → termina (código 0); cambiado → inicia la cadena.
2. **¿Llamar al LLM?** (`:110-115`) — el plan (`regenerar_faq_flujo.py --plan`) decide `llm_necesario`:
   - `no` → vía determinista (regex, 0 créditos);
   - `sí` + `--no-llm` → aborta por diseño (código 3);
   - `sí` → **avisa antes de consumir créditos** y continúa (el tier lo fija el enrutador).
3. **¿Cuándo compilar el PDF?** (`:146, :179-180`) — los resultados de la regeneración dicen `tex_cambiado`:
   - `True` → se compilan las 2 pasadas de `pdflatex`, se copia el `.pdf` y se verifica;
   - `False` → *"El .md cambió pero no impacta el .tex: sin recompilar"* (ahorra compilación y ruido).

O sea, no solo compara: la señal es el **gatillo**; las decisiones (vía, LLM sí/no, compilar sí/no, abortar) las toma el orquestador **entre la señal y la siguiente** — el `how` queda siempre en Capa 3.

Referencias: `flujo_sync_faq_flujo.py:96-97`, `:110-115`, `:146`, `:179-180`.

---

## P18. ¿Qué sucede durante la sincronización si se detecta un cambio estructural pero está activa la bandera `--no-llm`?

**Respuesta:** El flujo **aborta por diseño con código 3** y deja el `.tex` **intacto**. La cadena exacta:

1. **El orquestador lo anticipa** (`flujo_sync_faq_flujo.py:111-112`): con `llm_necesario=True` y `--no-llm` registra el aviso *"[WARN] Cambio estructural detectado pero --no-llm: la sincronización fallará por diseño"*.
2. **`regenerar_faq_flujo.py --no-llm` aborta sin tocar nada** (`execution/regenerar_faq_flujo.py:410-415`, docstring línea 35 — código salida `3`): *"Cambios estructurales detectados pero --no-llm está activo. No se tocó el .tex. Revisa manualmente o relanza sin --no-llm"*. No se llama al LLM → **0 créditos consumidos** (objetivo de la bandera).
3. **El orquestador propaga el error** (`flujo_sync_faq_flujo.py:137-140`): `return {"status": "error", "code": 3, ...}` → **no hay compilación** (el paso de compilar está condicionado a `tex_cambiado`, que aquí nunca llega), no se copia `.pdf` ni se actualiza el estado/snapshot.

Es el edge case documentado en la directiva: *"`--no-llm` con cambio estructural → Abortar con código 3 (el .tex queda intacto) y reportar qué secciones lo requieren"* (`directives/sync_faq_a_flujo.yaml:90-92`). La decisión siguiente queda en manos del orquestador humano: revisión manual o relanzar sin `--no-llm` (con el aviso de créditos).

Referencias: `execution/regenerar_faq_flujo.py:35, 410-415`, `flujo_sync_faq_flujo.py:111-112, 127-128, 137-140`, `directives/sync_faq_a_flujo.yaml:90-92`.

---

## P19. ¿El comportamiento `--no-llm` (abortar con código 3) ocurre **por la inmutabilidad del log**?

**Respuesta:** **No.** Son mecanismos distintos que comparten filosofía, pero no causalidad:

| | Inmutabilidad del log | Aborto `--no-llm` |
| :--- | :--- | :--- |
| **Qué protege** | La traza del run (`session_log_<run>.jsonl`: append-only + hash `prev`). | El **`.tex` y el presupuesto** del usuario en el flujo de sync. |
| **Artefacto** | `.tmp/session_log_*.jsonl` (garantiza que nadie reescriba el historial). | `docs/AGENTE_IA/faq_..._flujo.tex` (que nunca quede a medias). |
| **Origen** | Trazabilidad inspirada en dsh (`sesion_log.py:6-7`). | **Regla de autorización + atomicidad** de la directiva de sync (`sync_faq_a_flujo.yaml:90-92`): "no usar el LLM sin permiso" y "nunca escribir el .tex a medias". |
| **Capa** | Higiene de estado de sesión (bajo nivel). | Orquestación de un flujo concreto (Layer 2). |

Lo que realmente dispara el código 3 es una decisión de negocio del flujo de sync: `--no-llm` = *"cero créditos aunque el cambio lo requiera"* → como no está autorizado a llamar al LLM y no puede completar la síntesis, **cierra en falso** (fail-closed) dejando el `.tex` intacto. Es la misma lógica del caso `--no-llm` documentado en el edge case, no un efecto de la cadena de hashes.

**Donde sí interviene la inmutabilidad/log** es en una pregunta vecina pero distante: que `clean` de `estado_sesion.py` solo borre vistas con veredicto `huerfano` (certificado por `flujo/fin` en el log). Ahí el log sí es la autoridad. En P18, en cambio, el log ni se consulta: el aborto es previo y de autorización.

Conclusión: comparten el *espíritu* (conservador, sin estado a medias, sin efectos no autorizados), pero son **guardas independientes** sobre artefactos distintos.

Referencias: `execution/sesion_log.py:6-7` (inmutabilidad), `directives/sync_faq_a_flujo.yaml:90-92` (aborto), `execution/estado_sesion.py:245` (dónde el log sí es autoridad).

---

## P20. ¿Entonces el aborto `--no-llm` (código 3) ocurre porque "la decisión queda en manos del orquestador humano"?

**Respuesta:** Sí, con una precisión: el aborto **es el mecanismo** que deja la decisión al humano, no algo distinto a la decisión. La cadena de escalamiento:

1. **Layer 3** (`regenerar_faq_flujo.py --no-llm`) no puede completar (cambio estructural sin autorización de créditos) → **cierra en falso** (fail-closed, código 3).
2. **Layer 2** (`flujo_sync_faq_flujo.py`) propaga el error y **se detiene** — no intenta arreglar con lógica propia.
3. **El agente/orquestador** detecta el fallo y **escala al humano**. Esto es *escalamiento*, no *retry*: el retry budget (máx 3) es para fallos de servicio (429, edits inválidos); aquí no hay fallo de servicio sino **decisión de política** (¿gastar créditos o no?).
4. **El humano decide** una de las salidas del edge case de la directiva (`sync_faq_a_flujo.yaml:90-92`): revisión manual, relanzar sin `--no-llm` (con aviso de créditos) o abandonar.

En términos del framework: el código 3 **es la decisión ejecutada de "no actuar sin autorización"** (fail-closed), no una renuncia a decidir. Y el destinatario natural de la siguiente decisión es el humano precisamente porque el agente **no gasta créditos por su cuenta**: el costo y el "revisar a mano" son materias de política, no de algoritmo.

Referencias: `directives/sync_faq_a_flujo.yaml:90-92`, `.agent/AGENT_FRAMEWORK.md` (Retry budget → "Luego, escálalo al usuario").

---

## P21. ¿Cuál es el propósito del "Invariante Geométrico" durante la edición quirúrgica del LLM?

**Respuesta:** **Preservar la estructura del diagrama mientras se permite solo el cambio de contenido.** El invariante es el chequeo determinista post-edición en `execution/regenerar_faq_flujo.py:439-446`:

```python
# Invariante de geometría: mismo número de nodos en el bloque
n_antes = block.count("\\node[")
n_despues = nuevo_block.count("\\node[")
if n_antes != n_despues:
    raise RuntimeError("El LLM alteró la geometría del bloque... Abortando sin escribir.")
```

**Por qué importa el número de `\node[`:** en estos diagramas ISO 5807 el **significado vive en la tabla "Leyenda de etiquetas"**, no en la geometría. Cada símbolo (`T`/`P`/`D`/`E`/`A`/`N` + número) es un id de nodo cuya explicación está en la tabla. Si el LLM añadiera/borrara nodos, coordenadas, estilos o IDs, la geometría dejaría de corresponder con la leyenda y el diagrama se rompería visual y semánticamente (y forzaría recompilación maliciosa).

**Propósito concreto — triple defensa:**
1. **Soft layer (prompt):** reglas invariables del system prompt (`:276-281`) — *"NO modifiques la geometría: ni coordenadas, ni estilos `\node[...]`, ni el número de nodos, ni los nombres de nodo, ni etiquetas (T1, P1...)"*; solo tabla de leyenda, párrafos explicativos y textos de nodo.
2. **Hard layer (tokens):** `_edits_validos` rechaza edits cuyo `new` contenga tokens estructurales `_FORBIDDEN_IN_NEW` (`\begin{tikzpicture}`, `\section`, `\begin{document}`, ...) — `:67-68, 331-333`.
3. **Una vez aplicados los edits (el invariante mismo):** aunque el LLM ignore lo anterior, si `n_despues != n_antes` el script **aborta con `RuntimeError` sin escribir** (fail-closed) → el `.tex` nunca queda a medias ni con geometría rota.

En resumen: el invariante es la **garantía determinista de que la edición quirúrgica solo toca significantes (texto), nunca significación estructural del diagrama**; complementa a la autenticidad de `old` único (`_edits_validos`) y a la escritura atómica (`:464-467`). Es el equivalente en Layer 3 de la regla 1 del prompt en la capa probabilística.

Referencias: `execution/regenerar_faq_flujo.py:276-286, 67-68, 320-343, 439-446, 460-468`, `directives/sync_faq_a_flujo.yaml:86-88` (edge case del LLM que altera geometría).

---

## P22. En el guardrail de verificación del PDF, ¿qué se considera un solape de texto reportable?

**Respuesta:** Un par de palabras cuyas cajas de texto (bounding boxes) se solapan **más del 35 % del rectángulo de menor área**. Definición exacta en `execution/verificar_pdf.py`:

1. **Fuente:** `pdftotext -bbox` extrae la caja `(xMin, yMin, xMax, yMax)` de cada palabra, por página.
2. **Pareo:** `_detectar_solapes` ordena las palabras por `x` (después `y`) y, para cada palabra `i`, solo examina pares `j` con `j.xMin < i.xMax` (posible solapamiento horizontal): `:84-88`.
3. **Métrica normalizada:** `_solapa` calcula la **intersección de los dos rectángulos dividida entre el área del rectángulo menor**: `:38-52` → valor en `[0,1]`. Si no hay intersección, es `0.0`.
4. **Umbral:** `SOLAPE_FRACCION = 0.35` (`:32`); se reporta solo si `frac > 0.35` (`:90`): *"la fracción del rectángulo menor que debe quedar solapada"*.

```python
if frac > SOLAPE_FRACCION:
    solapes.append({"a": txt_i, "b": txt_j, "area": round(frac, 3)})
```

**Matices:**
- El umbral usa `>` (no `>=`); al normalizar por el rectángulo menor, una palabra corta (p. ej. una etiqueta) aplastada sobre una grande se reporta incluso si el área absoluta es pequeña — detecta "texto ilegible por montarse" y no solo solapes enormes.
- Cada solape reportado lleva `{pagina, a, b, area}`; la salida total agrega `solapes_total`.
- Son **informativos, no bloqueantes**: solo los `errores` (`!` en el `.log`) ponen `status: error` y exit 1 (`:136`); los solapes se devuelven y el orquestador los registra como `[WARN]` (`flujo_sync_faq_flujo.py:174`). Overfull también es cosmético.

Referencias: `execution/verificar_pdf.py:32, 38-52, 80-93, 127-136`, `flujo_sync_faq_flujo.py:164-177`.

---

## P23. ¿Por qué `flujo_sync_faq_flujo.py` llama a `compile_latex_code` con `clean=False`?

**Respuesta:** Para **conservar el `.log` de pdflatex** hasta que `verificar_pdf.py` lo lea, y solo después limpiar. La cadena temporal es exacta:

1. `compile_latex_code(..., clean=False)` → compila 2 pasadas y deja `.log`, `.aux`, `.out`, etc. en `.tmp/latex_build/` (`flujo_sync_faq_flujo.py:150-152`).
2. `verificar_pdf.py --log .tmp/latex_build/...log` → lee el `.log` y extrae errores (`!`) y overfull (`:110-113`). Si `clean` fuera `True`, el `.log` no existiría y la verificación solo podría detectar solapes (por `pdftotext -bbox`), perdiendo las dos señales clave de calidad de compilación.
3. Solo tras la verificación: `clean_latex_aux_files(str(BUILD_DIR))` → elimina auxiliares (`:170`).

Si `clean=True` se ejecutara dentro de `compile_latex_code`, el `.log` desaparecería antes de ser inspeccionado y no se podrían reportar errores ni overfull del guardrail, que son **la única señal de bloqueo** (errores `!` → código 1, overfull → warn). El flujo firma implícitamente el contrato: **compilar → verificar → limpiar**, en ese orden y nunca al revés.

Referencias: `flujo_sync_faq_flujo.py:144-170`, `execution/verificar_pdf.py:110-113`, `2026-09-11_faq_diagramas_flujo.md`.

---