# Sesión 2026-08-25 — Directiva entrevista_agente (entrevista previa para desarrollar Agentes IA)

**Fecha:** 2026-08-25
**Tema:** Formalizar como flujo de 3 capas la estrategia de "entrevista de requerimientos" antes de desarrollar un Agente IA
**Estado:** Implementado y probado

## Contexto

El usuario trajo una conversación con Gemini (`docs/AGENTE_IA/Entrevista_Previa_para_Agentes_IA.md`)
donde surgió la idea de que el LLM orquestador entreviste al usuario antes de construir un
agente. Se analizó el documento: estrategia sólida (requirements elicitation automatizada),
alineada con la arquitectura de 3 capas, pero con carencias que aquí se corrigieron al
formalizarla: requisitos no funcionales (costo/tier, RAM ≤4 GB, latencia), criterios de éxito
verificables, frontera determinismo/probabilístico explícita, artefacto de salida estructurado
(YAML, no prosa) y acotación de la entrevista.

## Decisiones

1. **Alcance: 3 capas completas** (regla AGENTS.md). La entrevista es conversacional
   (Capa 2 = orquestador); lo determinista es la síntesis/validación del borrador (Capa 3).
2. **Borrador en `.tmp/` primero**, pasa a `directives/<nombre>.yaml` solo con aprobación del
   usuario (deliverable vs intermediate).
3. **6 bloques fijos de entrevista** con IDs estables: `objetivo_alcance`,
   `herramientas_integraciones`, `arquitectura_memoria`, `flujo_ejecucion`,
   `requisitos_no_funcionales`, `fallos_reintentos_exito`.
4. Reglas transversales: distinguir *confirmado* vs *supuesto asumido*, guardar JSON tras cada
   bloque (entrevista retomable), alertar violaciones de guardrails antes de aceptarlas,
   cerrar la entrevista cuando los 6 bloques estén resueltos.
5. **Frase de activación** (acordada por el usuario): "Quiero entrevistar el agente X,
   objetivo: …". Registrada en `metadata.activacion` de la directiva; al detectarla se extraen
   nombre_agente y objetivo_agente y se inicia el step 1 sin re-preguntar.

## Actividades / Artefactos

- **`directives/entrevista_agente.yaml`** (nuevo): SOP completo — inputs (semilla + nombre),
  steps con los 6 bloques y sus preguntas típicas/mínimo a confirmar, expected_outputs,
  6 edge cases (semilla genérica, abandono, contradicciones, bloques incompletos, guardrails,
  JSON corrupto), metadata.
- **`execution/sintetizar_directiva.py`** (nuevo): función pura sin LLM ($0). Valida esquema/
  completitud del JSON de respuestas y genera borrador YAML con las 5 secciones obligatorias +
  metadata + descriptor_enrutamiento validado contra el vocabulario real del enrutador
  (importa FLASH/KIMI/OPUS_TASKS). Exit codes: 0 ok · 1 args/archivos · 2 incompleto (lista
  faltantes) · 3 JSON malformado.
- **`.agent/AGENT_FRAMEWORK.md`**: directiva registrada en "Available Directives".
- Fixtures de prueba en `/tmp/opencode/` (no versionados): completa, incompleta, malformada.

## Verificación

| Caso | Resultado |
|---|---|
| JSON completo → borrador YAML | exit 0; YAML parsea; 5 secciones presentes; descriptor `validacion` validado contra vocabulario ✓ |
| Bloques faltantes | exit 2 con lista exacta de faltantes ✓ |
| JSON malformado | exit 3 ✓ |
| Archivo inexistente / flag inválida / mismatch --nombre | exit 1 ✓ |
| Supuestos en bloque confirmado | reportados en supuestos_pendientes ✓ |

Correcciones durante el desarrollo (self-annealing, 2 iteraciones):
`yaml.safe_dump` no representa OrderedDict → refactor a dicts planos (orden garantizado);
supuestos de bloques confirmados no se recogían → lógica ajustada.

## Pendientes

- Primera ejecución real de la entrevista con un agente concreto para afinar las preguntas
  típicas de cada bloque (refinamiento según `directives/enrutamiento_llm.yaml` → refinement_protocol).
- El borrador generado deja `[BORRADOR]` en optional_inputs y pasos derivados del bloque de
  flujo; revisar siempre antes de aprobar el pase a `directives/`.
- Commit pendiente (el usuario no lo solicitó aún).

## Nota housekeeping

Existe posible duplicado del documento origen: raíz `Entrevista_previa_para_Agentes_IA.md`
vs `docs/AGENTE_IA/Entrevista_Previa_para_Agentes_IA.md`. Resolver en próxima sesión si aplica.
