# 2026-11-21 — monitor_saldo_openrouter_credits_api

## Tema
Corregir `execution/monitor_saldo_openrouter.py`: el saldo debía leerse de
`/api/v1/credits` (`total_credits - total_usage`) en vez de restarse a una
constante fija, para eliminar las falsas alertas de `top_up_inminente`.

## Contexto
- Durante la sesión de consistencia de Lab II apareció un cargo de $0.04 en
  OpenRouter. Al verificarlo con `monitor_saldo_openrouter.py`, el script
  reportó `-$30.29` y `alerta: top_up_inminente`.
- El usuario objetó con razón: con saldo negativo OpenRouter no habría
  autorizado el cargo de $0.04.
- Consulta directa a la API con la clave del `.env`:
  - `GET /api/v1/credits` → `total_credits: 65`, `total_usage: 59.959003626`
    → **saldo real $5.04** (positivo).
  - `GET /api/v1/auth/key` → `usage: 55.059396678`, `usage_daily: 0.43393`,
    `usage_monthly: 49.89213`. El `usage` de esta clave difiere del
    `total_usage` de la cuenta en $4.90: no es la fuente del saldo.
  - `GET /api/v1/activity` → `403 Only management keys can fetch activity for
    an account`. `GET /api/v1/usage` → `404`. No hay desglose por modelo
    accesible con esta clave (ni script en `execution/` que lo haga).
- Causa raíz: `CREDITS_TOTAL_REF = 24.769395`, fijada el 2026-09-01.
  El propio docstring decía «Ajustar si cambia la compra/top-up» y no se
  ajustó: con $65 comprados, `24.769395 - 55.0594 = -30.29`. La constante
  convertía cada recarga en una falsa alarma.

## Decisiones (usuario)
1. Autorización literal: **«corrija para que lea total_credits - total_usage de
   la API y deje de emitir falsas alertas de top_up_inminente»**.
2. Decisión de implementación: mantener `saldo_estimado` como alias legacy del
   nuevo campo `saldo` (no hay consumidores programáticos, pero sí documentación
   que lo menciona); `/auth/key` sigue consultándose solo para datos
   informativos.
3. El desglose por modelo de los $0.04 quedó **sin confirmar**: la API lo
   veda a claves no-management. La evidencia local (único evento de enrutamiento
   de hoy = opus para las 34 figuras TikZ a las 12:15:49Z, `usage_daily`
   $0.43393) apunta al flujo de figuras, no a la ronda de consistencia.

## Actividades
- **Lectura previa**: `grep` de `saldo_estimado|monitor_saldo|_estimado_saldo|
  CREDITS_TOTAL_REF` en todo el repo → 27 coincidencias, todas documentación o
  bitácoras; ningún consumidor programático ni test.
- **Corrección en `execution/monitor_saldo_openrouter.py`**:
  - Eliminada `CREDITS_TOTAL_REF` y `_estimado_saldo(usage)`.
  - Añadida `_get_credits(key)` (`GET /api/v1/credits`, convierte a `float`) y
    `_saldo(credits)` = `total_credits - total_usage`.
  - `_get_usage(key)` ampliado con `usage_daily`, documentado como informativo.
  - `chequeo()` y la rama `--watch` calculan el saldo con `_get_credits`.
  - JSON: nuevo `saldo`, `total_credits`, `total_usage`, `usage_daily`;
    `saldo_estimado` queda como alias. Log: «Saldo: $x (creditos $a - uso $b)».
  - Docstring reescrito: OpenRouter **sí** expone totales por API; se documenta
    el fallo de la constante para que no se reintroduzca.
- **Test nuevo `execution/test_monitor_saldo.py`** (13 aserciones, sin red):
  congela el caso real (credits 65 / usage 59.959003626 → saldo 5.040996374),
  prohíbe que vuelvan `CREDITS_TOTAL_REF` y `_estimado_saldo`, verifica que un
  `usage` de $55.06 de `/auth/key` no vuelve negativo el saldo, comprueba que
  con $5.04 **no** hay `alerta` y que con $2.50 **sí** hay
  `top_up_inminente` (la alerta no se desactivó).
- **Verificación en vivo**: `python3 execution/monitor_saldo_openrouter.py`
  → `{"status":"ok","saldo":5.04,"saldo_estimado":5.04,"total_credits":65.0,
  "total_usage":59.959004,...}`, sin campo `alerta`, exit 0.
  El test pasó tras corregir una aserción mal sumada por el agente
  (5.039996374 → 5.040996374); el código del monitor era correcto.
- `AGENTS.md`: añadido `python3 execution/test_monitor_saldo.py` al índice de
  tests con la descripción del caso congelado.

## Pendientes
- **Commit/push SIN hacer**: el usuario autorizó la corrección, no git.
  Incluye `execution/monitor_saldo_openrouter.py`,
  `execution/test_monitor_saldo.py`, `AGENTS.md` y esta bitácora.
- Para ver el desglose exacto por modelo haría falta una *management key* de
  OpenRouter. No se creó ni se elevó la clave actual.
- La afirmación histórica «OpenRouter NO expone el saldo por API» sigue en
  bitácoras de 2026-08-15: es contexto de esa fecha, no se reescribió.
