# 2026-09-09 — Delegación multi-proveedor a subagentes (estilo dsh)

## Contexto / Tema
Tras leer el mecanismo de subagentes del DeepSeek Harness, el usuario notó que dsh
delega trabajo a subagentes de DISTINTOS proveedores (seam `ctx.subagents` con
múltiples backends: in-process spawn/fork, ACP, Codex, Claude Code, dsh SDK;
`tool-subagent` = una herramienta por destino; `tool-subagent-control` =
send_message/interrupt/list_agents para hijos continuables). Se decidió evaluar e
incorporar un equivalente DETERMINISTA en ELECTRONICA.

## Decisiones (aprobadas por el usuario)
1. **Opción A:** los subagentes NO fijan modelo — heredan el motor rotativo del
   asistente (0 créditos OpenRouter). La especialización es por persona y permisos.
2. **`--modelo-explicito`:** el subagente sale `null` → elección del orquestador
   (solo el modelo es override).
3. **Trazabilidad:** ampliar el vocabulario de `execution/sesion_log.py` con tipos
   `delegacion/decidida` y `delegacion/resultado`.
4. No tocar artefactos `.tmp/` pendientes de la sesión anterior.

## Actividades
- **Investigación:** leídos en el repo clonado (`packages/subagent/`): README raíz
  (mapa de la familia), `subagent/README.md` (seam: Service Definition/Provider/
  Consumer, one-shot vs continuable, descubrimiento sin cargar), `tool-subagent/
  README.md` (config mínima, `toolName` por instancia, policies), `tool-subagent-
  control/README.md` (send_message/interrupt_agent/list_agents). Confirmado que
  opencode ya trae la primitiva de subagentes con `model` propio por agente,
  `permission.task` y modo `subagent`; `opencode.json` de ELECTRONICA estaba
  minimalista (solo instructions).
- **Implementación (3 capas):**
  - **Ejecución:** `execution/enrutador.py` — constante `SUBAGENTS`
    (flash→sub-rutina, deepseek→sub-sintesis, opus→sub-critico), `DELEGACION_REASON`,
    flag `--delegacion`, salida JSON con `subagent` + `delegacion_reason`.
  - **Ejecución:** `execution/sesion_log.py` — vocabulario ampliado con
    `delegacion/decidida` y `delegacion/resultado` (docstring + `TIPOS_EVENTO`).
  - **Subagentes:** `.opencode/agents/sub-rutina.md`, `sub-sintesis.md`,
    `sub-critico.md` (mode: subagent, sin modelo fijo, permisos por rol).
  - **Directiva:** `directives/delegacion_subagentes.yaml` (SOP 6 pasos, edge cases,
    metadata). Actualizado `.agent/enrutamiento.md` con sección de delegación.

## Pruebas (0 créditos)
- **Enrutador:** formateo→sub-rutina, contexto_masivo (60k)→sub-sintesis,
  examen_complejo+critico→sub-critico, modelo-explicito→subagent null,
  tarea desconocida→código 1. Determinismo OK.
- **sesion_log:** cadena completa (flujo/inicio → delegacion/decidida → flujo/paso
  → delegacion/resultado → flujo/fin) con integrity OK; manipulación de seq
  (1→22) detectada (exit 2). SQL: ninguno (tamper test limpio tras verificar).

## Pendientes
- Reiniciar opencode para que cargue los 3 subagentes (`opencode` los lee de
  `.opencode/agents/` al arrancar).
- Test de delegación real en vivo (p. ej. que el orquestador delegue un resumen a
  `sub-rutina` vía Task tool y quede trazado en sesion_log).
- Opcional: ampliar `SUBAGENTS` con más subagentes si aparece un nuevo rol
  (editar solo el mapa de `execution/enrutador.py` + re-test).

## Commit
`feat: delegación multi-proveedor determinista a subagentes (estilo dsh)`