# 2026-09-12 — Ajuste del documento PC de IA (Workstation B650)

## Tema
Añadir sección de "Ejemplos de Uso del Workspace" al documento infográfico
`docs/PC_PARA_IA/PC_IA_B650_WORKSTATION.tex` y sobrescribir su PDF.

## Contexto
- El plan original consistía en generar 4 documentos LaTeX (documentación completa,
  instalación, flujo y ejemplos) desde un skill/scripts fuente de la PC de IA
  (`pc3/`).
- **Hallazgo:** la fuente `pc3/` NO existe en este sistema (busqueda exhaustiva en
  repo, skills globales `~/.config/opencode/skills/`, `~/.claude/skills/`,
  `~/.agents/skills/`, `.opencode/skills/`, `.tmp/skill_*`, `docs/SKILL/`,
  `docs/PC_ASUS/` y en el home). Solo existe el propio `.tex` de lista de compras.
- Por ello se descartó el plan de 4 documentos.

## Decisiones (usuario)
1. Descartar el plan de 4 documentos; NO existe skill/scripts fuente de la PC de IA.
2. Solo ajustar el `.tex` actual siguiendo la idea de "capítulos de ejemplos de uso".
3. **Conservar** la lista de compras original y **añadir** los ejemplos tras ella
   (opción recomendada elegida por el usuario).
4. Sobrescribir `PC_IA_B650_WORKSTATION.{tex,pdf}` en `docs/PC_PARA_IA/`.
5. Crear bitácora de sesión y hacer commit al finalizar.

## Actividades
1. **Validación de comandos a documentar:** verificados contra el repo real
   (`compile_latex.py`, `verificar_pdf.py`, `enrutador.py`,
   `monitor_saldo_openrouter.py`, `estado_sesion.py`, `bitacoras.py`,
   `flujo_elaborar_examen.py`, `rag_system.py`, `fix_latex.py`,
   `update_repo.sh`, `git-update.sh`). Todos existen.
2. **Edición de `docs/PC_PARA_IA/PC_IA_B650_WORKSTATION.tex`:** nueva sección 5
   "Ejemplos de Uso del Workspace" con 8 subsecciones (verificación LaTeX,
   enrutamiento multi-LLM, elaboración de exámenes, fix de `\text{}`, RAG,
   control de versiones, monitoreo de saldo OpenRouter, higiene de estado de
   sesión). Cada ejemplo con comando real en `lstlisting` + recuadro explicativo.
   Veredicto Final pasa a ser la sección 6.
3. **Corrección de recuadros tcolorbox:** `cajaEjemplo` y `cajaRecuerda` son
   ENTORNOS (`\newtcolorbox`), no estilos `[cajaEjemplo,...]`. Primera compilación
   falló con `Package pgfkeys Error: I do not know the key '/tcb/cajaEjemplo'`.
   Se reemplazó `\begin{tcolorbox}[cajaEjemplo,title=...]` por
   `\begin{cajaEjemplo}...` y el inexistente `cajaNota` por el entorno `cajaRecuerda`.
4. **Compilación:** `pdflatex` 3 pasadas desde `docs/PC_PARA_IA/` → exit 0 en las 3;
   auxiliares (`.aux/.log/.out/.toc`) eliminados.
5. **Verificación determinista:** `execution/verificar_pdf.py --pdf` →
   `{"status": "ok", "paginas": 7, "errores": [], "overfull": [], "solapes": [],
   "solapes_total": 0}`.

## Pendientes
- Ninguno. Posible mejora futura (no acordada): refactorizar el preámbulo infográfico
  inline hacia `execution/estilo_infografia.py` → `PREAMBULO_INFOGRAFIA`.