# 2026-09-12 — faq_sync_flujo_automatico

## Tema
Automatizar la sincronización de `docs/AGENTE_IA/faq_higiene_estado_sesion_flujo.{tex,pdf}`
cuando se edita el FAQ fuente `faq_higiene_estado_sesion.md`. Continuación directa de la
sesión `2026-09-11_faq_diagramas_flujo.md` (ver su Anexo 2026-09-12 para el detalle completo).

## Contexto
- La fase 1 (diagramas ISO 5807 con etiquetas T/P/D/E/A/N + tablas *Leyenda de etiquetas*,
  6 páginas, 0 solapes) quedó entregada y verificada por bbox el 2026-09-11.
- El usuario pidió que `.tex`/`.pdf` se actualicen automáticamente al editar el `.md`,
  respetando la arquitectura de 3 capas (directiva + orquestador + execution).

## Decisiones (usuario)
1. Disparo: **comando con detección por hash** (`flujo_sync_faq_flujo.py`; `--watch` opcional).
2. Regeneración **híbrida**: campos conocidos inyectados deterministamente por el script;
   re-traducción semántica vía enrutador determinista + LLM OpenRouter (consume créditos,
   el flujo avisa antes). El `.tex` vigente es la plantilla; nunca se regenera desde cero.
3. Nuevo parámetro `clean=False` en `compile_latex_code` (aditivo, default `True`
   compatible con el MCP) para conservar el `.log` hasta que el orquestador verifique.

## Actividades
- Creados los 3 nuevos módulos (L1 directiva `directives/sync_faq_a_flujo.yaml`; L2
  `flujo_sync_faq_flujo.py`; L3 `execution/regenerar_faq_flujo.py` + `execution/verificar_pdf.py`)
  y el ajuste aditivo en `execution/compile_latex.py`.
- `py_compile` OK; pruebas unitarias de `_edits_validos`/`_aplicar_edits` (old único,
  tokens estructurales prohibidos, invariante `\node[` por bloque) e inyección determinista
  de fecha/modelo/N correctas.
- Baseline real establecido (snapshot + estado + log en `.tmp/`); corridas posteriores con
  `.md` intacto → "Sin cambios en el markdown (hash idéntico)".
- E2E en copias `/tmp` (sin tocar el entregable): cambio semántico en §2 → `llm` → 1 edit
  quirúrgico real aplicado (nota N1 ampliada con la resolución temporal de `time`) →
  compilación 2 pasadas OK → verificación `6 páginas, 0 errores, 1 Overfull (6.79 pt
  cosmético), 0 solapes`. Estado y snapshot reales restaurados tras la prueba.
- Documentación: fila nueva en la tabla "Qué consume créditos" de `.agent/enrutamiento.md`
  y comando nuevo en `AGENTS.md`; restaurados artefactos trackeados de `.tmp/latex_build`
  que un `rm` de limpieza había borrado.

## Actividades (continuación)
- Generado documento técnico `docs/AGENTE_IA/sync_faq_flujo_automatico.{tex,pdf}` (11 páginas)
  que explica el mecanismo de sincronización para estudio: arquitectura de 3 capas,
  cadena E2E TiKZ, clasificación hash/dif/bloques, LLM quirúrgico (routing, prompt system,
  parse/validate/invariante nodos), `clean=False`, guardrail bbox, códigos de salida,
  edge cases, validación, limitaciones. Estilo infográfico replicado (sourcesanspro,
  cajas tcolorbox, TiKZ ISO 5807, listings con `literate` para acentos UTF-8).
- Compilación: 0 errores, 0 solapes, 1 overfull cosmético (4.4 pt); PDF publicado vía
  `cp` a `docs/AGENTE_IA/`. Auxiliares de `.tmp/latex_build` limpiados.

## Pendientes
- Commit del trabajo de la sesión (bitácoras, flujos/scripts/directiva, AGENTS.md,
  `.agent/enrutamiento.md`, `compile_latex.py`, doc nuevo) — no commitado porque el usuario
  no lo pidió.
- Inspección visual humana del PDF (el modelo no tiene visión) sigue pendiente.