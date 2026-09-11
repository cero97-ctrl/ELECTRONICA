# 2026-09-10 — Prueba en vivo de delegación tier opus → sub-critico

## Contexto / Tema
Completar el camino crítico de la delegación multi-proveedor (directiva
`delegacion_subagentes.yaml`) que quedó pendiente el 2026-09-09: la prueba en vivo
solo había cubierto `flash → sub-rutina`. Esta sesión valida `opus → sub-critico`
(razonamiento crítico) de punta a punta con las 3 capas y trazabilidad append-only.

## Descriptor (probado y confirmado por el usuario)
- `--task examen` sobre `cursos/INT_ELECTRONICA/ejercicios/04/ejercicios.tex`
  (13 438 bytes, 2 659 tokens medidos por el enrutador).
- `enrutador.py --delegacion --no-log` → `{tier: opus, model: anthropic/claude-opus-5,
  subagent: sub-critico, fallback: [opus, deepseek, glm]}`.
- Determinismo: regla pura "tipo de tarea 'examen' es de razonamiento crítico -> opus".

## Ejecución (flujo completo)
1. `flujo/inicio` (seq 1).
2. `delegacion/decidida` (seq 2) con `{task, tier, subagent, tokens, critico, vision}`.
3. **Task tool** `subagent_type: sub-critico` → revisión de `ejercicios.tex`.
4. `delegacion/resultado` (seq 3, exit 0).
5. `flujo/fin` (seq 4).
6. `integrity` OK: cadena de hashes íntegra en los 4 eventos (append-only respetado).

## Resultado de la delegación (sub-critico)
- Veredicto: **ok** (5 ejercicios de filtros activos RC, Semana 4).
- Análisis por ejercicio: ganancias determinadas (R2 = Av·Ri), R calculado en
  Ej.2 ≈ 31.8 kΩ y Ej.4 ≈ 1.59 kΩ, Qs verificados (20 y 7.5), puntajes suman 10.0.
- 10 verificaciones realizadas (cálculos, unidades, órdenes de magnitud, Q, suma).
- Sin hallazgos de error; devolvió JSON estructurado válido (esquema exigido).

## Verificación técnica
- Saldo OpenRouter **sin variación**: $21.06 (usage $3.7068) — confirmado 0 créditos
  consumidos (subagente sin modelo fijo, hereda motor rotativo).
- Trazabilidad append-only completa e íntegra (4/4 eventos, hash chain OK).
- Log de prueba eliminado del `.tmp/` tras la verificación.

## Pendientes
- Opcional: probar un caso de `subagent: null` con `--modelo-explicito` en vivo
  (el camino restante del mapa; la elección recaería en el orquestador).
- Opcional: extender `SUBAGENTS` si aparece un rol nuevo (solo el mapa en
  `execution/enrutador.py` + re-test).

## Commit
`feat(delegacion): prueba en vivo tier opus → sub-critico (revisión de ejercicios.tex)`