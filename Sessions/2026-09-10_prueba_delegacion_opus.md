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
- ~~Opcional: probar un caso de `subagent: null` con `--modelo-explicito` en vivo
  (el camino restante del mapa; la elección recaería en el orquestador).~~ **HECHO**
  (ver prueba extra abajo).
- Opcional: extender `SUBAGENTS` si aparece un rol nuevo (solo el mapa en
  `execution/enrutador.py` + re-test).

## Prueba extra (2026-09-10) — `--modelo-explicito` → `subagent: null` en vivo
Camino restante del edge case 1 de `directives/delegacion_subagentes.yaml`:
- Descriptor: `--task resumen --archivos directives/delegacion_subagentes.yaml
  --modelo-explicito openai/gpt-oss-20b --delegacion --no-log`.
- Enrutador: `{tier: explicito, model: openai/gpt-oss-20b, subagent: null,
  fallback: [], reason: "Modelo explícito solicitado por el usuario"}`
  (sin telemetría de routing; salida esperada del edge case).
- **Elección del orquestador** (subagent null): naturaleza rutina → `sub-rutina`;
  el modelo explícito se respeta como override total.
- Trazabilidad: run `test_explicito_vivo` — `flujo/inicio` (seq 1),
  `delegacion/decidida` (seq 2, subagent null en datos), `delegacion/resultado`
  (seq 3), `flujo/fin` (seq 4); `integrity` OK (cadena de hashes íntegra).
- Subagente devolvió JSON válido (6 pasos, 3 subagentes, 5 edge cases).
- Saldo sin variación: $21.06. Log de prueba eliminado.
- Con esto quedan cubiertos los 3 caminos del mapa: flash→sub-rutina (2026-09-09),
  opus→sub-critico (arriba), modelo-explicito→null (elección orquestador).

## Commit
- `feat(delegacion): prueba en vivo tier opus → sub-critico (revisión de ejercicios.tex)`
- `feat(delegacion): prueba en vivo modelo-explicito → subagent null (elección orquestador)`