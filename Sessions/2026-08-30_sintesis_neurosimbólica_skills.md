# Sesión 2026-08-30 — Skills: Validación neuro-simbólica + reflexión

## Tema
Perfeccionar `flujo_libro_a_skill.py` según `docs/AGENTE_IA/conversacion_agentes_skills.md`:
enriquecer el skill (prerrequisitos, metodologías paso a paso, límites de aplicabilidad,
fórmulas con representación formal Python/SymPy) y añadir una **capa de validación
neuro-simbólica determinista** con bucle de reflexión opcional. Fase 2 (resolver con LLM
usando el skill) queda pendiente para una iteración futura.

## Decisiones tomadas (aprobadas por el usuario)
- **Fase 1 completa + `--reflexion`**. `--validar-estricto` aborta SOLO si se pasa la flag
  (por defecto advierte). Oráculo de validación: **solo sympy** (z3 NO instalado en
  elect_env; se omite con aviso).
- Retry budget respetado: `--reflexion` máx 3.
- Re-síntesis con `--feedback` reutiliza el corpus destilado persistido
  (`<salida>_destilado.txt`), sin destilar de nuevo.

## Actividades
1. **`execution/sintetizar_skill.py`**: +3 references (`metodologias.md`,
   `limites_aplicabilidad.md`, `prerrequisitos.md`); NORMAS de fórmulas (bloque
   ```python sympy + nota "Validez:"); prompts con refuerzo de razonamiento;
   `--feedback` con "CORRECCIONES PENDIENTES"; corpus destilado persistido;
   `_limpiar_salida` (reproducibilidad: elimina SKILL.md+references/ previos).
   - **Fixes de robustez JSON/YAML** (causa raíz, no prompt):
     - `_sanear_json()`: repara trailing commas y **escapes crudos** (`\Omega` →
       `\\Omega`) antes de `json.loads` (`extract_json_from_response`).
     - `_normalizar_frontmatter()`: re-emite `name`/`description` con comillas YAML
       (el LLM ponía `:` en la description → "mapping values are not allowed here").
2. **`execution/validar_skill_formulas.py`** (NUEVO, determinista, 0 créditos): extrae
   bloques ```python/sympy/py, valida sintaxis (ast), seguridad de imports
   (veta os/subprocess/eval/exec, `--solo-ast` sin ejecución) y ejecución en sandbox
   con sympy y timeout (default 5s). Reporta `estructuras` presentes/faltantes.
   Exits: 0 ok / 1 args / 2 sin SKILL.md / 3 con bloques inválidos.
3. **`flujo_libro_a_skill.py`**: nuevo **Paso 4 (validación)**; flags
   `--validar-estricto` y `--reflexion N`; bucle re-síntesis→revalidación;
   `state.validacion_skill`; renumeración (total = 5 + latex? + dry_run?); helper
   `_msg_fallo` para exponer stderr/raw_output de subprocesos fallidos (antes se
   escondía el mensaje real).
4. **`directives/libro_a_skill.yaml`**: 8 pasos, optional inputs nuevos, expected
   output `validacion_skill`, 13 edge cases (bloques inválidos, faltantes, sympy/z3
   ausentes), `execution/validar_skill_formulas.py` en scripts.
5. **`execution/generar_latex_skill.py`**: `\section*{<reference>}` por archivo.
6. **Verificación determinista (0 créditos)** del validador: fixtures válido, sintaxis
   rota, `import os`, error runtime, `eval`, sin refs, `--solo-ast`, exits 1/2/3 y
   timeout → todos correctos. Unit tests de `_sanear_json` y `_normalizar_frontmatter` OK.
7. **E2E en vivo (dry-run, corpus pequeño `ejemplo_bjt_divisor_tension.pdf`)**: flujo
   completo con reflexión. Síntesis sin fallos tras los fixes de JSON/YAML. **Paso 4
   detectó 9/11 bloques inválidos → reflexión re-sintetizó con feedback → 9/11
   válidos (2 sympy superaron el timeout de 5s)**. Reporte LaTeX compilado (secciones
   por reference). Saldo OpenRouter: $8.15 → $7.51 (uso $2.33).

## Hallazgos
- El LLM produce bloques sympy **no autocontenidos**: `sp` sin importar, `R1` sin
  definir (fallan al ejecutarse en intérprete limpio). La validación por-bloque en
  sandbox fresco es la señal correcta; el bucle `--reflexion` los corrige.
- El ensamblaje del **libro completo** (452 págs, 400K tokens → 28 chunks → corpus
  destilado de 107 KB) es lento (≈25 min de destilación) y la Fase 2 (estructura)
  roza el budget de salida de 8192 tokens, con riesgo de truncado. Pendiente: subir
  `OPENROUTER_MAX_TOKENS` o particionar el ensamblaje por reference para libros grandes.

## Pendiente
- Fase 2 del diseño (`conversacion_agentes_skills.md`): flujo "resolver con LLM usando
  el skill" (RAG sobre references).
- Ensamblaje escalable para corpus masivos (ver Hallazgos).
- Decidir si instalar `z3-solver` para validación SMT de condiciones de borde,
  y si el Aviso de estructuras faltantes debe ser bloqueante vía directiva.
- E2E del libro completo (452 págs) con la validación nueva (≈25–40 min, +$0.5–1).
  **Plan (decisión del usuario 2026-08-30): probar mañana al cargar créditos a
  OpenRouter. Saldo al cierre: $7.51 (web $7.44). Auto top-up activo: +$5 cuando
  el saldo baja de $3 (umbrales del monitor actualizados a warn=$3.50, alert=$3.10).**

## Commit
- `flujo_libro_a_skill.py`, `execution/sintetizar_skill.py`,
  `execution/validar_skill_formulas.py`, `execution/generar_latex_skill.py`,
  `directives/libro_a_skill.yaml`, este log.
- Excluido: `.tmp/run_state.json`, `.tmp/*` (intermedios), `docs/SKILL/bjt_divisor_test/`
  (artefacto de prueba, eliminado).