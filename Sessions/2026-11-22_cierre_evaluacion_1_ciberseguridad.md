# 2026-11-22 — Cierre Evaluacion 1 Ciberseguridad

## Tema
Cierre de la Evaluación 1 del examen remoto de Ciberseguridad (16-nov-2026) con acta definitiva de 11 calificaciones.

## Contexto
- El acta consolidada `SEMANA_01/acta_semana_01.{tex,pdf}` reflejaba solo 9 entregas de una nómina de 11; dos alumnos del G4 Legal no entregaron. El promedio numérico vive solo en el acta local, no en esta bitácora.
- Se planteó si existía recuperación del 17-nov que cerrara la cobertura. La verificación solo lectura no encontró artefactos: ningún entorno `*_recuperacion` en `wrangler.jsonc`, ni fuentes/HTML/actas de recuperación, ni `.tmp/verificados_*.csv`, ni bitácora `Sessions/2026-11-17*.md`. Los 4 Workers reportan `ventana.abierta=false`, `motivo="ya terminó"`, `inscritas=11`.
- `flujo_fusionar_actas.py` exige actas de recuperación reales; forzarlo fabricaría datos. Por eso la cobertura se cierra con dos ceros por inasistencia no justificada, no con una fusión.

## Decisiones (usuario)
1. **No asumir recuperación del 17-nov**: no hay artefactos verificables; no aplica.
2. **No fusionar actas**: no existen actas de recuperación; inventarlas violaría el determinismo.
3. **Los 2 ausentes no justificaron → 0 puntos**, con el 0 y su motivo en el acta de 11 filas: dos estudiantes del G4 Legal, identificados solo en el acta local (repo público).
4. **Promedio final** sobre 11 registrado únicamente en el acta local; las cifras no se reproducen aquí para no exponer resultados.
5. **Los PDF por rol siguen siendo registro de entregas**; solo `acta_semana_01.{tex,pdf}` refleja las 11 notas finales.
6. **«Listo, ya estás en build»** → autorización para implementar y regenerar, **NO** para commitear. Queda pendiente la revisión y autorización explícita del usuario para el commit.
7. Se alertó el determinismo y el plan aprobado: toda lógica nueva vive en 3 capas (directiva + orquestador + script con tests); ni CSV ni PDF se editan a mano; ninguna decisión se toma en el chat.
8. Alerta de determinismo dada y aceptada; registrada aquí como excepción **no** (se procedió conforme, sin romper la arquitectura).
9. Al mostrarse el `git diff` y pedirse autorización para commitear, el usuario eligió **«Esperar mi revisión»**. No hay autorización de commit: los 9 archivos quedan en el árbol de trabajo, sin `git add` ni `git commit`.

## Actividades
- Contexto recuperado de `Sessions/2026-11-15_...` y `Sessions/2026-11-16_examen_remoto_preflight_y_nomina_oficial_de_11.md`.
- Verificación solo lectura de los 4 Workers (`/salud`) y del repo privado `cero97-ctrl/cuestionarios-resultados`: 9 entregas en 4 roles (Rojo 2/2, Azul 3/3, Púrpura 3/3, Legal 1/3).
- `python3 execution/estado_sesion.py check` → `veredicto_global: ok` (sin huérfanos que purgar).
- Capa 3 nueva: `execution/calificaciones_inasistencia.py` (`leer_descriptor`, `filas_para`, `incorporar`) con validación de claves, fecha ISO, `total_preguntas`, cédula/grupo/nota, duplicados, cédula ya entregada y cédula ajena a la nómina.
- `execution/descargar_resultados.py`: estados `ESTADO_OK`/`ESTADO_SIN_ENTREGA`, `es_sin_entrega()`, `resumen()` con `entregas`/`sin_entrega_calificados`/`notas_finales`/`promedio_final` (conserva `promedio` histórico) y `latex_acta()` con icono azul (`azulNoche`, **no** `azulTitulo`: ese color no existe en la paleta infográfica y la primera compilación falló por eso), caja «Cobertura cerrada», tarjetas de calificaciones finales y nota explicativa al pie. Los ausentes quedan fuera de «A revisar a mano».
- `execution/acta_semana.py`: `--calificaciones`, cobertura medida **antes** de incorporar las filas, JSON con 9 entregas + 2 calificaciones (11 notas finales) y `faltantes_sin_calificar`.
- Capa 2: `flujo_acta_cuestionario.py` pasa `--calificaciones`, verifica `notas_finales == entregas + sin_entrega_calificados` y reporta `promedio_final`.
- Capa 1: `directives/acta_cuestionario.yaml` documenta el descriptor, la cobertura cerrada y los casos límite (ya entregó, ajeno a nómina, grupo divergente, total distinto, falta recuperación).
- Descriptor (git-ignorado, única fuente de los dos ceros): `cursos/CYBERSEGURIDAD/evaluaciones/resultados/calificaciones_inasistencia.yaml`, sha256 `4b381d8a1c935f7740fe9cedc3b7c69ad45fccc3765eaf57c7e5a1ae56c6250c`.
- Tests: `execution/test_calificaciones_inasistencia.py` (31/31), `execution/test_acta_semana.py` (76/76), `execution/test_descargar_resultados.py` (120/120). Sin red ni pdflatex.
- Regeneración: `python3 flujo_acta_cuestionario.py --consolidar --semana 1 --listas-dir .tmp --curso CIBERSEGURIDAD --calificaciones cursos/CYBERSEGURIDAD/evaluaciones/resultados/calificaciones_inasistencia.yaml --json --no-alert` → `status: ok`, 9 entregas + 2 calificados, 11 notas finales, `a_revisar: 0`, `overfull: 0`.
- `python3 execution/verificar_pdf.py` sobre `SEMANA_01/acta_semana_01.pdf` → `{"status":"ok","paginas":2,"errores":[],"overfull":[],"solapes":[],"solapes_total":0}`.
- Hashes del entregable: `.tex` `b4788744aced5dd6b65bca2e8f65e25c13758f4c5761e926da8938afbbddb7de` · `.pdf` `0e4fcc77fc56504606f73248c6d860649fb90ee233c4d55fa97222f6c4cb645b`. Copias previas (9 filas) en `.tmp/acta_semana_01_antes.{tex,pdf}`.
- `git status`: 6 archivos modificados y 3 nuevos (bitácora + módulo + test); el descriptor y el acta quedan fuera del índice por `resultados/**` (privacidad).

## Pendientes
- **El usuario eligió esperar su revisión (2026-11-22).** No commitear, no hacer `git add`, no tocar el índice hasta nueva autorización explícita. `git diff` ya fue mostrado; los PDF se abrieron localmente (este modelo no despliega PDF/imágenes en el chat).
- Si el usuario autoriza, commitear los 9 archivos de código/documentación (el descriptor de calificaciones NO viaja por git: contiene nombres y cédulas).
- Regenerar el acta si apareciera una recuperación verificable: sustituir el descriptor por actas reales y usar `flujo_fusionar_actas.py`.
- Ejecutar `python3 execution/bitacoras.py check` al cierre de la sesión (hecho: ver activities; si el comando reporta algo, corregir antes de terminar).
