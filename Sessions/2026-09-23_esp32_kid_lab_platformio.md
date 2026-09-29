# 2026-09-23 — esp32_kid_lab_platformio

## Tema
Creación de documento técnico LaTeX sobre PlatformIO en el entorno del proyecto ESP32 Kids Lab y consolidación de directorio.

## Contexto
- El usuario solicitó inicialmente crear un documento en LaTeX dentro de la carpeta `docs/ESP32_KID_LAB` con una descripción completa de qué es PlatformIO.
- En el repositorio existía previamente la carpeta `docs/ESP32_KIDS_LAB` con documentación del proyecto (`ESP32_Kids_Lab.tex`) y una imagen asociada (`platformio.jpeg`).
- Posteriormente, el usuario aclaró que la carpeta de destino correcta es `docs/ESP32_KIDS_LAB` y solicitó eliminar cualquier redundancia, conservando únicamente dicha carpeta.

## Decisiones (usuario)
1. Se generó el documento en formato LaTeX (`platformio.tex`) estructurado profesionalmente y se compiló a PDF (`platformio.pdf`) dentro de `docs/ESP32_KIDS_LAB/`.
2. Se eliminó el enlace simbólico `docs/ESP32_KID_LAB` para evitar duplicidad o redundancia, manteniendo exclusivamente el directorio canónico `docs/ESP32_KIDS_LAB/`.
3. Se contextualizó la imagen preexistente `platformio.jpeg` en una subsección específica sobre recomendaciones de memoria y optimización de caché durante compilaciones de PlatformIO.

## Actividades
- Redacción integral de `docs/ESP32_KIDS_LAB/platformio.tex` abarcando:
  - Definición y filosofía de PlatformIO frente al Arduino IDE tradicional.
  - Los 6 pilares clave: Multiplataforma, gestión de dependencias (`lib_deps`), configuración declarativa (`platformio.ini`), motor SCons, depuración unificada (`Unified Debugger`), y pruebas unitarias (`Unity`).
  - Estructura estándar de directorios en PlatformIO.
  - Análisis detallado del `platformio.ini` del proyecto `ESP32 Kids Lab` (LittleFS, modo `deep`, dependencias asíncronas).
  - Recomendaciones de recursos y caché de compilación (vinculadas a `platformio.jpeg`).
  - Tabla comparativa técnica: PlatformIO vs. Arduino IDE.
  - Comandos principales de la CLI (`pio run`, `pio run --target uploadfs`, etc.).
- Compilación de doble pasada con `pdflatex` y resolución de hipervínculos, índice y figuras sin advertencias ni errores.
- Limpieza de archivos temporales mediante `clean_latex.py`.
- Eliminación del enlace/carpeta `docs/ESP32_KID_LAB` para conservar únicamente `docs/ESP32_KIDS_LAB/`.

## Pendientes
- Ninguno por parte de esta tarea. El documento está completamente generado y el directorio consolidado.
