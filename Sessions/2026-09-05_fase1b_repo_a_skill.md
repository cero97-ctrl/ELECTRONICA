# 2026-09-05 — Fase 1b: skill de referencia de código/API a partir de un repositorio

## Tema
Diseño e implementación de la variante **repo→skill** de la Fase 1: convertir un
repositorio GitHub o directorio local en un skill global de referencia de código/API
(perfil `referencia_codigo`), en lugar del perfil "libro con fórmulas SymPy" de la
Fase 1 original.

## Contexto / decisiones previas
- El usuario confirmó: (1) acepta URL de GitHub + ruta local; (2) filtrado de archivos
  opción A (docs+código por defecto) extensible con `--incluir`/`--excluir` globs;
  (3) skill de "referencia de código/API" — cómo el repo resuelve problemas y aplicar la
  metodología en el workspace.
- Camino A aprobado: extender `sintetizar_skill.py` con `--perfil libro|referencia_codigo`
  (default libro intacto) en vez de un script gemelo.

## Actividades
1. **`execution/extraer_repo_github.py`** (nuevo, determinista, 0 créditos): clona
   `--depth 1` URLs GitHub o usa directorio local; filtra por extensión saltando
   `.git/node_modules/vendor/build/venv/__pycache__`; `--incluir`/`--excluir` globs,
   `--max-archivos`/`--max-bytes`; concatena a `texto_completo.txt` con cabeceras
   `=== ARCHIVO: <ruta> ===` + `indice.json` (incluidos/excluidos, árbol ASCII).
2. **`execution/sintetizar_skill.py`**: flag `--perfil`. Nuevos prompts por perfil
   (`_prompts_chunk_codigo`, `_ejemplo_json_codigo`, `_normas_contenido_codigo`).
   Esquema API: api/patrones/ejemplos/configuracion/prerrequisitos/glosario. Reutiliza
   `_find_balanced_json` y saneo de frontmatter.
3. **`execution/validar_skill_formulas.py`**: flag `--perfil`. En `referencia_codigo`:
   sintaxis→`observacion` (no bloquea), seguridad→solo riesgo de Sistema
   (`_escaneo_peligro_sistema`: os/sys/subprocess/socket/ctypes/open/eval/exec...),
   NUNCA ejecuta en sandbox (el paquete del repo no está instalado). Convierte los
   falsos positivos del perfil libro (74 bloques) en 0 errores conservando protección real.
4. **`flujo_repo_a_skill.py`** (nuevo, orquestador): espejo de `flujo_libro_a_skill.py`
   pero con `--repo`, `--incluir`/`--excluir`, paso 1 → `extraer_repo_github.py`, paso
   4 → `sintetizar_skill.py --perfil referencia_codigo`, paso 5 → validador con perfil.
5. **`directives/repo_a_skill.yaml`** (nuevo, SOP): 8 pasos, 8 edge cases.
6. **Tests** `test_extraer_repo.py` (19 ejes de extracción + validador perfil código):
   37 asserts en total, todos pasan, 0 créditos.
7. **AGENTS.md Commands**: documentados `flujo_libro_a_skill.py` y `flujo_repo_a_skill.py`.
8. **Manual** `docs/AGENTE_IA/fase1b_repo_a_skill.md`.

## Smoke test E2E (consumió créditos, usuario autorizó repo pequeño sugerido)
- Repo: `https://github.com/pallets/itsdangerous` (~32 archivos, 22.5K tokens).
- Extracción: ✅ 32 incl / 8 excl, 91396 chars, ~22511 tokens.
- Enrutador: ✅ tier=deepseek, `deepseek/deepseek-v4-pro`.
- Síntesis (perfil referencia_codigo): ✅ SKILL.md + api/patrones/ejemplos/configuracion/
  prerrequisitos/glosario. Sin formulas/metodologias (correcto para el perfil).
- Validación: ✅ exit 0, 0 errores, estructuras API completas. Oráculo sympy 1.14.0.
- LaTeX: ✅ compilado, `docs/SKILL/pallets_itsdangerous/{tex,pdf}`.
- El skill NO se instaló (dry-run): quedó en `.tmp/skill_pallets_itsdangerous/`.

## Fallo encontrado y corregido
- Bug en el 1er refactor de `_llm_chunk`: al extraer los prompts a funciones
  `_prompts_chunk_libro/_prompts_chunk_codigo` no pasaba el `chunk` → `NameError:
  name 'chunk' is not defined` en la síntesis (antes de llamar a la API, sin gasto).
  Corregido pasando `chunk` como parámetro.

## Hallazgo de diseño (importante)
- El validador neuro-simbólico "libro" (solo math/sympy/fractions + ejecución en
  sandbox) es **semánticamente incorrecto** para un skill de API: los ejemplos importan
  legítimamente el paquete del repo (`from itsdangerous import ...`) y los snippets de
  firmas no son programas completos. Se resolvió con el perfil en el validador
  (riesgo de Sistema bloquea; el resto observa). Documentado en §5 del manual.

## Costo
- Síntesis de itsdangerous (~22.5K tokens entrada, 2 chunks): del saldo $21.67, coste
  real del smoke test ~centavos (deepseek $0.44/$0.87 por M). No se midió el delta exacto.

## Instalación del skill pallets_itsdangerous (completado 2026-09-06)
- Validación pre-instalación (0 créditos): exit 0, 0 errores, estructuras de API 6/6.
  Las `observacion` son snippets no autocontenidos (esperado en este perfil, no bloquean).
- `python3 execution/instalar_skill.py --origen .tmp/skill_pallets_itsdangerous --nombre pallets_itsdangerous`
  → status ok, 7 archivos copiados a `~/.config/opencode/skills/pallets_itsdangerous/`.
- Frontmatter correcto (name + description con keywords de firma/HMAC/token).
- **Requerido:** reiniciar opencode para que cargue el skill.

## Pendiente
- (Opcional) Estimar coste de la síntesis repo grande y avisar antes (edge case ya cubierto).

## Documentación universitaria (completado)
- Se documentó la Fase 1b en `docs/AGENTE_IA/skill_fases_1_y_2.tex`:
  - Portada: banda de título extiende con "Fase 1b: De Repositorio a Skill de API".
  - Ficha técnica: fila de síntesis de repo (`--perfil referencia_codigo`).
  - Sección 7 nueva dentro de la PARTE I: pipeline E2E, arquitectura 3 capas,
    orquestador, perfil de síntesis, validación adaptativa y resultados E2E
    (`pallets/itsdangerous`).
  - PARTE III: bloque de comandos de la Fase 1b + fila comparativa vs Fase 1/2.
- PDF compilado con `pdflatex` (2 pasadas, exit 0, 0 errores LaTeX; overfull menores
  de tablas). Auxiliares `.aux/.log/.out/.toc` eliminados; solo quedan `.tex` y `.pdf`.
- **No commitado** (espera confirmación del usuario; `.tex` y `.pdf` quedan en
  `docs/AGENTE_IA/` para incluir en un commit posterior).