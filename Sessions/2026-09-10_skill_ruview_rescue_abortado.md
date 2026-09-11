# Aborto del skill `ruview_rescue` (artefacto de prueba, contenido fabricado)

Fecha: 2026-09-10

## Motivo de la sesión

Verificar si la skill `ruview_rescue` (diseñada para el workshop) estaba instalada
globalmente y, de no serlo, retomarla desde la síntesis existente
(`.tmp/sintesis_estructura_ruview_rescue_*.json`).

## Hallazgos del diagnóstico

1. **Skills diseñadas en `~/.config/opencode/skills/`:** 4 instaladas con
   `SKILL.md` + `references/` — `circuitos_dispositivos_electronicos`, `dsh`,
   `pallets_itsdangerous`, `computacion_cientifica`. `ruview_rescue` NO estaba
   instalada y NO era una skill de diseño real.
2. **Origen del artefacto:** fue la fuente mínima elegida para el dry-run de
   prueba del sistema de trazabilidad append-only
   (`Sessions/2026-09-09_trazabilidad_append_only.md`): `--repo
   Proyectos/RuView_Rescue` (12K, 1 README, ~175 tokens), `--nombre
   ruview_rescue --dry-run`. Sus artefactos de skill se eliminaron a
   propósito ("eran solo de prueba"); quedaron colgando solo el
   `.tmp/skill_ruview_rescue_destilado.txt` y el `.tmp/sintesis_estructura_ruview_rescue_*.json`.
3. **Contenido fabricado:** el corpus destilado quedó vacío
   (`(sin contenido extraído)`, 25 B) porque la fuente real
   (`Proyectos/RuView_Rescue/esp32_node/README.md`, 11 líneas) no contiene
   código, solo declara intención futura (*"La implementación detallada del
   firmware se realizará cuando se disponga del hardware físico"*). Pese a ello,
   el LLM ensambló un SKILL.md de 5246 chars + 6 references describiendo una
   arquitectura inexistente (`NetworkManager`, `mesh_network.h/cpp`,
   `message_queue`, `rescue_protocol`, `sensor_base`, `actuator_base`,
   `platformio.ini`, etc.).
4. **Imposibilidad mecánica de "retomar la fase 2 del JSON":**
   `execution/sintetizar_skill.py` solo escribe `sintesis_estructura_*.json`
   como artefacto crudo (L486-491); no lo consume como entrada (las entradas
   son `--texto` + `--entrevista`). No existe `texto_completo.txt` persistido
   para ruview.

## Decisión del usuario

**Abortar y limpiar artefactos** (opción recomendada): el skill ruview jamás fue
real; era una prueba del mecanismo de trazabilidad, ya cumplida. Instalarlo tal
cual habría violado la norma del flujo `repo_a_skill` ("Extrae TODO del código
fuente: no inventes") y el espíritu determinista del proyecto.

## Acciones ejecutadas (0 créditos OpenRouter)

- Eliminados los artefactos del skill inexistente (untracked en git, sin rastro):
  - `.tmp/skill_ruview_rescue_destilado.txt`
  - `.tmp/sintesis_estructura_ruview_rescue_1788957186.json`
- Verificado que no quedan restos de ruview en `.tmp/`.
- **No se tocó** el pipeline real de RuView: `flujo_ruview_rescue.py` (UDP
  listener :5005), `directives/ruview_rescue.yaml`, `docs/RuView/` —
  referencias a `ruview_rescue`/`RuView_Rescue` (AGENTS.md, flujo, directiva,
  guías) son de ese pipeline y permanecen intactas.

## Pendientes

- Ninguno derivado de esta sesión.
- Recordatorio histórico: si algún día `Proyectos/RuView_Rescue` tenga firmware
  real (CSI + MPU6050 + UDP), re-ejecutar el flujo de skill sobre el código real
  sería válido (un skill honesto, no fabricado).