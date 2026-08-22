# 2026-08-22 — Cambio de color del prompt en Linux (PS1/Bash)

**Tema:** Personalización del color y estilo (negrita) del prompt de Bash mediante la variable `PS1`.

## Contexto
- Consulta puntual del usuario sobre cómo cambiar el color del prompt en Linux.
- Sin relación con los flujos del repositorio; no requiere capa de ejecución.

## Actividades
1. Explicación de la modificación de `PS1` en `~/.bashrc` con códigos de escape ANSI:
   - Ejemplo aplicado: `PS1="\[\e[32m\]\u@\h:\w\$ \[\e[0m\]"` (verde) + `source ~/.bashrc`.
   - Paleta documentada: `31m` rojo, `32m` verde, `33m` amarillo, `34m` azul, `35m` magenta, `36m` cian.
2. Extensión a negrita/brillante anteponiendo `1;` al código de color:
   - Ejemplo aplicado: `PS1="\[\e[1;32m\]\u@\h:\w\$ \[\e[0m\]"`.
3. Incidental: el usuario notó que OpenCode renombra las sesiones automáticamente (`New session - <timestamp>` → título descriptivo). Se acordó que el agente sugiera explícitamente el título `<Tema> — <fecha>` al inicio de cada sesión para guiar el renombrado automático de la UI.

## Decisión
- Convención adoptada: el nombre de sesión en la UI debe reflejar **tema central + fecha**; el agente lo propondrá en su primera respuesta de cada sesión.
- El registro en `Sessions/<fecha>_<tema>.md` ya cumple esa convención desde 2026-08-14 (sin cambios necesarios).

## Pendientes
- [x] Crear este registro de sesión y confirmarlo con el usuario.
- [x] Comprometer el registro junto al trabajo de la sesión.
