# FAQ — Higiene de Estado de Sesión y Eslabón Semántico

Fecha: 2026-09-11

Preguntas y respuestas sobre la arquitectura de higiene de estado implementada en
tres commits:

| Commit | Tema |
| :--- | :--- |
| `80ff0ec` | Higiene de Estado de Sesión — `execution/estado_sesion.py` y guards en los 5 MCPs |
| `3446db4` | Eslabón semántico — `execution/bitacoras.py` (nueva/check) |
| `7dab0bb` | Documento LaTeX `docs/AGENTE_IA/higiene_estado_sesion.tex/.pdf` |

Artefactos cubiertos: `execution/estado_sesion.py`, `execution/bitacoras.py`,
`execution/sesion_log.py`, `directives/trazabilidad_sesiones.yaml`, `AGENTS.md` y
los servidores MCP (`mcp_*_server.py`).

---

## 1. Estado e inmutabilidad

### ¿Los logs append-only son la fuente de verdad inmutable?

Sí, por diseño estructural (`execution/sesion_log.py`):

- **Append-only en código**: `add()` abre el archivo en modo `"a"` (solo añade
  líneas; nunca sobrescribe ni edita). `sesion_log.py:134`.
- **Cadena de hashes SHA-256**: cada evento guarda `prev` = hash de la línea
  anterior. Editar, borrar o reordenar rompe la cadena y `integrity` lo detecta.
- **Secuencia `seq`**: debe ser contigua (1, 2, 3...); toda pérdida/duplicación
  es detectable.
- **Marca `"append_only": true`**: exigida por `integrity`.

Contraste con `run_state.json`: el log es *criptográficamente encadenado*
(cualquier edición es detectable), mientras que `run_state.json` es un JSON plano
que se sobrescribe sin rastro. Por eso el log es **fuente de verdad** y el estado
una **vista derivada**.

### ¿Es un blockchain?

Comparte el mecanismo central (*hash chain*: cada registro encadena el hash del
anterior → manipulación detectable), pero no es una blockchain:

| Aspecto | Log de sesión | Blockchain |
| :--- | :--- | :--- |
| Estructura | Hash-chain simple | Hash-chain + merkle trees |
| Escritura | Un solo escritor (el flujo) | Múltiples nodos descentralizados |
| Consenso | No | PoW/PoS |
| Motivación del atacante | Baja | Alta |
| Propósito | Trazabilidad/auditoría local | Valor transferible sin terceros |

Es una aplicación del mismo primitivo de hash-chaining, sin descentralización,
consenso ni incentivos. *Tamper-evident* sí; blockchain propiamente, no.

---

## 2. Guardia MCP

### ¿Por qué se descartó `flujo/fin` como guardia para validar `run_state.json`?

Porque responde a una pregunta equivocada. El guard necesita **identidad**
("¿este estado pertenece a la corrida que acabo de lanzar?") y `flujo/fin` es un
evento de **ciclo de vida**. Aparece en ambos casos opuestos:

- Caso huérfano: run de hace 1h terminó `flujo/fin`, dejó su estado sin limpiar
  → con `flujo/fin`, estado = basura.
- Caso legítimo: el flujo recién lanzado terminó *bien* → también emite
  `flujo/fin` → estado = válido y necesario para responder.

Si el criterio fuera "hay `flujo/fin` → descartar", se descartaría el estado
legítimo — exactamente el que el MCP lee *después* de que el flujo termina.
`flujo/fin` sí sirve para `resume()` (reanudabilidad), pero no para decidir a
quién pertenece una vista.

### ¿Qué mecanismo asegura que el `run_state.json` leído pertenece a la corrida actual?

**Comparación de mtime antes/después de la corrida** (`mcp_evaluar_server.py:72-96`,
idéntico en los otros 4 servers):

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

- `mtime_ahora > mtime_before` → reescrito durante esta corrida → pertenece a ella.
- `mtime_ahora <= mtime_before` → conserva mtime de otra corrida → no se reporta.
- Si no existía antes (`mtime_before = None`), se lee si ahora existe (si el
  flujo lo creó, es de esta corrida).

Es la única señal que vincula temporalmente el archivo al subproceso sin conocer
el `run_id` de antemano.

---

## 3. estado_sesion.py

### ¿Qué hace `clean` ante un archivo `no_verificable`?

**No actúa**: lo deja intacto y ni siquiera lo lista. En `estado_sesion.py:245`
solo se borra si `veredicto == "huerfano"`:

```python
if v["veredicto"] == "huerfano":
    ... ruta.unlink(...)
```

`no_verificable` = no hay log para el `run_id` → falta de certeza sobre si la
corrida terminó. Principio conservador: **"borro solo con certeza"**. `huerfano`
→ borra; `vigente` y `no_verificable` → conserva; `corrupto` → conserva y reporta.

### Si `check` detecta `deepseek-v4-pro`, ¿cuál es el veredicto?

**El modelo no determina el veredicto** (`estado_sesion.py:139-153`): solo añade
el campo informativo `modelo_obsoleto` / `advertencia`. El veredicto de la vista
es siempre función del log:

| Log | Veredicto | Campo extra |
| :--- | :--- | :--- |
| termina en `flujo/fin` | `huerfano` | `modelo_obsoleto` |
| en curso/error/vacío | `vigente` | `modelo_obsoleto` |
| ausente | `no_verificable` | `modelo_obsoleto` |

La advertencia **no incrementa `anomalias`** (solo `huerfano`/`corrupto` lo hacen)
ni activa borrado. El modelo obsoleto es una señal de atención ("reanudar con este
modelo fallaría"), no un criterio de limpieza. En el caso real detectado ambos
coincidían: se borró por `huerfano`, no por el modelo.

---

## 4. bitacoras.py y la directiva

### ¿Cuál es la función del subcomando `nueva` de `bitacoras.py`?

Crear la bitácora canónica de la sesión de HOY desde una plantilla. Genera el
nombre `Sessions/YYYY-MM-DD_<slug>.md` (slug ASCII con transliteración de
acentos), escribe las 5 secciones (`## Tema`, `## Contexto`,
`## Decisiones (usuario)`, `## Actividades`, `## Pendientes`) y **nunca
sobrescribe** (si ya existe, devuelve `ya_existia`). Emite JSON determinista:
`{"status":"ok", "archivo":..., "creada":bool, ...}`.

Es el punto de entrada del eslabón semántico: centraliza formato canónico,
nombrado consistente y no-destrucción → el archivo resultante cumple lo que
`check` exigirá al cierre.

### ¿Qué diferencia una bitácora `reciente` de una `legado`?

El **criterio es de fecha relativa a `FECHA_PLANTILLA` (2026-09-11)**, no de
estructura. Ambas se validan igual; se trata distinto el hallazgo:

| Periodo | Fecha del nombre | Tratamiento de anomalías |
| :--- | :--- | :--- |
| `hoy` | == hoy | Accionable → afecta veredicto/exit code |
| `reciente` | entre `FECHA_PLANTILLA` y hoy, o futura | Accionable → afecta veredicto/exit code |
| `legado` | antes de `FECHA_PLANTILLA` | `ok` forzado a `True` → solo informativo |

`legado` = escritas con otra convención (por eso las 33 antiguas reportan faltas
de `## Decisiones (usuario)` sin activar alertas). Reescribirlas sería falsificar
historia. `reciente` = escritas ya con la plantilla vigente → incumplirla es una
anomalía real a corregir antes de cerrar.

### ¿Qué campo indica si existe una bitácora para la fecha actual?

`sesion_hoy.hay_bitacora` (booleano), dentro del payload de `check`:

```python
"sesion_hoy": {
    "fecha": hoy.isoformat(),
    "hay_bitacora": bool(hoy_bitacoras),
    "archivos": [...],
}
```

Filtra por prefix del nombre (`startswith("YYYY-MM-DD")`), sin importar el tema
del slug. Es la señal que alimenta `veredicto_global`: si es `false` y no hay
anomalías estructurales, el veredicto es `"atencion"` (día sin bitácora).

### Según la directiva, ¿qué hacer si no se escribió la bitácora semántica al cerrar la sesión?

Edge case en `directives/trazabilidad_sesiones.yaml:137-148`. La recuperación es
**obligatoria y correctiva antes de cerrar**:

1. Ejecutar `python3 execution/bitacoras.py check` — si reporta *falta de
   bitácora del día* o *secciones vacías* (hoy/reciente), la sesión no debe cerrar
   así.
2. Corregir: `bitacoras.py nueva --tema "<tema>"` si falta, rellenar las secciones
   semánticas, y revalidar con `check`.
3. Las bitácoras `legado` (antes de 2026-09-11) están exentas: informativas, no se
   reescriben.

Razón: `check` es la señal, la remediación es rellenar/revalidar; el defecto no es
cosmético porque el contexto semántico es irrecuperable una vez cerrada la sesión
(no se regenera desde ningún log).

### ¿Qué información reside EXCLUSIVAMENTE en `Sessions/`?

El **contexto semántico** — lo que ningún log de ejecución puede capturar:

1. El POR QUÉ de las decisiones (sobre todo las del usuario: sección
   `## Decisiones (usuario)`).
2. Lo que se descartó y por qué (p. ej. la primera versión del guard MCP con
   `flujo/fin`).
3. Intenciones y matices del usuario (no caben en un `datos` JSON de vocabulario
   controlado).
4. Reglas y aprendizajes derivados (el razonamiento original antes de codificarlo
   en directivas).
5. Pendientes acordados + su contexto (a quién pertenecen, por qué quedaron
   abiertos).

Línea divisoria: bajo nivel = datos reproducibles (log + run_state); alto nivel =
significado (Sessions/). Sin bitácora, esa información se pierde definitivamente.

---

## Referencias cruzadas

| Artefacto | Ruta | Puntos clave |
| :--- | :--- | :--- |
| `sesion_log.py` | `execution/sesion_log.py` | `add()` append-only :134; `integrity` :237; vocabulario `TIPOS_EVENTO` :54 |
| `estado_sesion.py` | `execution/estado_sesion.py` | veredictos :123-154; `clean` solo `huerfano` :245; modelo obsoleto :139 |
| `bitacoras.py` | `execution/bitacoras.py` | `FECHA_PLANTILLA`; `nueva`; `check`/`sesion_hoy` |
| Directiva | `directives/trazabilidad_sesiones.yaml` | edge cases huérfano :126 y bitácora sin escribir :137 |
| Guard MCP | `mcp_evaluar_server.py` (y 4 servers más) | `mtime_before`/comparación :72-96 |
| AGENTS.md | raíz | reglas "State hygiene" y "Session logs (continuity)" |
| Documento LaTeX | `docs/AGENTE_IA/higiene_estado_sesion.tex/.pdf` | versión ampliada del diseño (9 páginas) |