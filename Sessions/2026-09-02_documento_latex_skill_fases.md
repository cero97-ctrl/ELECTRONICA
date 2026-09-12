# Sesión: Generación de Documento LaTeX Infográfico (Fases 1 y 2 de Skills IA)

Fecha: 2026-09-02
Tema: Unificación y compilación LaTeX de la Fase 1 (destilación de libros a skills) y Fase 2 (resolución de problemas con oráculo SymPy).

## Actividades

1. **Revisión de directivas y guías LaTeX:**
   - Lectura de `.agent/latex.md` (prevención de 16 errores comunes de LaTeX en el proyecto).
   - Aplicación del estilo infográfico institucional de `execution/estilo_infografia.py` (`sourcesanspro`, `\bandaTitulo`, `tarjetaDato`, `cajaRecuerda`, `cajaConcepto`, `cajaAlerta`, paleta de colores oscura tecnológica).
2. **Generación de `docs/AGENTE_IA/skill_fases_1_y_2.tex`:**
   - Integración completa y estructurada del contenido de:
     - `docs/AGENTE_IA/fase1_libro_a_skill.md` (Parte I: arquitectura de 3 capas, extracción, chunking determinista, motor `sintetizar_skill.py`, saneo JSON, validación neuro-simbólica y gate de instalación).
     - `docs/AGENTE_IA/fase2_resolver_skill.md` (Parte II: retrieval de embeddings, formulador LLM, oráculo SymPy en sandbox, bucle de reflexión, validación experimental en BJT y análisis de costes).
   - Inclusión de parte comparativa integral (Parte III) y tablas de comandos operativos.
3. **Compilación y limpieza:**
   - Compilación a PDF en `docs/AGENTE_IA/skill_fases_1_y_2.pdf` en doble pasada con `pdflatex` para resolución de referencias cruzadas y tabla de contenidos.
   - Limpieza de archivos auxiliares mediante `clean_latex.py`.

## Decisiones

- Se unificaron ambas fases en un único documento técnico estructurado en 3 partes, facilitando el estudio y referencia integral del pipeline neuro-simbólico.
- Se respetaron estrictamente las convenciones de `estilo_infografia.py` y los estándares de `.agent/latex.md` (manejo de paths con `\path{}`, comillas sin shorthand de babel, listings protegidos).
