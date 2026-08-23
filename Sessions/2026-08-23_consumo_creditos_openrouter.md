# Sesión 2026-08-23 — Aclaración: consumo de créditos OpenRouter

**Fecha:** 2026-08-23
**Tema:** Qué instrucciones del usuario hacen necesario consumir créditos de OpenRouter y cuáles no
**Estado:** Resuelto, documentado

## Contexto

El usuario observó que en las 2–3 sesiones previas (cambio de color del prompt Linux,
migración de chat_id de Telegram, autoenv conda en opencode) se resolvió todo sin gastar
un solo crédito de OpenRouter, y pidió una aclaración formal sobre qué tipo de
instrucciones sí los consumen.

## Análisis

Se verificó con grep qué scripts de `execution/` llaman a `openrouter_chat` de
`execution/llm_client.py`: `evaluar_examen.py`, `analizar_imagen.py`,
`elaborar_ejercicios.py`, `elaborar_examen.py`, `generar_kicad_llm.py`,
`extraer_netlist_imagen.py`, `agent_eda.py` (y `rag_system.py` por la política vigente).

Conclusión (matriz completa ahora en `.agent/enrutamiento.md` → sección
"Qué consume créditos OpenRouter y qué no"):

- **Nunca consumen:** toda la orquestación del chat (editar archivos, compilar LaTeX,
  git, diagnóstico, scraping determinista) — el motor del asistente rota entre modelos
  Free y no toca `OPENROUTER_API_KEY`. Tampoco `enrutador.py` en sí ($0: decide local,
  sin llamar APIs).
- **Sí consumen:** ejecución real de los flujos LLM vía `openrouter_chat`
  (`elaborar_examen/ejercicios` = default openrouter + tier opus, el más caro;
  `evaluar_examen`, `rag_system.py`, `agent_eda.py`, `extraer_netlist_imagen.py`,
  `generar_kicad_llm.py`).
- **Condicional:** `analizar_imagen.py` solo consume si se pasa `--api-backend
  openrouter`; su default es Gemini free tier (20 req/día/modelo).
- Regla práctica para el orquestador: si el comando lleva `--api-backend openrouter`
  (o su default lo trae), avisar al usuario antes; si es edición/compilación/diagnóstico
  o backend gemini, correr sin avisar.

Las sesiones previas fueron pura orquestación/edición de archivos, por eso $0.

## Cambios realizados

1. `.agent/enrutamiento.md` — nueva sección "Qué consume créditos OpenRouter y qué no"
   (auto-cargada por cualquier LLM orquestador vía `instructions: [".agent/*.md"]`),
   con matriz de consumo, regla de aviso al usuario y verificación.
2. `AGENTS.md` — bullet "Motor del asistente opencode (rotativo)" corregido:
   `enrutador.py` NO consume créditos (solo decide); referencia a la matriz completa
   en `.agent/enrutamiento.md`.
3. Este log de sesión.

## Decisiones

- La fuente autoritativa de la matriz es `.agent/enrutamiento.md`; `AGENTS.md` solo
  referencia. Evita divergencias entre ambos archivos.

## Pendientes

- Ninguno.
