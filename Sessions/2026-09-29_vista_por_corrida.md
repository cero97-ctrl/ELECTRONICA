# 2026-09-29 — vista_por_corrida

## Tema
P2-1 (colisión de `.tmp/run_state.json`) y P2-2 (`bio_env` en riesgo de purga).

## Contexto
Sesión previa (`2026-09-28_purga_disco_tier_recargable.md`) dejó 4 P1 resueltos y
4 P2 pendientes. P2-2 era urgente (`bio_env` salía como recuperable en el flujo
de disco: 3,5 GB, con 47 paquetes de R justo al lado). P2-1 era la causa
estructural de 1 anomalía constante en `estado_sesion.py`: la vista de estado
tenía nombre fijo, así que dos flujos simultáneos se pisaban la misma vista y el
emparejamiento vista<->log atribuía la vista de una corrida al log de otra.

## Decisiones (usuario)
1. P2-3 (Flatpak, 4,9 GB) NO se toca: requiere `sudo` y está fuera del catálogo.
2. P2-4 (`.git`, 733 MB) NO se toca: el untracking no reduce nada y reescribir
   historia no está autorizado.
3. P2-1 con alcance mínimo: nombre por corrida + escritura atómica. NO se
   rediseña la retirada de vistas, porque los MCP leen la vista DESPUÉS de que
   el subproceso termina (migrar eso sin más diseño rompería los MCP).
4. **NO se reorganizan los scripts de la raíz** (2026-09-29). Se evaluó mover
   `flujo_*.py` a `flujo/` y `mcp_*_server.py` a `mcp/`, y se descartó. Motivo
   del usuario: *"prefiero que todo funcione bien a que se vea mejor
   organizado"*. El inventario cuantificó el riesgo: 29/29 archivos referenciados
   y 6 puntos de rotura **silenciosa**:
   - `flujo_auditar_repo`, `flujo_auditar_sistema`, `flujo_motor_fallback` y
     `flujo_verificar_texto` calculan la raíz con
     `Path(__file__).resolve().parent` (uno lo documenta: *"este flujo vive en
     la raiz del repo"*), así que bajar un nivel les hace buscar `directives/`,
     `.env` y `execution/` donde no están.
   - `execution/auditar_repo.py:308` solo acepta `orchestrator: archivo.py`;
     con `flujo/archivo.py` el regex NO casa y **el guard de flags fantasma
     deja de comprobar** esas directivas sin avisar (verificado: `False`).
   - `telegram_gateway.service` fija `ExecStart` absoluto a `flujo_telegram.py`.
   - 22 flujos manipulan `sys.path` para alcanzar la capa 3.
   La estructura actual YA es la arquitectura de 3 capas (raíz = capa 2,
   `execution/` = capa 3, `directives/` = capa 1), no un desorden. **No
   reabrir esta propuesta** sin evidencia nueva que cambie el balance.

## Actividades

### P2-2 — `bio_env` protegido (hecho y verde)
- `execution/auditar_envs_conda.py`: `PROTEGIDOS_POR_POLITICA` incluye `bio_env`;
  `construir_resultado()` distingue `frio` recuperable de `frios_conservados`.
  Sin esto, el estado pasaba a `atencion` con "no hay frios" y Cold Start leía
  "frío recuperable = bio_env" como permiso de purga.
- `execution/test_auditar_entornos.py`: 73 aserciones, 0 fallos.
- Actualizados `directives/auditar_entornos_conda.yaml` y
  `docs/ENTORNOS_CONDA/README.md`.
- **Deuda detectada**: el parser expone `--proteger`, la directiva dice
  `--protegidos`. No corregido (no afecta a la ejecución; el default ya
  incluye `bio_env`).

### P2-1 — vista por corrida (hecho y verde)
- NUEVO `execution/run_state.py` (capa 3): nombre, escritura atómica,
  validación de `run_id`, snapshot para orquestadores.
- NUEVO `execution/test_run_state.py`: 60 aserciones, 0 fallos.
- Migrados 16 flujos con `save_state` idéntico (mecánica, con verificación de
  sintaxis previa a escribir) + 3 a mano por tener forma distinta:
  `flujo_verificar_texto`, `flujo_resolver_skill`, `flujo_motor_fallback`.
- Migrados los 5 MCP: `mcp_analizar/diagnostico/docs/elaborar/evaluar_server`.
- `run_id_de_la_corrida()` respeta `ELECTRONICA_RUN_ID`.
- Actualizados `directives/trazabilidad_sesiones.yaml`, `auditar_repo.yaml`,
  `mantenimiento_disco.yaml`, `evaluar_practica_laboratorio.yaml`,
  `entrevista_agente.yaml`, `resolver_skill.yaml`, `AGENTS.md`,
  `docs/AGENTE_IA/INSTRUCTIONS.md`, `docs/AGENTE_IA/fase2_resolver_skill.md` y
  el FAQ `faq_higiene_estado_sesion.md`.

### Bugs encontrados de paso (no previstos)
1. **Fuga de estado entre corridas** en `flujo_resolver_skill.py`: `load_state()`
   sin argumentos leía la vista de la corrida ANTERIOR y `estado_ok` la fusionaba
   con la nueva, así que `steps_completed` era la unión de todas las corridas
   que hubieran pasado por el fichero. El flujo terminaba bien e imprimía sus
   pasos: información silenciosamente falsa. Corregido al pasar a vista por
   corrida (verificado con una simulación de dos corridas).
2. **`slug_run_id` con `str.isalnum()`**: acepta `ñ`/`ó` en Python, pero
   `RUN_ID_RE` es `[A-Za-z0-9._-]`. Con `EJM 4-1.pdf` (espacio) el run_id era
   INVÁLIDO y `sesion_log.py` rechazaba el log: la corrida se quedaba SIN
   TRAZABILIDAD en silencio. El nombre del PDF entra en el run_id en
   `flujo_evaluar_examen.py`, así que esto ya pasaba antes de este trabajo.
3. **Slug sin tope de longitud**: un nombre de >120 chars no cabía en
   `RUN_ID_RE`. Ambos los cazó la aserción de invariante
   «`slug_run_id` SIEMPRE produce un run_id válido», no la lectura del código.
4. **`flujo_resolver_skill.py` no importaba `time`**: la línea nueva habría dado
   `NameError`; `--help` pasaba porque sale antes de llegar ahí.
5. **Guard del MCP por mtime, dos veces insuficiente**: con la vista por corrida
   dejó de servir (el fichero fijo ya no se escribe → siempre «no modificado» →
   `N/A` con exit code 0). Y aunque se arreglara, «buscar la vista nueva más
   reciente» atribuye la vista de OTRA corrida si dos flujos corren a la vez.
   Comprobado con un test, no supuesto. Resuelto fijando el `run_id` en el
   punto donde nace (el orquestador).

### Verificaciones
- `test_run_state.py` 60/0 · `test_auditar_entornos.py` 73/0 ·
  `test_barrera_disco.py` 99/0 · `test_auditar_repo.py` 128/0 ·
  `test_auditar_sistema.py` 102/0 · `test_verificar_texto.py` 22/0.
- 18 flujos importan y responden `--help`.
- Corrida real de `flujo_verificar_texto.py`: vista y log comparten `run_id` y
  `estado_sesion.py check` los empareja (`run_state_verificar-texto-*`).
- `flujo_auditar_repo.py --solo texto` → limpio.
- `python3 -m pytest` NO existe en `elect_env`; los tests se ejecutan directos.

### Ítem 2 — sincronización del diagrama del FAQ (2 bugs más, con test)
Al relanzar `flujo_sync_faq_flujo.py` (con gasto autorizado: flash, saldo
$21.05) falló dos veces seguidas. **Ninguno era culpa del LLM**:

6. **La validación de edits estaba FUERA del retry budget.**
   `_edits_validos()` se llamaba en el llamador, no dentro del bucle de
   reintentos de `_llm_edits`. Un `old` desalineado por el modelo (el LLM
   reescribió la tabla de leyenda y las comillas no cuadraron byte a byte)
   tumbaba la corrida entera sin probar los otros dos candidatos que el
   presupuesto ya autorizaba. El guardarraíl hizo bien su trabajo —no aplicó un
   edit dudoso— pero lo hacía con un coste desproporcionado. Movida la
   validación dentro del bucle.
7. **El escalado de modelos mandaba NOMBRES DE TIER, no IDs.** El enrutador
   devuelve `flash`/`deepseek`/`glm`; OpenRouter solo conoce
   `proveedor/modelo`. Toda la cadena de fallback moría con
   `400: 'deepseek' is not a valid model ID` — o sea, el presupuesto se gastaba
   entero sin producir una sola edición. Todos los demás scripts lo pasan
   envueltos en `MODEL_TIERS[...]`; este nunca lo hizo. Corregido en la capa
   correcta (`llm_client.resolver_modelo`, fuente única de IDs, idempotente y
   transparente para `--modelo-explicito`), no en el llamador.
- Tras ambos arreglos: 10 edits LLM, PDF de 6 páginas verificado, 0 solapes,
  geometría preservada (0 nodos añadidos/eliminados), 0 apariciones de `mtime`
  como guardia y 12 de `run_id`.
- NUEVO `execution/test_sync_faq.py`: 7/7. **Verificado que los tests detectan
  los bugs** (se reintrodujeron temporalmente: 4/7, con el diagnóstico correcto
  en cada fallo) — un test que pasa con el código roto no vale nada.

### Corrección de una cifra que yo mismo escribí mal
Al presentar el ítem 1 como "urgente" dije "~4 KB por corrida, sin límite".
Era una estimación sin medir. Medido: **0,24 KB por vista**, ~10,5 corridas/día
≈ 2,5 KB/día ≈ **0,9 MB/año**. Contraste: `.tmp/` pesa 124 MB, de los cuales
**85 MB son un único clon de git**. El "problema" era el 0,002% de `.tmp/`.
Decisión revisada: **no automatizar la retirada**; compra 0,9 MB/año con un
mecanismo de edad que hay que mantener y un riesgo real de romper a los MCP.
Corregido el número en `directives/trazabilidad_sesiones.yaml` con las cifras
medidas y el porqué de no automatizar.

## Pendientes
1. **Retirada de vistas (decisión de diseño, no hecha).** Con vista por
   corrida, cada corrida deja la suya: los `huerfano` de `estado_sesion.py`
   pasaron de 1 a 4 y crecerán ~4 KB por corrida sin límite. `clean` los purga
   (solo los que tienen log con `flujo/fin`), así que es higiene manual. Una
   retirada automática al final del flujo rompería a los MCP, que leen la vista
   después de que el subproceso termina: si se va a automatizar, necesita un
   mecanismo con edad (p. ej. purgar vistas cuyo log terminó hace > 24 h).
2. ~~Diagrama del FAQ desfasado~~ **RESUELTO 2026-09-29.** El usuario autorizó
   la llamada LLM (OpenRouter, tier flash). La re-traducción falló dos veces
   por dos bugs reales, ambos corregidos y con test de regresión:
   (a) el retry budget se saltaba la validación: `_edits_validos()` se
   llamaba una vez, fuera del bucle de `_llm_edits()`, así que un LLM que
   devolvía una edición inválida se reintentaba para siempre con el mismo
   error. Ahora valida dentro del bucle; (b) `llm_client.py` pasaba el **alias**
   del tier (`deepseek`) a OpenRouter en vez del ID real
   (`deepseek/deepseek-v4.1-flash`), que daba `400 deepseek is not a valid
   model ID`. Se añadió `resolver_modelo()` como fuente única. Resultado: 10
   ediciones + 1 resincronización, PDF de 6 páginas, 0 solapes, geometría y
   0 `mtime` intactos, 12 referencias a `run_id`. Coste real: ~$0,004.
3. ~~`directives/sync_faq_a_flujo.yaml` con YAML roto~~ **RESUELTO 2026-09-29.**
   Se entrecomillaron las descripciones de las líneas 15, 17 y 52 (puntos sin
   comillar en texto plano). `yaml.safe_load` abre la directiva y
   `flujo_sync_faq_flujo.py --dry-run` responde `cambio: false` (hash idéntico).
   Nota: `--plan` **no existe** en esa CLI; la opción soportada es `--dry-run`.
4. ~~`--protegidos` vs `--proteger`~~ **RESUELTO 2026-09-29.** La directiva
   usaba `--protegidos A,B`, que el parser de
   `execution/auditar_envs_conda.py` rechaza; el flag real es `--proteger A,B`.
5. ~~Huérfano heredado `.tmp/run_state.json`~~ **RESUELTO 2026-09-29.** Huérfanos
   purgados con `estado_sesion.py clean` (27). Se conservan los 252 logs
   append-only (fuente de verdad) y las 2 vistas `no_verificable`
   (`run_state_sismico.json`, `run_state_motor-fallback-*.json`), que sin log no
   se borran por diseño. `veredicto_global: ok`.
8. **Decisión del usuario (2026-09-29): `.tmp/` se deja intacto.** Los 124 MB son
   casi todos un clon de ~85 MB, no basura de vistas. No purgar sin que lo pida
   expresamente; si algún día lo pide, `flujo_disco.py --check` primero (la
   barrera anti-borrado solo permite la whitelist de `catalogo_disco.py`).
   Cerrado el guard de flags fantasma: `test_auditar_repo` 134/0 y repo real
   con 0 flags fantasma. Todo **sin commit**.
9. **`test_verificar_texto.py` tenía una aserción obsoleta (corregido).** Tras
   P2-1 el estado vive en `run_state_<run_id>.json`, pero el test seguía
   comprobando `.tmp/run_state.json` (nombre fijo legacy que ya no escribe
   nadie): falso rojo permanente. Además su snapshot de limpieza estaba colocado
   DESPUÉS de ~20 invocaciones del flujo, así que cada ejecución del test
   dejaba 8 vistas huérfanas que `estado_sesion.py` reportaba después
   (`veredicto: atencion`). Arreglado: `comprobar_existe_la_vista_por_corrida()`
   valida el patrón `run_state_verificar-texto-*`, el snapshot de vistas se
   toma ANTES de la primera invocación y la limpieza retira solo lo creado.
   Verificado: 22/0, `antes=10 despues=10` vistas (el test ya no ensucia) y la
   suite completa de 9 deja `.tmp` igual. Lección: al migrar el nombre del
   estado, migrar también los tests que lo afirman.
6. `run_state_sismico.json` y `faq_flujo_sync.json` quedan como excepciones
   declaradas (vistas propias de otro dominio, no de la sesión). El test de
   migración las nombra para que la excepción se vea.
7. Cifra de crecimiento corregida: la vista mide ~0,24 KB, no ~4 KB. Medido con
   210 logs / 20 días: ~10,5 corridas/día → ~2,5 KB/día y ~0,9 MB/año. La
   cifra de 4 KB exageraba el riesgo ~16×. `directives/trazabilidad_sesiones.yaml`
   ya corregida; decisión de no automatizar la retirada se mantiene.
