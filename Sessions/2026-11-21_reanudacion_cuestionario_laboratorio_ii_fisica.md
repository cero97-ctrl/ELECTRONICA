# 2026-11-21 — reanudacion_cuestionario_laboratorio_ii_fisica

## Tema
Reanudación de la sesión del cuestionario web de **Laboratorio II de Física**
después de la pausa del 18-nov. El usuario cargó la sesión y pidió continuar.

## Contexto
- La sesión del 18-nov (`Sessions/2026-11-18_cuestionario_web_laboratorio_ii_fisica.md`)
  dejó construido el pipeline web: HTML alumno/docente para Lab I y Lab II, cada curso
  en su propio repo de Pages, dos Workers desplegados con ventana, y las reglas del token
  de resultados por entorno/repo. Todo quedó **sin commitear** al pedido del usuario.
- El 20-nov (`Sessions/2026-11-20_cuestionario_lab_i_ventana_945.md`) se hizo commit y
  push de ese trabajo (`147b7dfd`, 16 archivos) y se **movió la ventana de Lab I** a
  09:45–10:50 VET, con flip a público a las 09:45. Lab II no se tocó.
- Hoy (21-nov) el usuario recargó la sesión. Antes de actuar se verificó el estado real
  en vez de dar por bueno el de la bitácora: los dos Workers responden, las ventanas
  siguen cerradas («todavía no empieza») y los cuatro repos siguen privados.

## Decisiones (usuario)
1. **HTML sin fecha**: el usuario pidió dejarlo sin día ni hora impresos («déjalo así»,
   18-nov), aunque el dato vive en los secretos del Worker y en la bitácora.
2. Pausa acordada el 18-nov; hoy se reanuda sin cambios nuevos en la configuración.
3. Del 20-nov (vigente): Lab I abre el 26-nov a las **09:45 VET** y cierra a las
   **10:50 VET**; el flip a público se hace a la apertura, no a las 08:00.
4. Lab II conserva su ventana del 24-nov, 08:00–09:05 VET (`12:00Z`–`13:05Z`).
5. **OCR como entrada de material**: el usuario decidió usar el markdown del OCR como
   entrada para «corregir o generar material del curso» (21-nov).
6. **El OCR es la fuente de verdad de las prácticas** (21-nov): el usuario afirmó que el
   markdown «contiene las prácticas que deben hacerse en el curso tal y como lo exige la
   Universidad». Esto **supera la decisión del 4-nov** de tomar P1–P4 del `.tex` exacto
   de git HEAD: ahora las 8 prácticas se derivan del OCR.
7. **Alcance confirmado vía question tool** (21-nov): el usuario eligió la **opción 2 —
   flujo repetible de 3 capas**, y el artefacto concreto son **las 8 prácticas** (no un
   ajuste único, no `curso.yaml` completo, no material nuevo aparte). Con esto se acepta
   la alternativa conforme propuesta en la alerta de determinismo y se registra la
   excepción a la alerta de autoridad: el OCR overridea P1–P4 por decisión consciente
   del usuario.

## Actividades
- Lectura de las dos bitácoras posteriores a la pausa para recuperar el estado: la del
  18-nov (configuración original) y la del 20-nov (cambio de ventana y commit).
- `git log`: el trabajo pendiente ya está commiteado y pusheado (`147b7dfd`); `HEAD` actual
  es `42735743` (propuesta SERVIDOR_IA, ajena a este flujo). `git status` limpio salvo
  el PDF personal del usuario y esta bitácora.
- `execution/estado_sesion.py check` → `veredicto_global: ok`.
- Comprobación en vivo:
  - `cuestionarios-worker-lab2/salud` → `ok:true`, `abierta:false`, `inscritas:3`.
  - `cuestionarios-worker-lab1/salud` → `ok:true`, `abierta:false`, `inscritas:2`.
  - Visibilidad: `cuestionarios-lab1`, `cuestionarios-lab2`, `cuestionarios-resultados-lab1`
    y `cuestionarios-resultados-lab2`, todos `private`.
- Bitácora de hoy creada con `execution/bitacoras.py nueva`.
- **OCR de `practicas.pdf` completado** (el usuario pidió pasarlo a OCR→Markdown para
  usarlo como fuente; no se pudo adjuntar al prompt: 45,4 MB > 20 MiB):
  - Ya existía `cursos/LABORATORIO_II_FISICA/docs/practicas_ocr.md` (42 KB, 33 secciones:
    páginas 1–2 y 26–56), generado el 4-nov. Las páginas 3–25 se omitieron **a propósito**
    porque las prácticas 1–4 ya están en LaTeX en HEAD y esa es la fuente exacta
    (`Sessions/2026-11-04_practicas_reales_laboratorio_ii_fisica.md`). No se tocó.
  - La caché de aquella corrida sobrevivió en
    `.tmp/ocr_practicas/.cache/86a5926a079f/textos` (33 páginas). `--check` con el
    directorio por defecto `.tmp/ocr` decía 0 en caché; con `--salida .tmp/ocr_practicas`,
    33 en caché y 23 faltantes. Eso evitó repetir 33 páginas de cuota.
  - Corrida: `flujo_ocr_pdf.py --pdf cursos/LABORATORIO_II_FISICA/docs/practicas.pdf
    --salida .tmp/ocr_practicas --no-alert` → `status ok`, **56/56 páginas**, 6 peticiones,
    16 088 tokens (7 259 prompt + 8 829 respuesta), 0 vacías / 0 ilegibles / 0 faltantes.
    Entregable: `.tmp/ocr_practicas/practicas_ocr.md` (71 KB, 56 secciones `## Página N`,
    1 `[ILEGIBLE]` en la portada, 34 `[FIGURA]`). Sin créditos OpenRouter: cuota free de
    Gemini (`GOOGLE_API_KEY`, `gemini-2.5-flash`, lote 4, ancho 1400).
  - Muestreo de calidad: la página 3 conserva ecuaciones en LaTeX
    (`\[R = \frac{V}{I}\]`, `$\Omega$`); las tablas de instrumentos (páginas 54–56) llegan
    con celdas comprimidas y algunos encabezados desalineados, tal como advierte la cabecera del OCR
    curado: **no es fuente tipográfica de verdad**, los valores se contrastan contra el PDF.
- **Alerta de determinismo levantada antes de ejecutar** (guardrail de `AGENTS.md`): el
  generador `flujo_disenar_curso.py` consume `curso.yaml`, **no** markdown; los 10
  `practica_0N.tex` son generados y están trackeados. No existe script de capa 3 que
  convierta OCR-markdown → material. Leer el markdown en el chat y editar los `.tex` a
  mano sería «procesar datos inline en el chat en lugar de un script determinista
  reutilizable»: violación del espíritu determinista. Alternativa conforme propuesta:
  síntesis editorial → `curso.yaml` validado → regeneración determinista por el flujo
  (método ya usado el 4-nov), o bien crear las 3 capas si debe ser repetible.
- **Alerta de autoridad**: el 4-nov se decidió que P1–P4 se toman del `.tex` exacto de
  git HEAD, **no** del OCR, por ser ese el original tipográfico. El OCR completo nuevo
  añade justamente pp. 3–25 (P1–P4); el resto (P5–P8, tablas, fichas Keithley) ya se
  consumió el 4-nov. Realimentar P1–P4 con OCR ruidoso puede degradar contenido exacto.
  Requiere decisión explícita del usuario antes de tocar esas prácticas.

- **Flujo OCR → 8 prácticas implementado (3 capas)** tras la confirmación de la opción 2:
  - Capa 1: `directives/ocr_a_practicas.yaml` (SOP con 3 pasos, edge cases, coste cero).
  - Capa 2: `flujo_ocr_a_practicas.py` (valida entradas, lanza la capa 3 como subproceso,
    valida entrega, guarda vista `run_state`, alerta; `--check`/`--dry-run` sin coste).
  - Capa 3: `execution/generar_practicas_desde_ocr.py` (parseo puro, validación,
    renderizado infográfico reutilizando `_tm`/`_lista` de `generar_material_curso.py`
    y `PREAMBULO_INFOGRAFIA`, compilación aislada con 0 líneas `!`).
  - Correcciones al validar contra el OCR real: (1) cabeceras irregulares
    (`PRÁCTICA`/`PRACTICA`, con/sin negrita); (2) el contenedor `3. PARTE EXPERIMENTAL`
    cuelga figuras en P8 y debe renderizarse; (3) `[FIGURA: ...]` a veces va **inline** al
    final de un párrafo → `_separar_figuras_inline`; (4) `_validar_matematica` solo
    entiende `$...$` y daba falsos positivos sobre el display math `\\[ ... \\]` →
    validador propio `validar_matematica_ocr`.
  - Verificación: `--check` → ok, 8 encontradas, 0 problemas. Generación real en
    `.tmp/practicas_desde_ocr/` → 8 `.tex` + 8 `.pdf`, 0 líneas `!` y 0 `Overfull \hbox`
    en los 8 logs, `sha_conjunto=899466f16fa24345` (idéntico en dos corridas).
  - Tests: `execution/test_generar_practicas_desde_ocr.py` → 70 aserciones, 0 fallos.
    Diagrama ISO 5807: `docs/AGENTE_IA/ocr_a_practicas_flujo.{tex,pdf}` (5 pp., 0 errores).
    `AGENTS.md` actualizado (test + comando del orquestador).
  - **NO se han sobrescrito** las prácticas trackeadas en
    `cursos/LABORATORIO_II_FISICA/practicas/`: el trabajo quedó en `.tmp/` a la espera de
    que el usuario decida el destino final y autorice escribir/committear.

## Pendientes
- **24-nov, 08:00 VET — Lab II**: publicar con
  `python3 flujo_publicar_cuestionario.py --web-dir cursos/LABORATORIO_II_FISICA/evaluaciones/web --repo cero97-ctrl/cuestionarios-lab2 --visibilidad public --push`
  (Pages tarda ~1 min). A las **09:05** el mismo comando con `--visibilidad private`
  y después `flujo_acta_cuestionario.py` sobre `cuestionarios-resultados-lab2`.
- **26-nov, 09:45 VET — Lab I**: el mismo par de comandos sobre
  `cursos/LABORATORIO_I_FISICA/evaluaciones/web` / `cuestionarios-lab1`; cerrar a las
  **10:50** y armar el acta de `cuestionarios-resultados-lab1`. El aviso de apertura debe
  decir 09:45–10:50, no 08:00–09:00.
- **No tocar la ventana de Lab II**: cambiar solo el inicio dejaría el fin antiguo antes
  del inicio y el Worker rechazaría las 3 entregas con 403 (trampa ya documentada el 20-nov).
- **OCR completo como entrada de material — RESUELTO**: `.tmp/ocr_practicas/practicas_ocr.md`
  (56 páginas) se usó como fuente del flujo OCR → 8 prácticas (3 capas), ver Actividades.
  Queda **decidir el destino final**: las 8 prácticas generadas están en
  `.tmp/practicas_desde_ocr/`. Sobrescribir `cursos/LABORATORIO_II_FISICA/practicas/`
  (trackeadas, derivadas antes de `curso.yaml`) requiere autorización del usuario; no se
  hizo. Si se promueve el markdown a `docs/`, usar nombre nuevo
  (`practicas_ocr_completo.md`) sin sobrescribir el OCR curado de 33 páginas.
- El HTML no imprime día ni hora: pendiente cerrado por decisión del usuario.
- **Bug latente heredado (no corregido)**: `flujo_desplegar_worker_cuestionarios.py`
  duplica el bloque `extras` + `_secretos` + `GITHUB_TOKEN` dentro de la rama
  `if not presentes["GITHUB_TOKEN"]` (aprox. líneas 510–545 y 557–592). No se ejecutó
  porque el token ya está fijado; en un redespliegue sin él escribiría los secretos dos
  veces. Se dejó para otra sesión según acuerdo del 20-nov.
- Fuera de alcance por acuerdo previo: `cursos/LABORATORIO_I_FISICA/ALUMNOS_LAB_I_FISICA.pdf`
  (trabajo del usuario, sin trackear).
