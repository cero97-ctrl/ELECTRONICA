# Sesión 2026-08-27 — Agente `flujo_libro_a_skill` (PDF → Skill global)

**Fecha:** 2026-08-27
**Tema:** Convertir un libro PDF en un skill de agente (referencia rápida) instalado en global
**Estado:** Implementado (determinista probado); síntesis LLM pendiente de corrida real

## Contexto

El usuario preguntó si es posible convertir un libro PDF en un *skill* de opencode. En la
conversación se aclaró que no quería una conversión puntual, sino un **Agente IA reutilizable**
que hiciera ese trabajo: entrevistar al usuario (tema, ubicación, objetivo…), convertir el PDF
en un skill, e instalarlo como skill global. Reutilizable para Física, Matemáticas, Electrónica,
etc., según el proyecto futuro.

## Decisiones

1. **Construir un Agente de 3 capas** (regla AGENTS.md) en el repo ELECTRONICA: directiva +
   orquestador + 3 scripts de ejecución. Solo el **skill generado** se instala en global
   (`~/.config/opencode/skills/<name>/`); el agente generador es versionable en el repo.
2. **Objetivo del skill: referencia rápida** (FAQ/consulta) — conceptos clave, fórmulas, tablas,
   glosario. Con **`references/`** de materiales auxiliares además del `SKILL.md`.
3. **PDFs de texto selectable solamente** — sin OCR (fuera de alcance). Si el PDF es escaneado,
   `extraer_libro_pdf.py` lo detecta por densidad de caracteres y lo rechaza.
4. **Libros completos con chunking** — el texto se parte en chunks deterministas y se destila
   con LLM. Routing determinista vía `execution/enrutador.py` con `--task contexto_masivo`
   (default `deepseek/deepseek-v4-pro`).
5. El skill final **no se autocarga hasta reiniciar opencode** (la config no se recarga en caliente).

## Entrevista del flujo (bloques)

Tema/dominio, ruta del PDF, objetivo (fijo: referencia rápida), nombre del skill (snake_case),
alcance (completo o rango de capítulos/páginas), idioma (default es), confirmación de
instalación en global. Registro progresivo en `.tmp/entrevista_skill_<nombre>.json`.

## Actividades / Artefactos

- **`directives/libro_a_skill.yaml`** (nuevo): SOP — goal, required_inputs (pdf, nombre, tema),
  optional_inputs (idioma, alcance, modelo, sobrescribir, dry_run), steps (entrevista →
  extraer → enrutar → sintetizar → revisión → instalar), expected_outputs, edge cases
  (PDF escaneado, nombre inválido/destino ocupado, costo alto, JSON inválido del LLM,
  entrevista interrumpida, PDF inexistente), metadata + enrutamiento.
- **`execution/extraer_libro_pdf.py`** (nuevo): extracción determinista del texto (pdftotext
  con fallback PyMuPDF), detección de PDF escaneado, métricas (páginas/chars/tokens).
- **`execution/sintetizar_skill.py`** (nuevo): chunking determinista + destilación LLM vía
  `openrouter_chat` (default deepseek). Genera `SKILL.md` (frontmatter name/description válido)
  + `references/*.md`. Usa `_find_balanced_json` (`.agent/python.md`), retry máx 3.
- **`execution/instalar_skill.py`** (nuevo): valida estructura y copia a
  `~/.config/opencode/skills/<name>/`; `--sobrescribir` y `--dry-run`.
- **`flujo_libro_a_skill.py`** (nuevo): orquestador — entrevista ligera, valida PDF, orquesta
  los 3 scripts, state en `.tmp/run_state.json`, alerta audible de éxito/error.

## Pruebas realizadas

- ✅ Sintaxis de todos los archivos (`py_compile`) y validez de la directiva YAML.
- ✅ `extraer_libro_pdf.py`: extrajo `docs/AGENTE_IA/manual_nuevo_proy.pdf` (7 págs, 9250
  chars, ~2312 tokens). PDF sin texto → código 3 (corrección: los páginas vacías disparan
  "sin texto", no el caso escaneado de baja densidad).
- ✅ `instalar_skill.py`: dry-run, nombre inválido (code 1), instalación real (code 0),
  destino ocupado sin `--sobrescribir` (code 3).
- ✅ `sintetizar_skill.py` (funciones puras): `_find_balanced_json`, `_repartir_chunks`,
  `_sanitizar_ref_nombre`, `_validar_frontmatter` (válido/inválido/descoincidencia).
- ✅ `enrutador.py --task contexto_masivo` → tier `deepseek`.
- ✅ Orquestador end-to-end hasta la síntesis (con modelo explícito inválido para no gastar
  créditos): entrevista, extracción y manejo de fallo de síntesis correctos.

## Pendientes

- Ejecución real de la síntesis LLM (consumo de créditos OpenRouter) con un PDF concreto del
  usuario y su aprobación explícita del costo.
- Tras instalar el primer skill real, recordar al usuario que **reinicie opencode**.

## Notas

- La medición de tokens del enrutador debe hacerse sobre el **texto extraído**
  (`texto_completo.txt`), no sobre el PDF binario (que infla la cuenta). Ajustado en el
  orquestador: el tier se resuelve tras la extracción (Paso 2).
- `sintetizar_skill.py` empezó usando el backend `gemini` en la primera versión; se dejó solo
  `openrouter` (necesario para la robustez de extracción JSON vía `openrouter_chat`).
