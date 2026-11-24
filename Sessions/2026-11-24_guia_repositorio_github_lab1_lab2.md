# 2026-11-24 — guia_repositorio_github_lab1_lab2

## Tema
guia_repositorio_github_lab1_lab2

## Contexto
- (Por qué se aborda / eventos detectados que motivan la sesión.)

## Decisiones (usuario)
1. (Acuerdos explícitos del usuario. NO inventar; si no hay, anotar qué se
   asumió y por qué.)

## Actividades
- (Qué se hizo: pasos, scripts, salidas, veredictos.)

## Pendientes
- (Qué queda abierto; pendientes acordados de otras sesiones que NO se tocaron.)

## Tema
Guías de repositorio GitHub para Laboratorio I y II de Física

## Contexto
- Se solicitó redactar un documento (tex,pdf) con instrucciones para estudiantes de Laboratorio I y II de Física sobre crear la estructura de carpetas guiada por las plantillas y hacer push a GitHub.
- Entregables en `cursos/LABORATORIO_I_FISICA/docs/` y `cursos/LABORATORIO_II_FISICA/docs/`.

## Decisiones (usuario)
- Formato: dos documentos específicos por curso (uno por docs/), cada uno con nombre, URL de plantilla y particularidades propias.

## Actividades
- Inspeccionadas plantillas `plantillas/repo_grupo` de ambos cursos (README, .gitignore, estructura semana_01..10 con datos/analisis/figuras/README.md y semana_10/portafolio).
- Revisado estilo infográfico (`execution/estilo_infografia.py`) y guías existentes en `docs/` de ambos cursos.
- Generados `.tex` con preámbulo infográfico, secciones: requisitos, plantilla oficial, estructura obligatoria, creación en PC (copiar plantilla / desde cero), personalización, creación de repo privado en GitHub, primer push, autenticación HTTPS/PAT o SSH, verificación y errores comunes.
- Compilación aislada con `execution/compile_latex.py` en `.tmp/latex_build/`; corregido uso de `cajaFortaleza` como entorno (debe ser estilo de `tcolorbox`, ver `.agent/latex.md` §17). Recompilación final: 0 errores `!`, 0 Overfull hbox, PDFs copiados a destinos.

## Pendientes
- Confirmar con el usuario si desea commitear los nuevos `.tex/.pdf` y la bitácora.
