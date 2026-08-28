# Sesión 2026-08-27 — Skill global `computacion_cientifica` (GSL y ecosistema open-source)

**Fecha:** 2026-08-27
**Tema:** Convertir el prompt `docs/AGENTE_IA/GSL.md` en un skill de agente bajo demanda, ampliado con buenas prácticas
**Estado:** Implementado e instalado en global

## Contexto

El usuario pidió analizar `docs/AGENTE_IA/GSL.md` (prompt que enruta al LLM hacia la mejor
selección de bibliotecas científicas open-source: LAPACK/BLAS/OpenBLAS, GSL, FFTW, NLopt/Ceres,
ODEPACK, Julia/NumPy-SciPy, Netlib) y evaluar si conviene integrarlo al proyecto.

## Análisis / Decisión

- El contenido es sólido y alineado con la regla base del proyecto ("priorizar herramientas
  open-source", AGENTS.md y AGENT_INSTRUCTIONS.md); lo vuelve concreto y accionable por dominio.
- **NO conviene como contexto permanente** (`.agent/*.md` se carga en toda sesión; el proyecto
  no tiene hoy código HPC, solo C++ embebido/ESP32 y Python). Forzarlo siempre gastaría tokens
  y generaría ruido.
- Es una **guía de estilo técnica** (compatible con `.agent/latex.md` / `.agent/python.md`),
  no lógica de negocio ni decisión de modelo, por lo que no viola la regla de determinismo.
- **Opción elegida (A): skill bajo demanda**, coherente con la filosofía de skills que se
  consolidó en el `flujo_libro_a_skill`. El skill se instala en global
  (`~/.config/opencode/skills/computacion_cientifica/`) para ser reutilizable en cualquier
  proyecto.

## Actividades / Artefactos

- **`~/.config/opencode/skills/computacion_cientifica/SKILL.md`** (nuevo, global): skill
  basado en el GSL.md, ampliado con buenas prácticas:
  - Ecosistema por dominio (Álgebra lineal, GSL, FFTW, NLopt/Ceres, ODEPACK, NumPy-SciPy/Julia, Netlib).
  - Verificación numérica (residuo, número de condición, solución analítica, doble precisión).
  - Manejo de errores numéricos y de dominio (códigos de retorno GSL, NaN/Inf).
  - Thread-safety (RNG por hilo, planes FFTW por hilo).
  - Linkage GSL (`gcc -lgsl -lgslcblas -lm`, `-lopenblas`, `gsl-config`).
  - Reproducibilidad (semilla RNG fija, versión de bibliotecas, flags de compilación).
  - Benchmarking / aprovechamiento de hardware (SIMD, -O2/-O3, -march=native).
- **`~/.config/opencode/skills/computacion_cientifica/references/bibliotecas_y_linkage.md`**
  (nuevo, global): tabla de bibliotecas por dominio, guía de instalación/compilación GSL,
  cabeceras frecuentes y checklist de verificación numérica.

## Pruebas realizadas

- ✅ Validación del frontmatter del skill: `name == carpeta`, `description` presente, YAML
  válido (se cita la description con comillas dobles por el `: ` interno que rompía el parser).
- ✅ Estructura correcta: `SKILL.md` + `references/bibliotecas_y_linkage.md`.

## Notas

- El skill global vive fuera del repo; solo el log de sesión se commitea en ELECTRONICA.
- Requiere **reiniciar opencode** para que el skill cargue (la config no se recarga en caliente).
- Lección reusable: en YAML frontmatter de skills, si la `description` de una línea contiene
  `: ` (dos puntos + espacio), citarla entre comillas dobles para evitar `ScannerError`.
