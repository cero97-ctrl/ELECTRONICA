# 2026-10-08 — Flujo research_topic: auriculares de traducción simultánea con IA

## Tema
Flujo research_topic: auriculares de traducción simultánea con IA

## Contexto
- El usuario pidió investigar «auriculares de traducción simultánea con IA». Estaba en
  modo plan, así que se le ofrecieron tres opciones; confirmó la **Opción A**: implementar
  el flujo declarado en `directives/research_topic.yaml` (Status: planificado, sin capa 3)
  y correrlo con ese tema — en vez de investigar inline en el chat (guardarraíl de
  determinismo de AGENTS.md: procesar/raspear inline viola el espíritu del proyecto).

## Decisiones (usuario)
1. Opción A: construir el flujo completo de 3 capas (directiva + orquestador + scripts) y
   ejecutarlo con el tema de los auriculares, guardando el informe como archivo reutilizable.
2. Confirmó ejecutar el paso de síntesis con LLM (consume créditos OpenRouter) tras el aviso
   de costo; saldo previo: $20.25.

## Actividades
- `estado_sesion.py check` OK; sin sesiones previas del tema (`glob Sessions/*traduc*` vacío).
- **Hallazgo de entorno:** `bs4` faltaba en `elect_env` → `scrape_single_site.py` no
  arrancaba (import roto preexistente). Se instaló `beautifulsoup4` 4.15.0 (+soupsieve).
  Además `curl_cffi` 0.16.3 (necesario para el buscador: `requests` plano recibe 202/decoy de DDG,
  Bing 200 con resultados ajenos al azar, SearXNG con challenge anti-bot).
- **Capa 3 `execution/web_search.py`:** buscador DDG (html + lite) sin API key, curl_cffi
  impersonando TLS (chrome124/firefox133/safari18), rotación motor+huella con budget máx 3
  transportes, limpieza de redirects `uddg`, `l=es-es`. Códigos 0/1/2. Probado en vivo: 6
  resultados españoles relevantes.
- **Capa 3 `execution/process_search_results.py`:** lee el JSON de búsqueda, raspa las N
  primeras fuentes vía `scrape_single_site.py` (fetch_html + html_to_markdown), corpus
  marcado, y sintetiza informe markdown con `openrouter_chat` (tier recibido por CLI, el
  enrutador decide). Degrada a modo bruto si el LLM falla o llega `--no-llm` (avisa en el
  entregable). Bug corregido en el camino: `html_to_markdown` recibe string, no Response; y
  la clave se carga con `llm_client.load_api_key()` (carga `.env`), no `os.getenv` a secas.
- **Capa 2 `flujo_research_topic.py`:** orquestador argparse, run_state por corrida
  (`ELECTRONICA_RUN_ID`), decisión de modelo vía `execution/enrutador.py --task destilacion`
  (subproceso, $0) salvo `--modelo` explícito, alert_user al cierre. Flags: `--tema
  --output --max-results --max-pages --modelo --no-llm --dry-run --no-alert`.
- **Capa 1 `directives/research_topic.yaml`:** pasa a `Status: activo` (regla
  `declaracion_honesta` de la auditoría), con `orchestrator:`, `Real scripts:`, Opciones CLI
  (deben casar con el argparse, o `directivas` de la auditoría cae en flags fantasma) y
  edge cases. `--no-llm` evita créditos.
- **Ejecuciones reales del tema «auriculares de traducción simultánea con IA»:**
  - 1.ª pasada `--no-llm` (validación sin costo): modo bruto, 4 fuentes raspadas, corpus
    ~22,3k chars. Sirvió para detectar el bug de `fetch_html`→`html_to_markdown`.
  - 2.ª pasada con LLM (confirmada por el usuario): modo `llm`, informe estructurado de 52
    líneas (funcionamiento, límites, criterios de compra, modelos recomendados, fuentes) en
    `docs/INVESTIGACIONES/auriculares-de-traduccion-simultanea-con-ia.md`.
- AGENTS.md actualizado: comando de investigación web + entrada en la lista de
  orquestadores + dependencias nuevas del entorno.
- No se commiteó (el usuario no lo pidió).

## Pendientes
- Verificar el nuevo flujo con la auditoría (`python3 flujo_auditar_repo.py --dimension
  directivas --dimension capas`) cuando toque la pasada de higiene: las referencias de
  `research_topic.yaml` y la capa 3 de `flujo_research_topic.py` deberían resolver.
- `execution/process_search_results.py` admite `--max-chars` por página (default 6000); no
  se expone aún como flag del orquestador por no inflar la interfaz. Se puede añadir si un
  tema reclama corpus más largos.
- Otros instalados de `curl_cffi`/`beautifulsoup4` quedan en `elect_env`; documentar en la
  checklist de migración de entorno si se quiere.