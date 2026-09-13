# 2026-09-13 — Revisión ensamblaje workspace

## Tema
Revisión del ensamblaje del workspace ELECTRONICA (higiene de estado, guardia MCP, memoria, .tmp).

## Contexto
- El usuario pidió revisar cómo está ensamblado el workspace repasando las piezas de higiene de memoria.
- Dijo que guardáramos cada pregunta+respuesta en un cuestionario markdown en `docs/AGENTE_IA/`.

## Decisiones (usuario)
1. Crear/acumular `docs/AGENTE_IA/cuestionario_2026-09-13.md` con cada pregunta y su respuesta (P1..P39 hasta ahora).
2. Confirmación de cierre: "todo está perfectamente coordinado" — matizada: la lectura vía guardias MCP está bien ensamblada, pero queda la brecha de trazabilidad plana (ver Pendientes).

## Actividades
- P1: por qué `session_log_<run>.jsonl` es fuente de verdad vs `run_state.json` (append-only + hash encadenado vs vista derivada).
- P2/P3: mecanismo Guardia MCP (mtime antes/después en los 5 MCP servers) y caso `mtime_before = None`.
- P4/P5: mtime no lleva historial; valores posibles (`None` | float epoch).
- P6: `.tmp/run_state.json` es el archivo medido por la guardia.
- P7: "la guardia" = patrón mtime en cada MCP server (Guard MCP).
- P8: `estado_sesion.py` + `bitacoras.py` (tríada con `sesion_log.py`), dos capas de memoria (bajo/alto nivel).
- P9: flujos guardan intermedios en `.tmp/` (run_state, session_log, JSONs).
- P10: intermedios y entregables = archivos (diferencia por ciclo de vida, no naturaleza).
- P11: único veredicto que permite `clean` = `huerfano`.
- P12: memorias no cubren toda tarea — solo 13 flujos escriben run_state; solo `flujo_repo_a_skill` escribe session_log; bitácora es por sesión.
- P13: MCP servers consumen run_state vía guardia de mtime; no usan session_log ni bitácora; `mcp_latex`/`mcp_sistema` fuera del circuito.
- P14 (cierre): criterio 'Legado' de bitácoras = fecha < FECHA_PLANTILLA (2026-09-11) o nombre fuera de convención; no cuentan como anomalía.
- P15 (cierre): Capa 2 del sync automático = `flujo_sync_faq_flujo.py` (detecta por hash, clasifica determinista/semántico, enruta LLM, orquesta cadena, valida, registra estado).
- P16 (cierre): confirmado que Capa 2 toma decisiones de alto nivel — hash = señal, decisión = qué hacer con el resultado.
- P17 (cierre): decisiones concretas tras la señal: ¿LLM? (vía --plan, aviso créditos, --no-llm aborta) y ¿compilar? (solo si `tex_cambiado`).
- P18 (cierre): cambio estructural + --no-llm → aborta código 3, .tex intacto, 0 créditos, sin compilar; decisión al humano (revisar o relanzar).
- P19 (cierre): el aborto no es por la inmutabilidad del log — guardas independientes (traza vs .tex/presupuesto) con misma filosofía.
- P20 (cierre): el código 3 es la decisión de "no actuar sin autorización" (fail-closed) + escalamiento al humano; escalamiento ≠ retry.
- P21 (cierre): Invariante Geométrico en regenerar_faq_flujo.py — mismo nº `\node[` antes/después de edits; aborta sin escribir si cambia; triple defensa (prompt/tokens/chequeo determinista).
- P22 (cierre): solape reportable en verificar_pdf.py = intersección normalizada por rectángulo menor > 0.35 (SOLAPE_FRACCION); informativo, no bloqueante.
- P23 (cierre): clean=False en compile_latex_code conserva el .log para que verificar_pdf.py lea errores/overfull; limpieza posterior con clean_latex_aux_files; orden compilar→verificar→limpiar.
- P24 (cierre): violación del invariante geométrico → RuntimeError no capturado → exit 1 (traceback, stdout vacío); el orquestador propaga code 1. Contrasta con --no-llm (JSON estructurado código 3). Créditos ya consumidos en _llm_edits.
- P25 (hallazgo): el código 5 de sync_faq_a_flujo.yaml:82-84 (fallo LLM/edits inválidos tras reintentos) **NO está implementado**; los 3 caminos (reintentos, edits inválidos, invariante geométrico) terminan en exit 1 por excepción no capturada. Discrepancia directiva↔script → ver Pendientes.
- P26 (opción múltiple): el campo de inyección determinista es el modelo obsoleto (`_RE_MODELO = r"deepseek-[\w.-]+"`, aplicado en `aplicar_campos_conocidos`); FECHA_PLANTILLA y nº antiguas también son deterministas. No: geometría, hashes, descripciones semánticas.
- P27 (opción múltiple): cilindro ISO 5807 = `almacenamiento` (estilo TikZ `cylinder, shape border rotate=90`, `:71-76`); nodo `A*` → .tmp/run_state.json, session_log, bitácoras. No: decisión (rombo), entrada/salida (trapecio), terminador (redondeado).
- P28 (opción múltiple): tamper-evident = cadena de hashes (`prev`=sha256 raw anterior + `seq` + `append_only`) verificada por `integrity` en sesion_log.py:237-271; no es proof (no bloquea escritura), no usa HSM, no cifra.
- P29 (opción múltiple): primer arranque sin snapshot = línea base (sync_faq_a_flujo.yaml:72-76): campos deterministas + se crea snapshot, NO al LLM; código 2 es por .md/.tex inexistentes, no por snapshot.
- P30 (opción múltiple): geometría de palabras = `pdftotext -bbox` (poppler-utils) en verificar_pdf.py:55-65, parseada con _WORD_RE; no vision LLM, ni --geometry, ni sha256sum.
- P31 (opción múltiple): tier elegido por enrutador determinista (`decide(task=conversion, tokens medidos, critico, vision=False)`, regenerar_faq_flujo.py:255-265); tokens = len(corpus)//4 (:431-432); --critico escala a opus; --modelo es override opcional.
- P32 (opción múltiple): SOLAPE_FRACCION=0.35 = umbral de tolerancia de solapes (intersección/rectángulo menor > 0.35 => reportable); ignora solapes accidentales, detecta texto montado.
- P33 (opción múltiple): sección ignorada (front/refs) → `via:"ignorada"`, .tex intacto, hash marcado atendido (estado+snapshot nuevos al cierre); no anomalía, no borra, no regenera vacío.
- P34 (opción múltiple): auto-curación determinista = misma entrada → mismo comportamiento; LLM acotado (edición quirúrgica validada por capas deterministas: token guard, geometría, JSON balanceado); decisiones vía enrutador puro; humanos solo por escalamiento/política.
- P35 (opción múltiple): 'accionable' en bitacoras.py = anomalía de bitácora hoy/reciente que modifica veredicto y exit code (2 si accionables); legado se lista informativo sin contar (ok siempre).
- P36 (opción múltiple): limitación explícita del sync = NO crea diagramas desde cero; requiere plantilla base (.tex inexistente → código 4). Sí soporta todos los símbolos ISO 5807, salida PDF, sin tope de nodos.
- P37 (opción múltiple): `nueva` escribe 5 secciones (Tema/Contexto/Decisiones/Actividades/Pendientes); solo 4 validadas como requeridas (Contexto es "opcional, recomendable").
- P38 (opción múltiple): líneas `!` en .log → verificar_pdf.py marca status=error y exit 1 (única señal bloqueante); sigue reportando solapes/overfull; alerta/notificación es del orquestador.
- P39 (opción múltiple): 'Eslabón Semántico' = memoria de alto nivel (Sessions/*.md: por QUÉ se decidió) que conecta con los logs de bajo nivel; NO es el mapeo md→tex, la jerarquía de capas ni la cadena de hashes.
- Ritual de higiene ejecutado: `estado_sesion.py check` → ok; `bitacoras.py nueva` (hoy) + `check --today` → ok.
- Verificado: `mcp_evaluar_server.py:72-96` (guardia), docstring de `bitacoras.py` y `estado_sesion.py`, grep `run_state`/`sesion_log` en `*.py`.

## Pendientes
- **(Discrepancia directiva↔script, hallazgo P25)** `sync_faq_a_flujo.yaml:82-84` promete **código 5** para fallo LLM/edits inválidos tras agotar reintentos, pero `regenerar_faq_flujo.py` nunca devuelve 5 — los 3 caminos (reintentos `:317`, edits inválidos `:330-333`, invariante geométrico `:443`) terminan en exit 1 por excepción no capturada. Decidir: implementar `return 5` (capturando y mapeando) o ajustar la directiva a la conducta real (código 1).
- **(Brecha conocida)** Trazabilidad plana incompleta: solo `flujo_repo_a_skill.py:48` invoca `sesion_log.py`; los otros ~12 flujos escriben run_state **sin** log → sus vistas son `no_verificable` para `estado_sesion.py clean`. Opciones futuras: integrar `sesion_log.py add` (inicio/paso/fin) en los demás `flujo_*` para que la purga tenga certeza.
- Se dio la opción de repasar otras piezas del ensamblaje (MCP↔directivas, ciclo bitácoras) — el usuario puede continuar o cerrar.