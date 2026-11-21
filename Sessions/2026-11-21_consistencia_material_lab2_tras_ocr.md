# 2026-11-21 — consistencia_material_lab2_tras_ocr

## Tema
Tras reemplazar P01–P08 por el OCR+TikZ del escaneo, auditar `docs/`,
`evaluaciones/`, `laboratorio/`, `plan_estudios/` y `README.md`, y aplicar los
ajustes autorizados por el usuario.

## Contexto
- El escaneo `docs/practicas.pdf` (56 pp., UDO 2011) pasó a ser la fuente del
  desarrollo de P01–P08 el 21-nov-2026; P09–P10 siguen intactas (mismo SHA-256).
- Los títulos y el orden del temario no cambiaron, así que `plan_estudios/`,
  `docs/guia_estudiante.tex`, `docs/semana_1.tex` y `laboratorio/` siguen vigentes.
- Sí aparecieron tres frentes reales:
  1. El cuestionario web del 24-nov se generó el 18-nov y cuatro preguntas citaban
     texto que ya no existe en las prácticas (Q4 voltímetro antes del amperímetro,
     Q7 contrato JSON de la Práctica 01, Q9 fórmula «especificada en la práctica»,
     Q10 «8 pares / 20 pares»).
  2. `README.md`, `curso.yaml` y `docs/practicas_ocr.md` seguían afirmando que
     `curso.yaml` es la fuente única de verdad y que las P1–P4 venían de LaTeX.
  3. El OCR íntegro vivía solo en `.tmp/` (ignorado): un clone no podía regenerar
     P01–P08.

## Decisiones (usuario)
1. Alcance autorizado: **«Todo: cuestionario + redeploy + documentación»** —
   corregir Q4/Q7/Q9/Q10 en las fuentes, regenerar HTML, re-desplegar el Worker de
   Lab II y actualizar `README.md`, `curso.yaml` y `docs/practicas_ocr.md`.
2. Decisiones heredadas respetadas: el OCR manda sobre el YAML para P01–P08;
   P09–P10 no se tocan; sin commit/push sin autorización explícita.
3. Se decidió además promover el OCR completo a `docs/practicas_ocr_completo.md`
   y republicar el HTML corregido al repo privado de Pages, sin cambiar la
   visibilidad (sigue 404 hasta el 24-nov). Ambas acciones son consecuencia directa
   del alcance autorizado: sin ellas el alumno vería el cuestionario viejo.

## Actividades
- **Auditoría inicial (solo lectura)**: 0 cambios en `plan_estudios/` y
  `laboratorio/`; `evaluaciones/banco_preguntas.yaml` y los controles cubren temas
  vigentes; «8 de 9 prácticas» de la final sigue correcto.
- **Copia de seguridad** de las seis fuentes/HTML implicados en
  `.tmp/cuestionario_lab2_20261121_backup/` (sha del HTML alumno antiguo:
  `2558e1dd…`). Las fuentes están gitignored a propósito: no había red de seguridad.
- **Cadena determinista reproducida** (sin lógica nueva en el chat):
  1. `execution/dividir_cuestionario.py --canonico …_origen.md --fuente …md
     --respuestas …_respuestas.md --titulo "Lab II de Física - Características I-V"
     --curso LABORATORIO_II_FISICA --grupos 3 --forzar` → 36 normalizaciones,
     clave `A`×10 (idéntico al 18-nov).
  2. `execution/barajar_cuestionario.py --canonico …_respuestas.md --forzar` →
     semilla `lab_ii_fisica_cuestionario_respuestas`, clave final
     `A D D B D A B A A B`, no degenerada. **La clave no cambió** respecto al
     Worker desplegado, pese al cambio de enunciados.
  3. Re-división desde el canónico barajado → fuente sin clave,
     `normalizaciones: 0`, `cargar_clave` en verde.
- **Correcciones de contenido** (en `_origen.md`, con la respuesta correcta aún
  en A para conservar la permutación): Q4 pasa a plantear la configuración como
  hipótesis explícita, sin atribuirla a la guía; Q7 atribuye el contrato JSON a la
  sección real «Contrato de datos de los scripts» de `guia_estudiante.tex`; Q9
  presenta la fórmula de mínimos cuadrados como herramienta del análisis, no como
  texto de la práctica; Q10 elimina los números de ensayos inventados y pregunta
  por la razón física de la densidad de puntos en el diodo.
- **Worker**: `--check` en verde (ventana `2026-11-24T12:00:00Z`–
  `2026-11-24T13:05:00Z`, 65 min = 60 de examen + 5 de holgura). Despliegue real
  con `--env lab2 --actualizar-fuente`: `salud: true`, secretos
  `CLAVE_JSON/GITHUB_TOKEN/CEDULAS/VENTANA_INICIO/VENTANA_FIN/MIN_JUSTIFICACION`
  presentes, `clave_sha256=c7d708e0…`, `inscritas: 3`. Sin `--nomina`, el secreto
  `CEDULAS` persistió.
- **HTML**: `flujo_evaluacion_web.py --fuente …` regeneró alumno/docente/índice
  (10 preguntas). Verificación: 0 fugas (`const CLAVE`, `Answer:`, `Respuesta:`,
  `Pista:`, `Explicación:`, `✓`, `✗`, `Modo docente`), 10 preguntas,
  `const ENTREGA_URL` presente, clave del docente idéntica a la del Worker y solo
  dos URLs externas (MathJax + Worker). Nuevo sha del alumno: `0eeeaa7a…`.
- **Pages**: `flujo_publicar_cuestionario.py --web-dir … --repo
  cero97-ctrl/cuestionarios-lab2 --visibilidad private --push` subió el HTML
  corregido con el mismo sha `0eeeaa7a…`; `pages_visible: false` (404 hasta el
  día del examen). Los repos de los cuatro roles no se tocaron.
- **Documentación**:
  - `README.md`: tabla con las tres fuentes de verdad, aviso explícito de que
    `flujo_disenar_curso.py` sin `--solo` pisa P01–P08 y sus 34 figuras, y comando
    seguro con `--solo silabo,plan_semanal,guia,controles,final,rubrica,laboratorio,readme`.
  - `curso.yaml` (solo comentarios de cabecera): deja de llamarse «fuente única»;
    acredita el PDF de la UDO para P01–P08 y advierte del mismo peligro.
  - `docs/practicas_ocr.md`: corrige la cobertura anticuada y apunta al OCR íntegro.
  - `docs/practicas_ocr_completo.md`: copia byte a byte de
    `.tmp/ocr_practicas/practicas_ocr.md` (sha `8899019f…`, 56 páginas).
- **Validaciones**: `curso.yaml` parsea con PyYAML (10 semanas);
  `verificar_texto.py` sobre los cuatro ficheros modificados y la bitácora sin
  hallazgos (4649 líneas escaneadas); sin caracteres de ancho completo nuevos.
- **Auditoría de higiene parcial** (`flujo_auditar_repo.py --solo
  texto,bitacoras,estado_sesion,untracked,pdf_stale`): `bitacoras` y `untracked`
  en ok; avisos conocidos en `pdf_stale` y `estado_sesion`. `texto` quedó en fallo
  con **13 hallazgos preexistentes**, todos `ancho_completo U+FF1B` en las líneas
  `Topics covered`/`Keep learning` de los canónicos privados (6 en Lab II y 7 en
  Lab I, gitignored). La copia de seguridad anterior tiene los mismos 6 en Lab II:
  **ninguno fue introducido por esta sesión** ni está en los ficheros tocados.

## Pendientes
- **Commit/push SIN hacer**: el usuario autorizó el alcance, no git. Incluye los
  cuatro ficheros de documentación (trackeables) más la bitácora. Las fuentes y el
  HTML del cuestionario están gitignored por diseño: no viajan en el commit, pero
  ya están corregidos en local y publicados en el Worker/Pages.
- El 24-nov, antes de las 08:00 VET, hacer `flujo_publicar_cuestionario.py …
  --visibilidad public --push` para Lab II y volver a `private` al cerrar.
- Riesgo **documentado pero no blindado**: `flujo_disenar_curso.py` completo sigue
  pudiendo sobrescribir P01–P08. Si se quiere barrera en código (y test), abrir
  otra sesión; no se hizo porque el alcance era documentación.
- Los 13 `U+FF1B` de los canónicos privados siguen ahí (6 Lab II, 7 Lab I). No se
  corrigieron para no alterar el canónico-evidencia ni el conteo documentado de
  36 normalizaciones; las copias derivadas ya los normalizan. Si se quiere el
  `texto` en verde, corregirlos en ambos canónicos y re-ejecutar la cadena
  (normalizaciones bajaría a 30).
- Hallazgo heredado sin tocar: `flujo_desplegar_worker_cuestionarios.py` duplica
  el bloque de secretos si `GITHUB_TOKEN` no está presente (ver bitácora
  2026-11-20); hoy no se ejecutó porque el token sí está fijado.
- `ALUMNOS_LAB_I_FISICA.pdf` (trabajo ajeno, sin trackear) sigue intacto.
