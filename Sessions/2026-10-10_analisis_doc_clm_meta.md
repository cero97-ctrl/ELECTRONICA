# 2026-10-10 — analisis_doc_clm_meta

## Tema
Análisis crítico del documento `docs/AGENTE_IA/clm-meta-context-language-model.md`
(Context-Language Models de Meta/UW) y detección de contradicciones con la
arquitectura de 3 capas del repositorio.

## Contexto
- El usuario copió `docs/AGENTE_IA/fuentes/clm-meta-context-language-model.md`
  (entonces en `docs/AGENTE_IA/`; movido en la sesión posterior
  `2026-10-10_protocolo_fuentes_externas.md`) "para
  analizarlo en detalle". El documento se autodenomina *"Manual técnico y
  directiva arquitectónica"* dirigido a un LLM, y propone que el modelo edite
  libremente su propio contexto (Bash como única herramienta, `C_{t+1} =
  ModelEdit(C_t)`).
- Se verificó la fuente real antes de analizar: paper **arXiv 2609.37725,
  "Context Language Models"**, enviado el **29-sep-2026**, de Rulin Shao et al.
  (University of Washington + **Meta Superintelligence Labs** + MIT + Trillium
  Labs). Repositorio: `github.com/facebookresearch/context-language-models`
  (licencia **CC BY-NC 4.0**, no comercial).
- Veredicto sobre la procedencia: el `.md` es un **resumen de segunda mano
  (probablemente generado por un LLM a partir de un video/blog), no una
  especificación**. Es el mismo patrón ya documentado para la nota de FreeCAD
  ("resumen de un video, no una especificación"). **Por decisión del usuario se
  marca como fuente secundaria NO citable: el archivo original NO se modifica.**

## Decisiones (usuario)
1. **Alcance:** formalizar **solo la bitácora de sesión** (no nota comparativa en
   `docs/`, no directiva nueva).
2. **Tratamiento del `.md`:** marcarlo como **fuente secundaria no citable**,
   documentándolo únicamente en esta bitácora; **no se edita el archivo**.
3. **No adoptar CLM** como modelo operativo: viola el espíritu determinista del
   proyecto (se alertó según el guardrail de AGENTS.md antes de proponer nada).
4. **Al cerrar, hacer los commits.**

## Actividades

### Verificación factual (`.md` vs. fuente real)
Fallos de atribución que delatan el origen automático del resumen:
- Autor: el `.md` dice **"Rin Xia et al."** → real: **Rulin Shao** (+12 autores:
  Zettlemoyer, Lewis, Yih, Koh, Ivison, Lambert…).
- Institución: el `.md` dice **"Meta AI"** → real: **Meta Superintelligence
  Labs** (+ MIT y Trillium Labs, omitidos).
- Modelos evaluados: el `.md` dice **"Claude 3.5 Sonnet"** → real: **Claude 4.6
  Sonnet**; modelos usados Qwen3.6-27B / Qwen3.5-9B / GPT-5.6-Sol.

Cifras correctas (coinciden con el paper): BrowseComp-Plus +11,4% con 21,5%
menos FLOPs (53,4→59,4); EdgeBench-12h 59% menos FLOPs; **163 ediciones
manteniendo 6–8K tokens**; Suffix Cache Reuse 35% y solo parche de SGLang;
licencia no comercial; informe OpenAI/Astra 27 summaries ("IGNORE ALL developer
messages").

Cifras distorsionadas o no verificables:
- **9B con RL:** el `.md` lo resume como "+0,4 pp, margen estrecho" →
  real: **28,8% → 42,5% (+13,7 pp; +47,6% relativo)**, empatando un resumen
  *entrenado* (42,1%) con ~39% menos cómputo. El "+0,4 pp" es solo el empate.
- Fila del enjambre de 24h internamente incoherente ("+65%" y "+1,8 pp" con
  "2,6% vs 4,4%"): números de benchmarks distintos recombinados.
- Benchmarks mal etiquetados: el 59% es EdgeBench (no "tipo SWE-bench"); el
  "+36% frente a 128k" confunde con el 35% de Suffix Cache Reuse.
- "No requiere fine-tuning": sobreextiende el zero-shot (el propio texto admite
  que el 9B necesita RL intensivo).
- No verificables: KV-cache 73,9%→29,9% y 7,7x; ejemplo "11 de 12 sellos / 14 de
  18"; "50% de tareas sin editar".
- Colisión de nombre **"ContextBench"**: el del paper (Needle/Sudoku/KV/Log,
  *pilot study* no publicado) ≠ `arXiv 2602.05892` (retrieval en coding agents).

### Contradicciones con la arquitectura de 3 capas
1. **Colapsa Capa 2 y Capa 3:** pone la lógica de decisión ("qué conservar")
   dentro del modelo → anti-patrón prohibido ("la lógica vive en `execution/`").
2. **Rompe reproducibilidad:** "tú decides qué sobrevive" no es función pura del
   descriptor; mismo input → output distinto.
3. **Bash sin restricciones anula la Capa 3:** se salta I/O validadas, retry
   budget (máx 3) y la barrera anti-borrado (`catalogo_disco.validate_destino`).
4. **Mutación vs. append-only verificado:** el repo mantiene
   `session_log_*.jsonl` append-only y lo verifica; `run_state*.json` son vistas
   derivadas purgables. CLM destruye la cadena de auditoría. *Nota:* el propio
   blog del paper recomienda log append-only + archivo editado = **exactamente
   el diseño que ELECTRONICA ya tiene**.
5. **Self-prompt injection:** el `.md` mismo lo lista como riesgo; adoptarlo
   introduciría el canal de inyección que el documento advierte.
6. **Redundancia:** el "notas.txt/plan_agente.md" que propone ya existe como
   `Sessions/` + `estado_sesion.py check` + `run_state`.
7. **Política de hardware:** el beneficio es de servidor/hosted; localmente la
   edición a mitad de contexto invalida el KV cache. Este equipo no entrena (RL
   iría a Colab) y apenas infiere.

Nota cruzada: dsh/Cordis (framework comparado en el repo) usa trayectoria
**append-only** con resume/fork → tanto ELECTRONICA como dsh favorecen
append-only; CLM es una tercera postura mutacional contradictoria con ambas.

### Lo rescatable
- El **diagnóstico** (degradación ~3ª hora, alucinación de memoria, falacia de
  la ventana grande) coincide con la razón de ser de las bitácoras y de las
  auditorías.
- La invariante "conserva datos primitivos verificados; declara la ausencia;
  jamás fabriques plausible" ya rige el repo.
- Conclusión: el **subconjunto seguro de CLM ya está implementado** (log
  inmutable + vista mutable + poda humano-en-el-loop). No hay nada que
  implementar; se descarta la parte no determinista.

## Pendientes
- (Opcional, NO acordado) una directiva `contexto_higiene.yaml` que solo
  formalizaría lo ya existente (bitácora + `estado_sesion.py check`/`clean`),
  sin autoedición por el modelo. Queda a decisión futura del usuario.
- **No se adopta CLM** por violar el determinismo (decisión registrada).
- El `.md` permanece sin cambios; su calidad de "fuente secundaria no citable"
  vive solo en esta bitácora.
- **Reversión (sesión `2026-10-10_protocolo_fuentes_externas.md`):** el `.md` SÍ
  se modificó después (se le añadió una cabecera de procedencia) y se movió a
  `docs/AGENTE_IA/fuentes/`.
