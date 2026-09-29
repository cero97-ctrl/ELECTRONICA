# 2026-09-24 — jev_ai_system_one

## Tema
Jev AI / System One models (TypeSafe AI) — estudio del artículo HF, sin integración.

## Contexto
- El usuario compartió el artículo de HuggingFace (Community Article, autor `sora-2`)
  "Jev AI API & AI Agents: A Practical Guide to Reliable Agent Workflows"
  (https://huggingface.co/blog/sora-2/jev-ai-api-ai-agents-a-practical-guide-to-reliable)
  sobre Jev, modelo de decisiones de TypeSafe AI fundada por el exinvestigador de OpenAI
  Diogo Almeida (ex-ChatGPT/RLHF, dejó OpenAI hace ~2 años; lanzamiento sept 2026, ~$40M seed;
  TechCrunch 18-sep-2026 lo confirmó).
- Pedido de la sesión: estudiar el artículo. Verificado con búsquedas web en paralelo
  (docs.typesafe.ai, GitHub codaaiteam/jev-ai, DataCamp, TechCrunch vía Google News).

## Decisiones (usuario)
1. "Si esto describe casi exactamente lo que ya hacemos, entonces solo déjalo
   estudiado/bitácora." → NO integrar ni comparar formalmente; solo registrar el hallazgo.

## Actividades
- `webfetch` del artículo HF completo (markdown).
- `websearch` x2: verificación de Jev/TypeSafe AI (ex-OpenAI, primitivas Choice/Score/Noul,
  endpoint /v1/systemone, precios) y de la nomenclatura de la API.
- `python3 execution/estado_sesion.py check` → veredicto_global ok, sin huérfanos,
  sin acciones recomendadas.
- Conclusión del estudio:
  - Jev es un "System One model": transformer que NO genera texto, evalúa un `state` contra
    preguntas tipadas (Choice / Score / Noul) y devuelve probabilidad calibrada (70–500 ms,
    input $0.042/M, output gratis, sin "alucinación" por answer-space predefinido).
  - El artículo propone arquitectura: orquestador + Jev (decisión) + LLM generativo (contenido)
    + permisos de aplicación (ejecución) + revisión humana. "Define decisions before tools".
  - PARALELO con ELECTRONICA: describe casi exactamente nuestros principios:
    * `execution/enrutador.py` = versión determinista de su "decidir ruta antes de ejecutar"
      (Jev sería la versión probabilística/calibrada de eso).
    * 3 capas (directiva → orquestador → script) = su "permisos en la capa determinista".
    * Su guardrail "el código ejecuta y valida, la política puede rechazar aunque el modelo
      esté confiado" = nuestra regla de no decidir la ejecución con razonamiento en el chat.
  - Diferencia filosófica: Jev introduce decisión probabilística (ML hospedado) donde nosotros
    usamos reglas puras → choca con el guardrail de determinismo (mismo input → mismo output);
    su lugar natural sería complementar decisiono ambigüedad de intención, nunca sustituir
    el enrutador.
  - Caveats detectados:
    * El artículo HF es Community Article (no oficial); su endpoint (`thejevai.com/v1/systemone`)
      difiere de la doc oficial (`api.typesafe.ai/v1/systemone`).
    * Ecosistema de dominios espejo (thejevai.com, jevai.org, jevai.net, jevmodel.org,
      jev-typesafe.org, tryjevai.com, jevals.com, autojev.ai...) — patron de fan/satellite sites;
      validar dominio oficial antes de usar API key.
    * Benchmarks vendor-reported (DataCamp: sin reproducción independiente a gran escala aún).
  - Conclusión operativa: por ahora es solo referencia conceptual; nuestro enrutador ya cubre
    la función de "decisión" de forma determinista y sin créditos.

## Pendientes
- (Ninguno acordado.) Si en el futuro el usuario quiere profundizar: comparativa formal
  Jev (probabilístico) vs enrutador determinista, o plan de experimento de bajo riesgo con
  la API oficial (validando dominio/endpoint primero).