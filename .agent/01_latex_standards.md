# Estándares para Documentos y Tesis en LaTeX

- **Codificación e Idioma:** Todo documento debe utilizar `\usepackage[utf8]{inputenc}`, `\usepackage[T1]{fontenc}` y `\usepackage[spanish]{babel}`.
- **Estructura Base:** Utilizar preferiblemente las clases `article` o `report` a 12pt en formato `a4paper`.
- **Estilo de Código:** Utilizar el paquete `listings` definiendo colores apropiados (ej. para bloques de Python, Verilog o TCL).
- **Revisión Académica:** 
  - Al corregir o analizar propuestas de grado, adoptar un enfoque crítico y constructivo. 
  - Asegurar que los objetivos sigan la metodología SMART (Específicos, Medibles, Alcanzables, Relevantes, a Tiempo).
  - Promover el desglose de proyectos grandes (Modularización y Priorización) para hacerlos viables académicamente.
- **Cumplimiento Estricto:** Prestar estricta atención a las reglas documentadas en `/home/cero/MEGA/VS_CODE_WORKSPACE/ELECTRONICA/.gemini/latex.md` para evitar problemas comunes de compilación y estilo. Las respuestas que incluyan código deben ser directamente compilables.
- **Consulta Previa de Errores Registrados:** Antes de crear o modificar un archivo `.tex`, consultar el registro histórico de errores en `.agent/latex.md` para evitar cometer fallos ya documentados (falta de `amsmath`, nodo `full diode bridge`, `pC` deprecado, forward references, etc.).