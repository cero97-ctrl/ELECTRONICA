# Análisis de OmniRoute — Gateway AI multi-proveedor

> **Fecha:** 2026-09-21 · **Fuente:** https://github.com/diegosouzapw/OmniRoute
> (branch `release/v3.8.51`) · **Contexto:** análisis informativo solicitado por el
> usuario; sin integración ni instalación. Relacionado con la doc de autoridad
> `arquitectura_enrutamiento_llm.md` (mismo directorio).

---

## 1. Qué es

**OmniRoute** es un gateway AI **local-first** y open source (MIT, TypeScript/Next 16,
~68.8k stars, 600+ contribuidores) que unifica decenas de proveedores de LLM detrás de
**un único endpoint OpenAI-compatible** (`localhost:20128/v1`). Escribe la base del
catálogo que rutea a **357+ proveedores** (152 marcados con free tier, ~1.1k IDs de
modelo único / ~1.62B tokens gratis/mes, deduplicando pools compartidos) hacia
cualquier herramienta de codificación sin reconfiguración.

Instalación sin fricción: `npm i -g omniroute` (o Docker/Electron/Termux/PWA), con
modelo `auto` funcional desde el primer arranque sin API keys.

## 2. Arquitectura y capacidades clave

| Capacidad | Detalle |
| :--- | :--- |
| **Ruteo** | 19 estrategias: auto-fallback cuota-aware, weighted, cost-optimized, context-relay, priority; 3 capas de resiliencia (circuit breaker + cooldown + lockout) |
| **Provider pool** | 357+ proveedores, 152 free tier; deduplicación honesta de pools (cada pool compartido cuenta una vez) |
| **Compresión de tokens** | RTK + Caveman apiladas → 15–95% de ahorro (~89% avg en sesiones con herramientas); código/URLs/JSON se preservan byte-perfect |
| **Protocolos** | Servidor MCP integrado (~100+ tools / 30+ scopes, stdio/HTTP/SSE), A2A (JSON-RPC), traducción de formato OpenAI↔Claude↔Gemini↔Responses |
| **Clientes** | Claude Code, Codex, Cursor, Cline, Copilot, Antigravity, Windsurf, Kiro, **OpenCode** (plugin `@omniroute/opencode-provider`), etc. |
| **Operación** | Local-first, self-host en cualquier plataforma; dashboard web `localhost:20128/dashboard`; CLI con 80+ comandos |
| **Extras** | Modalidad vision/audio/video (bridging), telemetría de cuotas en vivo, guardrails, memory |

## 3. Fortalezas

- **Económico:** monetiza los tiers gratis agregados; fallback automático ante 429
  /límites → "never stop coding".
- **Un solo endpoint:** una config sirve para muchas herramientas; cero fricción de
  setup (zero-config).
- **Privacidad:** local/self-host, sin pasar por la nube del proveedor de gateway.
- **Madurez:** comunidad y actividad enormes, roadmap activo hacia v3.9.0 LTS,
  auditoría bisemanal del catálogo free-tier.

## 4. Debilidades y riesgos

- **Ruteo robusto pero no determinista en el sentido del workspace:** la decisión
  final del modelo depende de estado global (cuotas, prioridad, costo calculado en
  runtime), no de un descriptor puro. El mismo requerimiento puede resolver a
  modelos distintos según el momento → violaría el principio de reproducibilidad de
  ELECTRONICA si se usara como capa de decisión.
- **Catálogo volátil:** los tiers gratis entran y salen cada 2 semanas; las cifras
  publicadas se mueven en ambos sentidos y dependen de auditoría manual.
- **Riesgo de la dependencia de tiers gratuitos:** tasa de fallo/elevada de latencia
  en horas pico puede escalar a proveedores de pago y gastar más de lo esperado.
- **No resuelve geo-bloqueo VE:** OmniRoute no suplanta regiones; Groq/OpenAI
  directos seguirían devolviendo 403 sin VPN a nivel máquina.
- **Madurez de la "honestidad" de conteo:** depende de categorizar bien qué es
  "free forever" vs signup credits; errores de catalogación enturbian las métricas.

## 5. Relevancia para ELECTRONICA

OmniRoute encaja como **complemento potencial, no sustituto**, de la arquitectura
existente:

| Capa | ELECTRONICA | OmniRoute (si se integrara) |
| :--- | :--- | :--- |
| **Decisión de modelo** | `execution/enrutador.py` — 100% determinista, $0 | No participa; se respeta el tier elegido |
| **Testamento de fallback** | Cadenas cost-aware fijas (flash→deepseek→glm, opus→deepseek→glm), máx 3 intentos | Fallback automático de ejecución entre proveedores del mismo o parecido modelo |
| **Ejecución** | `openrouter_chat` (consumo de créditos OpenRouter) | Posible capa de ejecución alternativa: cuando OpenRouter falle o el saldo baje, OmniRoute podría servir modelos de tiers gratis agregados |
| **Geo VE** | Solo OpenRouter/Gemini sin VPN | Complemento de proveedores accesibles; no omite el filtro de región |

**Conclusión:** la decisión de *qué* modelo usar debe seguir viviendo en
`enrutador.py` (principio rector determinista del workspace). OmniRoute podría
actuar como capa de *ejecución* fallback económica para `openrouter_chat` (reducir
consumo de créditos cuando el saldo esté cerca del auto top-up), sin tocar la
matriz de decisión. No se recomienda adoptarla como router de decisión.

## 6. Comparativa de principio con el enrutador del workspace

| Dimensión | `execution/enrutador.py` | OmniRoute |
| :--- | :--- | :--- |
| Naturaleza de la decisión | Función pura del descriptor; mismo input → mismo output | Estado global (cuotas/prioridad/costo) → output variable |
| Telémetro de decisión | `.tmp/routing_log.jsonl` | Dashboard/telemetría de cuotas |
| Créditos | 0 (decisión local) | 0 por la puerta del gateway; el consumo ocurre en el provider destino |
| Filosofía | Determinismo estricto | Resiliencia y optimización de costo por conveniencia |

---

*Referencias: repositorio GitHub `diegosouzapw/OmniRoute`, npm `omniroute`, sitio
`omniroute.online`. Cifras de catálogo a 2026-09-21 (v3.8.51).*