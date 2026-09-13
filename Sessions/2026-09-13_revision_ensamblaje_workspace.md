# 2026-09-13 — Revisión ensamblaje workspace

## Tema
Revisión del ensamblaje del workspace ELECTRONICA (higiene de estado, guardia MCP, memoria, .tmp).

## Contexto
- El usuario pidió revisar cómo está ensamblado el workspace repasando las piezas de higiene de memoria.
- Dijo que guardáramos cada pregunta+respuesta en un cuestionario markdown en `docs/AGENTE_IA/`.

## Decisiones (usuario)
1. Crear/acumular `docs/AGENTE_IA/cuestionario_2026-09-13.md` con cada pregunta y su respuesta (P1..P23 hasta ahora).
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
- Ritual de higiene ejecutado: `estado_sesion.py check` → ok; `bitacoras.py nueva` (hoy) + `check --today` → ok.
- Verificado: `mcp_evaluar_server.py:72-96` (guardia), docstring de `bitacoras.py` y `estado_sesion.py`, grep `run_state`/`sesion_log` en `*.py`.

## Pendientes
- **(Brecha conocida)** Trazabilidad plana incompleta: solo `flujo_repo_a_skill.py:48` invoca `sesion_log.py`; los otros ~12 flujos escriben run_state **sin** log → sus vistas son `no_verificable` para `estado_sesion.py clean`. Opciones futuras: integrar `sesion_log.py add` (inicio/paso/fin) en los demás `flujo_*` para que la purga tenga certeza.
- Se dio la opción de repasar otras piezas del ensamblaje (MCP↔directivas, ciclo bitácoras) — el usuario puede continuar o cerrar.