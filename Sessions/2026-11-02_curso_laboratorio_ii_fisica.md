# 2026-11-02 — curso_laboratorio_ii_fisica

## Tema
Diseñar y generar el curso completo de **Laboratorio II de Física** en
`cursos/LABORATORIO_II_FISICA/`, partiendo del índice escaneado en
`cursos/LABORATORIO_II_FISICA/docs/contenido.pdf` y usando el flujo determinista
existente (directiva → orquestador → `execution/generar_material_curso.py`).

## Contexto
- `contenido.pdf` es un **escaneo de 1 página** (Simple Scan): `pdftotext` devuelve 1
  carácter y no hay `tesseract` instalado. Se OCR-eó con `google.genai`
  (`gemini-2.5-flash`) sobre un PNG generado con `pdftoppm -r 220 -png -singlefile`
  (`/tmp/opencode/lab2/contenido.png`).
- El PDF **solo trae el índice**: Prefacio; P1 Manejo del instrumental eléctrico y
  característica I–V; P2 Determinación de una resistencia; P3 Resistencia interna de
  voltímetro/amperímetro/fuente; P4 Circuitos eléctricos; P5 Elementos no lineales,
  diodo; P6 Respuesta de R, L y C a tensión senoidal; P7 Circuitos resonantes;
  P8 Carga y descarga de un capacitor; tablas de C/L; datos técnicos de instrumentos;
  bibliografía. El contenido detallado no existe: hay que redactarlo desde física
  estándar.
- El generador `execution/generar_material_curso.py` (Layer 3) funcionaba, pero con
  ~20 textos **cableados al dominio de ciberseguridad** (icono `shield-alt`,
  "Repositorio GitHub", "contenedor del laboratorio o sistema con autorización
  escrita", rúbrica fija de 5 criterios, contrato de datos con JSON de escaneo de
  puertos, `semana_10` fijo en el final). Reutilizarlo para física **no rompía**:
  emitía texto del dominio equivocado, que es el fallo más silencioso posible.
- El descriptor de referencia del esquema completo sigue siendo
  `cursos/CYBERSEGURIDAD/curso.yaml`.

## Decisiones (usuario)
Las seis preguntas de diseño se respondieron con la opción recomendada:
1. El **contenido detallado lo redacta el agente** desde física estándar (el PDF solo
   aporta los títulos).
2. Carpeta destino: la **existente** `cursos/LABORATORIO_II_FISICA/` (donde vive el PDF).
3. Duración **10 semanas**: 1–8 = las ocho prácticas del índice; 9 = práctica
   integradora RLC; 10 = evaluación final práctica y cierre.
4. Evaluación: **prácticas 60 / controles 20 / final 20**, escala 10, mínima 5.
5. Entrega: **repositorio GitHub privado por grupo** (`informe/`, `datos/*.csv`,
   `analisis/*.py`, `figuras/`).
6. Profundidad: práctica **completa** (fundamento teórico, materiales, tabla de datos,
   análisis de incertidumbres) → **requiere extender el generador** de forma
   retrocompatible.

Plan presentado y **aprobado textualmente** por el usuario ("ok, plan aprobado"):
extender el generador con campos opcionales (defaults = comportamiento actual),
actualizar la directiva, añadir test determinista, escribir `curso.yaml`, generar y
verificar.

7. Ante el agotamiento de la cuota Free del motor (17:35 UTC), el usuario eligió
   **esperar el reset (~7 h)** en vez de conmutar de motor (que reiniciaría opencode)
   o seguir a riesgo de corte. El trabajo queda pausado en el punto de los Pendientes;
   nada se revierte.
8. **Dejar borrados** los 9 ficheros trackeados de `cursos/LABORATORIO_II_FISICA/`
   (ver "Incidente de ficheros borrados"). El usuario decidió NO restaurarlos: el
   contenido del curso se sigue redactando desde física estándar (decisión 1), y esos
   ficheros no se usan como fuente. **No restaurarlos en la próxima sesión.**

## Actividades
- OCR del índice y extracción completa del temario (ver Contexto).
- Exploración del flujo de 3 capas: `directives/disenar_curso.yaml`,
  `flujo_disenar_curso.py`, `execution/generar_material_curso.py`,
  `cursos/CYBERSEGURIDAD/curso.yaml`, `directives/rubricas/rubrica_practica_lab.yaml`,
  `directives/evaluar_practica_laboratorio.yaml`.
- Verificación del toolchain: `pdflatex` (TeX Live 2023) + `latexmk`; presentes
  `tcolorbox`, `fontawesome5`, `sourcesanspro`, `circuitikz`, `siunitx`. Sin `pgfplots`
  → las gráficas las hace el alumno con Python, no el LaTeX.
- Higiene de sesión: `python3 execution/estado_sesion.py check` → `veredicto_global: ok`
  (sin huérfanos que purgar).
- **Generador extendido** (`execution/generar_material_curso.py`), todo retrocompatible:
  - `_UNICODE` + griegas y símbolos (`Ω μ µ τ θ φ ω α β π λ Δ ≈ ≠ ∞`) para que la prosa
    con unidades no rompa `pdflatex`.
  - Helpers nuevos: `_texto(datos, clave, defecto)` (textos parametrizables),
    `_carpeta_entrega(datos, n)` (plantilla `entregas.carpeta`, p. ej.
    `semana_{n:02d}`, con caída al patrón histórico si la plantilla es inválida),
    `_tabla_columnas(columnas, filas, caption, nota)` (tabla de N columnas con celdas
    LaTeX **crudas**, porque llevan `$V$` y `\si{\ohm}`), `_validar_tabla(tabla, etiqueta)`.
  - `_documento()` toma `meta.icono` (default `shield-alt`), sanitizado con regex.
  - `validar()`: `evaluacion.rubrica` (cada criterio con clave ASCII
    `[a-z][a-z0-9_]*`, `peso`, `descripcion`; pesos suman 10), `practica.tabla_datos`
    y `apendices[].tabla` (filas alineadas con la cabecera), apéndice sin contenido.
  - `tex_silabo()`: línea "Entrega" sin la palabra "Repositorio"; sección Laboratorio
    **condicional** a `laboratorio.imagenes`.
  - `tex_plan_semanal()`: texto de entrega desde `textos.plan_entrega`.
  - `_contrato_datos(datos)`: ejemplo JSON desde `textos.contrato_ejemplo`.
  - `tex_guia()`: `textos.como_funciona`, `titulo_entregas`, `titulo_estructura`,
    `aviso_entrega`, `titulo_politicas`, `nota_correccion`, `reglas_codigo`; laboratorio
    condicional a imágenes; contrato de datos desactivable con
    `textos.contrato_datos: false`; **apéndices** al final (título + texto + tabla).
  - `tex_practica()`: `meta.duracion_sesion`, entrega con `_carpeta_entrega`,
    `textos.aviso_practica`, y secciones nuevas `fundamento_tex`, `figura_tex` +
    `figura_caption`, `materiales`, `tabla_datos`, `analisis` — ninguna se emite si no
    está en el descriptor.
  - `tex_control()`: `control.caracter`, plataforma desde `entregas`.
  - `tex_evaluacion_final()`: `final.semana` (default `meta.semanas`) + carpeta real,
    `final.caracter`, `final.condiciones`, `final.entregables`,
    `final.criterios_aprobacion`.
  - `yaml_rubrica()`: criterios desde `evaluacion.rubrica` (si no, los 5 históricos);
    descripciones serializadas con `json.dumps` para que dos puntos/comillas no rompan
    el YAML.
  - `md_laboratorio()`: degrada a texto cuando no hay imágenes; `md_readme()`: títulos
    de entrega parametrizados.
- **Regresión verificada**: `cursos/CYBERSEGURIDAD/curso.yaml` sigue validando
  (`validar() == []`), genera 20 artefactos sin errores y `silabo`/`guia` **compilan**
  con 0 líneas `!` en `.tmp/latex_build/curso_CYBERSEGURIDAD/*.log`. Se generó sobre
  `/tmp/opencode/curso_cyber` para no tocar el curso real.
- **Test nuevo**: `execution/test_generar_material_curso.py` → **33 aserciones, 0 fallos**.
  Cubre validación (rúbrica que no suma, clave no ASCII, tabla desalineada, apéndice
  vacío), emisión de secciones nuevas, no-invención cuando faltan, **no contaminación
  de dominio** (física sin "contenedor del laboratorio" ni "autorización escrita"),
  apéndices, laboratorio sin imágenes, plantilla de carpeta, griegas, determinismo.
  No compila LaTeX (eso lo cubre el flujo).
- **Incidente de cuota (17:35 UTC)**: opencode emitió `Free usage exceeded, subscribe
  to Go [retrying in 7h 23m attempt #1]`. Diagnóstico con el flujo de failover:
  - `python3 flujo_motor_fallback.py estado` → `modelo_actual: null` (la config
    `~/.config/opencode/opencode.jsonc` no fija modelo).
  - El motor en curso **ya es el fallback** (`openrouter/qwen/qwen3.8-max-0902`), así que
    la cadena de failover estaba agotada en su último eslabón.
  - Sonda del otro pool: `python3 execution/verificar_cuota_motor.py
    --modelo opencode/big-pickle --timeout 75` → `{"estado": "indeterminado",
    "motivo": "timeout"}`. **No es evidencia de disponibilidad**; no se conmutó.
  - `flujo_motor_fallback.py check` no cabe en 120 s (2 confirmaciones × hasta 120 s).
  - No se ejecutó `switch` a propósito: conmuta y **reinicia opencode**, lo que cortaría
    la sesión en curso. Decisión del usuario, no del asistente.

## Incidente de ficheros borrados (no restaurar)
Detectado al hacer `git status` al cierre. En `cursos/LABORATORIO_II_FISICA/` solo queda
`docs/contenido.pdf` (untracked); nueve ficheros **trackeados en HEAD** están borrados
del árbol de trabajo sin commitear, y no existen en otro lugar del workspace ni en
`git stash`:

| Fichero (en HEAD) | Tamaño | Contenido |
| --- | --- | --- |
| `LAB_II_LATEX/PRACTICAS_LAB_II.tex` + `.pdf` | 48.505 B | redacción LaTeX de las prácticas |
| `PRACTICA_2/puente_wheatstone{,_corregido,_deepseek}.tex/.pdf` | — | práctica 2 ya desarrollada |
| `PRACTICA_2/ejemplo_puente_desequilibrado.tex` | — | ejemplo complementario |
| `PRACTS_ORIGINALES/PRACTICAS_1_2_3.pdf` | 13.702.270 B | escaneos originales |
| `PRACTS_ORIGINALES/PRACTICA_4.pdf` | — | escaneo original |

- Causa probable: el repo vive bajo `~/MEGA/` y la sincronización de MEGA puede borrar
  ficheros. El último commit que los tocó es `f5ee242 WIP: guardar cambios antes de pull`.
- **Decisión del usuario: dejarlos borrados** (ver Decisiones 8).
- Riesgo operativo a recordar: el borrado **no está commiteado**, así que siguen
  recuperables con `git restore cursos/LABORATORIO_II_FISICA/`. Un `git add -A` o
  `./update_repo.sh` / `./git-update.sh` commitearía el borrado y consolidaría la
  pérdida en el árbol (quedaría solo en historia). Si en una sesión futura se va a
  commitear, revisar antes `git status` de esa carpeta y decidir explícitamente.

## Actividades (segunda parte, retomada tras el reset de cuota)
- `directives/disenar_curso.yaml` actualizada a **v1.1** (aditivo; la v1.0 queda
  reproducida en los textos que no se tocaron): sección nueva `campos_opcionales`
  con 35 entradas (campo → default → efecto) y 7 edge cases nuevos (18 en total).
  Dos trampas de YAML encontradas al escribirla: (a) en un item de secuencia con
  mapa (`- icono: texto`), la línea de continuación debe ir MÁS indentada que la
  clave o PyYAML la lee como otra clave; (b) un escalar plano no puede EMPEZAR por
  backtick (`` ` `` es indicador reservado) ni contener `": "`, y un `": "` dentro
  de un item de lista no rompe el parseo sino que **convierte el string en
  diccionario** (9 casos así en el descriptor de física). Por eso
  `campos_opcionales` usa claves planas con `>-`.
- Escrito `cursos/LABORATORIO_II_FISICA/curso.yaml` (~1500 líneas): 10 semanas
  (1–8 = las ocho prácticas del índice; 9 = integradora RLC; 10 = evaluación final
  y portafolio), 3 fases, 4 grupos con 4 roles rotativos por fase, pesos 60/20/20
  sobre escala 10 con mínima 5, rúbrica de 7 criterios que suma 10, 2 controles de
  fase (4 × 2,5), evaluación final en semana 10 (3+3+2+2), laboratorio Docker
  opcional (`jupyter/scipy-notebook`, red `labfisica`, subred 172.29.0.0/24),
  5 apéndices, 7 referencias y 11 políticas. Cada práctica lleva `fundamento_tex`,
  materiales, pasos, `tabla_datos`, `analisis` y entregable; 9 de las 10 llevan
  figura en circuitikz. Los criterios de las 10 prácticas son un **ancla YAML**
  (`&criterios_practica` / `*criterios_practica`): una sola definición, imposible
  que diverjan entre documentos y respecto de `rubrica_practica.yaml`.
- **Dos fallos del generador descubiertos al usarlo de verdad, corregidos en el
  generador y no solo en el dato:**
  1. `resultados_aprendizaje` como lista de strings pasaba `validar()` y reventaba
     en `tex_silabo` con `TypeError: string indices must be integers` (hace
     `r["id"]`). Ahora se valida la forma `{id, texto}` y sale código 3.
  2. Un carácter Unicode en LaTeX **crudo** (celdas de tabla, `*_tex`) no lo
     traduce `_UNICODE` (eso solo aplica a los campos escapados) y revienta
     pdflatex. Nuevo `_unicode_crudo()` + `_ASCII_SEGURO`, enganchado en
     `_validar_tabla` y en el bucle de semanas; además caza el `%` sin escapar.
     Convierte un ciclo de compilación de ~3 min en un error instantáneo que
     sugiere la macro (`escribir $\Omega$`).
- Cuatro errores de LaTeX reales del descriptor, documentados en `.agent/latex.md`
  como entradas **18–21**: `%` sin escapar en una celda (comenta el `\\` y el
  síntoma sale dos filas más abajo como `Misplaced \noalign`), `\,` + `\%` en modo
  matemático con babel spanish (`! Incompatible glue units`, por mezclar glue `mu`
  con `pt`), `galvanometer` no existe como bipolo de circuitikz (usar `ammeter`),
  y Unicode literal en región cruda.
- **Curso generado y verificado**: 16 documentos LaTeX, **16 PDF**, 0 líneas `!` y
  0 `Overfull \hbox` en los 16 logs. Páginas: guía 8, sílabo 5, plan semanal 6,
  prácticas 01–09 → 5, práctica 10 → 4, controles y final → 2. Determinismo
  confirmado (sha256 idéntico de `silabo.tex` y `evaluacion_final.tex` en dos
  corridas). La rúbrica generada la carga `evaluar_examen.cargar_rubrica` sin
  quejas y sus pesos suman 10.0. Ningún `.tex` generado arrastra vocabulario de
  ciberseguridad. `docs/contenido.pdf` original intacto.
- `execution/test_generar_material_curso.py`: 33 → **40 aserciones, 0 fallos**
  (RA mal formado, Unicode en crudo, `%` sin escapar y su contrario escapado).
- `AGENTS.md`: añadido el test nuevo a la línea de **Tests**.
- **Auditoría de higiene** (`flujo_auditar_repo.py --json`): `salud.veredicto =
  con_avisos`, `exit_code 0`, 14/14 dimensiones medidas, **0 con fallo** (8 ok,
  6 aviso). Los avisos son preexistentes: `directivas` (9 referencias declaradas
  no implementadas en 8 directivas con `Status: planificado`; `disenar_curso.yaml`
  NO está entre ellas), `peso_git` (235 MB), `untracked` (102 ficheros),
  `estado_sesion` (43 estados sin log, no juzgables) y `disco` (85,3 %).
- **Aviso propio detectado y corregido**: `pdf_stale` señalaba
  `silabo.tex` (303 s) y `evaluacion_final.tex` (125 s) más nuevos que su PDF.
  Causa: la comprobación de determinismo se hizo con `--sin-compilar`, que
  reescribe el `.tex` sin recompilar. Idéntico contenido (mismo sha256), pero el
  auditor tiene razón en marcarlo. Corregido regenerando `--solo silabo,final`
  **con** compilación; ahora los 16 PDF son posteriores a su fuente y `pdf_stale`
  baja de 4 a 2 pares desfasados, los dos ajenos a esta sesión.
  Lección: una verificación de determinismo que reescribe entregables debe ir
  seguida de una compilación, o hacerse sobre una copia en `.tmp/`.
- `execution/generar_tareas_curso.py` importa de `generar_material_curso` y sigue
  importando y mostrando su CLI sin cambios (los símbolos que consume no se tocaron).

## Estado al cierre (pausa hasta mañana)
El curso está **generado, compilado y verificado en disco**; no se commiteó nada.
Cierre con higiene pasada: `estado_sesion.py check` → `ok` (45 comprobaciones,
0 acciones recomendadas, nada que purgar); `bitacoras.py check` → `ok`;
`flujo_auditar_repo.py` → `con_avisos` con 0 fallos; tests 40/40.

Para retomar no hace falta regenerar nada. Si se quiere reconfirmar el estado en
seco: `python3 execution/test_generar_material_curso.py` y
`grep -c '^! ' .tmp/latex_build/curso_laboratorio_ii_fisica/*.log` (todo a 0).
La entrada de trabajo es el **Pendiente 1** (sustituir los datos típicos del
apéndice 3 y los materiales por los reales del laboratorio) y la decisión de
commitear del **Pendiente 2**.

## Pendientes
1. **Revisión docente del contenido.** El apéndice 3 (datos técnicos de
   instrumentos) lleva valores típicos y la propia tabla lo dice; hay que
   sustituirlos por la ficha real del laboratorio. Idem el inventario de
   materiales de cada práctica (valores de R, C, L y modelos de instrumento) y los
   rangos de las tablas de datos, que hoy son plantillas con `$\ldots$`.
2. **Decidir si se commitea** (el usuario no lo pidió). Ojo con `git status` en
   `cursos/LABORATORIO_II_FISICA/`: siguen los 9 borrados trackeados sin commitear
   (ver Incidente) y un `git add -A` los consolidaría. Además entrarían ~4 MB de
   PDFs nuevos y las bitácoras que siguen untracked.
3. Mejora opcional detectada y **documentada pero no corregida**: con
   `laboratorio.imagenes` vacío, `docker-compose.yml` se escribe igual y queda con
   `services: {}`, que `docker compose up` rechaza. Está como edge case en la
   directiva; el curso de física declara una imagen y no lo sufre.
4. Mejora opcional: `_unicode_crudo` cubre celdas y `*_tex`, pero no las claves de
   `columnas` escritas con macros inexistentes (p. ej. un icono FontAwesome que no
   existe en `meta.icono` solo falla al compilar).
5. Ajeno a esta sesión, detectado por la auditoría: `pdf_stale` sigue marcando
   `docs/CYBERSEGURIDAD/disenar_curso_flujo.tex` (7 s más nuevo que su PDF) y
   `docs/AGENTE_IA/rea_evaluacion_incorporacion.tex` (~6,8 días). El primero es del
   diagrama de flujo de la sesión de hoy sobre el curso de ciberseguridad; se
   recompila con `execution/generar_diagrama_flujo.py` y su descriptor.
6. No se commiteó nada: el usuario no lo pidió.
