# Sesión 2026-09-08 — Exploración de DeepSeek Harness (skill dsh)

**Fecha:** 2026-09-08
**Tema:** Explorar características de DeepSeek Harness (dsh) y evaluar su posible incorporación a ELECTRONICA.

## Contexto

El usuario trae `docs/AGENTE_IA/dsh-agent-skill-spec.md`, una especificación técnica para
construir un "consultation and query skill" sobre DeepSeek Harness (dsh), el agent harness
open-source de DeepSeek AI basado en Cordis ("Everything is a plugin. Every run is traceable.").

Objetivo del usuario: explorar las características de dsh y evaluar si incorporarlas a este
espacio de trabajo si se considera útil.

## Decisiones (con aprobación del usuario)

1. **Alcance del skill:** solo docs + archivos raíz (`--incluir "*.md" "*.yaml"`), sin código TS.
   Skill de consulta ligero, centrado en arquitectura/despliegue/operación. Bajo costo.
2. **Prueba hands-on de dsh:** NO por ahora. Evaluación basada en el skill documentado.
   Pendiente registrado para futuro: `npx @deepseek-ai/dsh web` y probar los 4 runtime modes.
3. **Opción elegida para explorar:** reutilizar `flujo_repo_a_skill.py --perfil referencia_codigo`
   (infraestructura ya existente y probada) en lugar de crear un MCP nuevo.
4. Aviso de créditos: la síntesis (`sintetizar_skill.py`) consume créditos OpenRouter (tier deepseek).

## Actividades

- Lectura y análisis de `docs/AGENTE_IA/dsh-agent-skill-spec.md`.
- Verificación del entorno: Node v22.23.1 (nvm), saldo OpenRouter, infraestructura de skills
  existente (`flujo_repo_a_skill.py`, `sintetizar_skill.py`, `instalar_skill.py`).
- Ejecución de Fase A: generación del skill `dsh` (extracción → enrutador → síntesis →
  validación → LaTeX → revisión → instalación).
- Ejecución de Fase B: memo de evaluación de incorporación (LaTeX).

## Resultados

- Skill `dsh` generado e instalado en `~/.config/opencode/skills/dsh/`.
- Reporte LaTeX en `docs/SKILL/dsh/`.
- Memo de evaluación en `docs/AGENTE_IA/dsh_evaluacion_incorporacion.tex`.

## Pendientes

- [ ] Prueba hands-on de dsh (4 runtime modes) cuando el usuario lo decida.
- [ ] Decidir qué características incorporar a ELECTRONICA según el memo (trazabilidad
      append-only, modularización plugin-style, etc.).