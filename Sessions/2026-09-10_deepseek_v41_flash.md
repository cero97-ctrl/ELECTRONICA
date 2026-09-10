# Sesión 2026-09-10 — Migración del tier deepseek: V4 Pro → V4.1 Flash

## Disparador

El usuario recibe un e-mail del equipo DeepSeek (2026-09-10) anunciando:
- Lanzamiento oficial de **V4.1 Flash** (2026-09-10, hora Beijing).
- **Discontinuación de V4 Pro** el **2026-09-14 12:00 Beijing (04:00 UTC)**: las
  peticiones a `Pro` se redirigirán a V4.1 Flash y se facturarán a precio Flash.
- V4.1 Flash supera a V4 Pro en rendimiento, costo, velocidad y tiempo de tarea.
- Precios V4.1 Flash (por 1M tokens): in cache hit $0.003, in cache miss $0.15,
  out $0.6 (off-peak); picos (UTC 1–4 y 6–10) $0.006/$0.3/$1.2.

## Diagnóstico

ELECTRONICA tenía el tier medio (`MODEL_TIERS["deepseek"]`) mapeado a
`deepseek/deepseek-v4-pro`, que deja de servirse el 14-sep. Se verificó en el
catálogo de OpenRouter que `deepseek/deepseek-v4.1-flash` ya está activo:
- in $0.15/M, out $0.60/M (off-peak), contexto 1M (1048576), coincide con el e-mail.

## Decisiones (aprobadas por el usuario)

1. **Pinear V4.1 Flash explícito** (`deepseek/deepseek-v4.1-flash`) — opción
   determinista; se descarta el alias `~deepseek/deepseek-v4-flash-latest` (no pineado).
2. **Retirar del todo `deepseek/deepseek-v4-pro`** — no queda ni como opcional
   (`--modelo-explicito`); se deja de servir el 14-sep y el vendor lo redirige.
3. Sin cambios en la cadena de fallback (`deepseek→glm→opus`), en el enrutador ni en
   los umbrales de tokens; el rol del tier (contexto masivo/razonamiento intermedio,
   JSON mode) se conserva.
4. Las **Sessions/ y docs históricas no se tocan** (p. ej.
   `docs/AGENTE_IA/fase1_libro_a_skill.md`, `fase1b_repo_a_skill.md`, `Sessions/*` de
   agosto).

## Cambios

### Código (fuente única de IDs)
| Archivo | Cambio |
|---|---|
| `execution/llm_client.py` | `MODEL_TIERS["deepseek"]` → `deepseek/deepseek-v4.1-flash`; comentario docstring `llm_client.py` (razonadores). |
| `flujo_repo_a_skill.py` | `DEFAULT_MODEL` → `deepseek/deepseek-v4.1-flash`. |
| `flujo_libro_a_skill.py` | `DEFAULT_MODEL` → `deepseek/deepseek-v4.1-flash`. |
| `execution/sintetizar_skill.py` | dict interno `MODEL_TIERS` y docstring → nuevo ID. |
| `execution/generar_latex_orquestador_repo_skill.py` | plantillas LaTeX (modelo default y tier enrutado) → nuevo ID. |
| `execution/generar_latex_fase1b.py` | plantilla LaTeX → nuevo ID. |

### Documentación / política
| Archivo | Cambio |
|---|---|
| `.agent/enrutamiento.md` | tabla de niveles: ID + costo nuevos con nota de sustitución. |
| `docs/ARQUITECTURA_ENRUTAMIENTO_LLM/arquitectura_enrutamiento_llm.md` | sección tier medio + jerarquía + ejemplos (`v4-pro` → `v4.1-flash`). |
| `directives/libro_a_skill.yaml` | edge case `content=None` → modelo actual. |
| `AGENTS.md` | sección enrutamiento multi-LLM (IDs) y tabla comparativa vs dsh. |

## Verificación (0 créditos)

- `py_compile` OK en los 6 scripts tocados.
- Determismo del enrutador (A=B):
  `--task contexto_masivo --archivos AGENTS.md .agent/enrutamiento.md` →
  `{tier: deepseek, model: deepseek/deepseek-v4.1-flash, tokens: 8185}` idéntico
  en dos ejecuciones.
- `grep deepseek-v4-pro` restante solo en historia (Sessions/, docs AGENTE_IA previos).
- Saldo OpenRouter: **$21.06** (usage $3.7068, tier pago) — se mantiene tras la
  migración (ninguna llamada realizada).

## Pendientes / observaciones

- Los precios tabulados ($0.15/$0.60) son los **off-peak de OpenRouter vistos en el
  catálogo**; hay franjas peak (UTC) con tarifa ~2× — asumidas en docs pero no
  automatizadas (el enrutador no decide por franja horaria).
- No se realizó ninguna llamada de consumo real tras la migración; primer uso real
  de V4.1 Flash quedará evidenciado en `.tmp/routing_log.jsonl` y la factura del mes.