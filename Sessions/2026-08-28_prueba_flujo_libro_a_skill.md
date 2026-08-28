# Sesión 2026-08-28 — Prueba real `flujo_libro_a_skill` (Primera síntesis LLM)

**Fecha:** 2026-08-28
**Tema:** Primera ejecución real (con consumo de créditos) del orquestador sobre el libro "Circuitos y Dispositivos Electrónicos" (Lluis Prat Viñas)
**Estado:** Completado — skill generado en dry-run, 3 bugs corregidos en el camino

## Contexto

Prueba end-to-end del agente `flujo_libro_a_skill.py` (directiva `libro_a_skill.yaml`) con un libro
real de electrónica de 452 páginas. Pendiente desde la sesión 2026-08-27 (la síntesis LLM real nunca
se había corrido).

## Décisiones del usuario para la prueba

- **Modo:** dry-run (generar sin instalar en global) → revisar antes de instalar.
- **Nombre:** `circuitos_dispositivos_electronicos`.
- **Alcance:** libro completo (no acotar).
- Tema: "Electrónica: dispositivos semiconductores y circuitos analógicos", idioma `es`.

## Caracterización del libro (verificada)

- 452 páginas, 2.5 MB, texto selectable (no escaneado); QuarkXPress→Acrobat 6 (2004).
- Texto extraído: **1 603 651 chars ≈ 400 912 tokens** (~24 chunks @16K). Mi estimación previa
  (152K tok, muestreo de 3 págs) fue una subestimación: la portada/primera página tiene densidad baja.
- Tier enrutado: `deepseek` (`deepseek/deepseek-v4-pro`), decisión determinista del enrutador.

## Bugs encontrados y corregidos (self-annealing)

1. **`EOFError` en entrevista no interactiva** — `confirmar()` en `flujo_libro_a_skill.py` no
   capturaba EOF (a diferencia de `preguntar()`), rompía toda ejecución sin TTY. Corregido con
   `try/except EOFError`. Además el flag "¿Acotar...? (s/N)" tenía default `"s"` (inconsistente con
   la etiqueta); ahora pasa `default="n"` → libro completo en modo no interactivo.
2. **`ModuleNotFoundError: No module named 'execution'`** — `sintetizar_skill.py` importaba
   `from execution.llm_client import ...` dentro de `_llm_chunk`/`_llm_estructura`, que al ejecutar
   el script directo (`python3 execution/sintetizar_skill.py`) deja solo `execution/` en `sys.path`.
   Corregido con el patrón dual de los scripts hermanos:
   `try: from execution.llm_client import ... / except ImportError: from llm_client import ...`.
   (Aplica a los 2 puntos que lo usaban.)
3. **`deepseek-v4-pro` devuelve `content=None`** (fallo crítico, análogo al doc #17 de gemini-3.x):
   con prompts grandes el modelo consume **todo** `max_tokens` en razonamiento interno
   (`reasoning_tokens=2048`, `finish_reason=length`, `content=None`) → `openrouter_chat` lanzaba
   "mensaje vacío" y mataba el flujo de forma impredecible (los chunks pasaban o no según la longitud
   del razonamiento). Verificado empíricamente per-chunk y con 3 mitigaciones:
   - `reasoning={"enabled": False}` → content completo, `reasoning_tokens=0` ✅ (elegida)
   - `reasoning={"effort": "low"}` → aun razona (373 tok)
   - `max_tokens=8192` → funciona pero más costoso por chunk
   Implementado: `execution/llm_client.openrouter_chat(..., reasoning=Optional[dict])` (nuevo parámetro
   vía `extra_body`; default `None` = sin cambio para los demás consumidores) y
   `sintetizar_skill._razonamiento_para(modelo)` que devuelve `{"enabled": False}` solo si
   `"deepseek"` está en el id. Además `_llm_chunk` ganó un **retry de hasta 3** por chunk
   (antes: 1 solo intento, moría al primer `content=None`).

## Resultados de la prueba

- ✅ 4 pasos completados (extracción → enrutador → síntesis → dry-run), `run_state` con
  `steps_failed: []`.
- ✅ Skill: `SKILL.md` (4 KB, frontmatter válido, `name`==carpeta, `description` extensa y en 3ª
  persona con disparadores) + `references/{formulas,tablas,glosario}.md`. `instalar_skill.py --dry-run`
  valida los 4 archivos.
- ✅ Contenido técnicamente sólido para recurso rápido (Leyes de Kirchhoff, Thévenin/Norton, diodos,
  BJT/MOSFET/opamps, transitorios RC/RL, formulario).
- Costo: **$1.20 USD** de usage OpenRouter total de la sesión (diagnósticos + síntesis completa), saldo
  $8.64 al cierre. La síntesis en sí ~$0.7–0.9.

## Pendientes / observaciones

- **Instalar en global** con `python3 execution/instalar_skill.py --origen .tmp/skill_circuitos_dispositivos_electronicos --nombre circuitos_dispositivos_electronicos` (tras revisión del usuario) y luego **reiniciar opencode**.
- `steps_completed` en `run_state` registra solo el paso 1 y el final en dry-run (2/3 no se marcan);
  es cosmético, no afecta el flujo. Posible mejora futura.
- La `description` del skill es una sola línea larga sin comillas en frontmatter: válido en YAML, pero
  si algún día contiene `": "` habría que comillar. OK por ahora.
- Considerar registrar el hallazgo de reasoning de deepseek en `.agent/python.md` (análogo al #17 de
  gemini) para memoria del framework.