# 2026-10-12 — rea_evaluacion_incorporacion

## Tema
rea_evaluacion_incorporacion

## Contexto
- El usuario aporta una nota de NotebookLM («Ingeniería Inversa IA») sobre REA
  (Reverse Engineer Anything, `morluto/rea`) y pide evaluar su incorporación al
  proyecto **sin instalar nada**, dejando el análisis en un documento LaTeX/PDF.
- Continúa la serie de evaluaciones de herramientas externas de `docs/AGENTE_IA/`
  (`graphify_evaluacion_incorporacion`, `dsh_evaluacion_incorporacion`).
- El destino es el clon de ELECTRONICA en la **HP EliteDesk 805 G6** (contexto:
  `Sessions/2026-10-10_veredicto_hardware_hp_elitedesk.md`).
- Se aplica el protocolo de fuentes externas (`Sessions/2026-10-10_protocolo_fuentes_externas.md`).

## Decisiones (usuario)
1. Entregable en `docs/AGENTE_IA/rea_evaluacion_incorporacion.{tex,pdf}`, hermano de
   los de graphify/dsh.
2. Reubicar la nota fuente a `docs/AGENTE_IA/fuentes/` con cabecera de procedencia YAML
   y bloque de correcciones.
3. No instalar nada en esta sesión; solo investigar y documentar.
4. No hacer commit (salvo petición explícita posterior).

## Actividades
- Investigación verificada en fuente primaria: `github.com/morluto/rea`, `rea.tools`,
  `rea.tools/get-started/`, `docs/installation.md`.
- Bitácora creada con `execution/bitacoras.py nueva`.
- Nota fuente reubicada de la raíz a
  `docs/AGENTE_IA/fuentes/rea-ingenieria-inversa-ia.md` (no estaba trackeada → `mv`),
  con cabecera de procedencia YAML (`tipo_fuente: repo`, `citable: no`,
  `analisis: Sessions/2026-10-12_...`) y tabla de correcciones verificadas.
- Correcciones fijadas: paquete/comando real `rea-agents` (`npx rea-agents setup`), no
  `rea-agent`; release **6.4.0** (2026-10-11); requisito **Node 22.19+/24.11+/26+**;
  cobertura mayor (ELF, Go, WASM, bytecode EVM, HAR, firmware binwalk/unblob, .NET,
  APK); clientes soportados incluyen **OpenCode** y `dsh` (solo en `main`); motores
  Hopper/IDA/JEB son comerciales, Ghidra es libre.
- Redactado `docs/AGENTE_IA/rea_evaluacion_incorporacion.tex` (10 secciones, estilo
  infográfico, preámbulo reutilizado del doc hermano graphify).
- Compilado aislado en `.tmp/latex_build/rea/` (3 pasadas `pdflatex`); corregido
  icono FA6 `shield-halved` → `shield-alt` (no existía en fontawesome5) y el único
  `Overfull \hbox` (ruta larga envuelta con `\path{}`).
- PDF copiado a `docs/AGENTE_IA/rea_evaluacion_incorporacion.pdf`; verificado con
  `python3 execution/verificar_pdf.py` → `status: ok`, 9 páginas, 0 errores, 0
  `overfull`, 0 solapes.
- Veredicto registrado: **adopción condicional** como herramienta (Capa 2), nunca como
  flujo determinista; Ghidra headless primero, Hopper/IDA diferidos; perfil MCP compacto
  y vigilancia del disco de 256 GB.

## Pendientes
- Ejecutar el piloto en la HP EliteDesk 805 G6 al llegar el equipo (criterios de
  aceptación en la §10 del PDF): `node -v`, `rea doctor --provider ghidra --json`,
  `setup --client opencode --dry-run`.
- Decidir instalación de Ghidra 12.1.x + JDK 21 (espacio en disco) y si se usa el
  segundo slot de disco.
- Pendiente global (no tocado): script de respaldo/exportación para migración de entorno
  (acordado 2026-08-27).
