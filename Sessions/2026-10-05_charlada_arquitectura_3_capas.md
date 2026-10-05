# 2026-10-05 — charlada_arquitectura_3_capas

## Tema
Material de conferencia (30 min) sobre arquitectura determinista de 3 capas, para
docentes de ingeniería, con eje en el patrón transferible y no en el catálogo del repo.

## Contexto
El usuario pidió preparar una charla y material en LaTeX. Faltava la pieza que siempre
falta: **el material se construyó con el mismo patrón que la charla defiende**, lo que
la convierte en una demostración de su propia tesis en lugar de una descripción de ella.
Sesión de continuidad: `2026-10-02_nota_determinista_escala_rubrica.md` (los tres fallos
que se explican son los registrados allí).

## Decisiones (usuario)
1. **Audiencia:** docentes de ingeniería → nivel conceptual, pero con código y logs reales.
2. **Eje:** el patrón transferible. No un recorrido por el catálogo del repositorio.
3. **Entregable:** diapositivas **y** LaTeX. No solo uno.
4. **Duración:** 30 minutos.
5. **Sin demo en vivo:** «solo material».
6. **Sin plantilla institucional.**
7. **Alcance del estudio:** los cuatro modos (mapa del repo, recorrido de flujo, cuatro
   fallos, ensayo del guion).
8. **ASMUMIDO, no confirmado:** Beamer 16:9 para el deck y handout A4 infográfico. La
   respuesta a la pregunta «deck o handout» fue ambigua y se resolvió así; si el
   profesor quiere otra cosa, solo cambia `--salida-dir` y el preámbulo.
9. **ASMUMIDO:** autor `ELECTRONICA` y fecha 2026-10-05, porque no se facilitó el nombre real.

## Actividades

### Las tres capas, construidas para la charla
- **Capa 1** `directives/charlada_ia_3_capas.yaml` (SOP).
- **Capa 2** `flujo_charlada.py` (orquestador; 4 pasos, no compila ni mide).
- **Capa 3** `execution/generar_charlada_latex.py` (mide el disco, redacta, compila, pre-vuela).
- `execution/estilo_infografia.py`: paleta extraída a `PALETA` + `definir_colores()`, de
  modo que el deck y el handout compartan una sola fuente de color. Invariante semántico
  comprobado (17 nombres/hex idénticos) y regresión `diseno_cluster.tex` limpia.

### Cifras medidas (no estimadas, no contadas con `grep`)
- 51 directivas · 62 scripts de ejecución · 23 flujos · 7 MCP · 66 sesiones.
- **10 fronteras LLM** sobre 62 scripts → **84 % determinista**. Los tres excluidos
  (cliente, enrutador y el propio detector) están nombrados en el material para que el
  criterio sea auditable.
- **585 aserciones** en 6 ficheros de test, confirmado **reejecutando** (`--verificar-cifras`).

### Verificación (por qué el log y no el PDF)
`nonstopmode` produce PDF aunque el documento esté roto: `success=True` y «existe el PDF»
no certifican nada. Todo se juzga parseando `^! ` del `.log`.
- Resultado final: **deck 16 páginas / 16 frames, 0 errores, 0 overfull**;
  handout 4 páginas, 0 errores, 0 overfull; diagrama ISO 3 páginas, 0 solapes.
- `flujo_auditar_repo.py`: **con_avisos, exit 0, 0 dimensiones con fallo**. `capas`
  reconoce el flujo nuevo (21/21 delegan, 0 sin capa 3).

### Fallos encontrados y corregidos (todos por el camino)
1. `\item \\ldots` — doble barra: salto de línea inválido (234 → 102 errores).
2. `\texorpdfstring{X}` con **un** argumento: Beamer exige dos, se comía el título del frame.
3. `{{...}}` y `}}` de sobra por f-strings: una llave sin cerrar en el deck.
4. **La herramienta de verificación mintió**: el checker de llaves hacía `split("%")` y
   partía la línea en el `\%` de «84 %», reportando un falso desequilibrio. El error era
   del checker, no del LaTeX. Mismo género que `success=True`; se corrigió con `re.split(r"(?<!\\)%")`.
5. `\vspace{2pt}` dentro de un f-string: `{2pt}` se lee como campo de sustitución y rompe el
   archivo. Sustituido por `\smallskip`, que no tiene argumentos.
6. **Las llaves del JSON desaparecían**: en modo texto `{`/`}` son agrupamiento de TeX, así que
   `response_format={"type": "json_object"}` se imprimía sin llaves — mutilando el ejemplo
   central del fallo 3. Resuelto con constantes `LB`/`RB`.
7. **`%` dentro de `lstlisting`** es carácter de comentario y truncaba la línea (`84\ %`).
8. `\pause` duplicaba cada diapositiva en dos páginas del PDF (16 frames → 22 páginas), sin
   ningún error ni aviso. Para un PDF que se presenta con clic, cada duplicado es un clic de
   más que el profesor tiene que acertar. Eliminado y **añadido el invariante
   `páginas == frames`** para que no vuelva.
9. El `--subtitulo` por defecto afirmaba «80 %» mientras la medición daba 84 %. Ahora se deriva
   de la medición: un literal en un default se contradice solo en cuanto el repo cambia.
10. **Corrupción CJK propia** (dos ideogramas inyectados donde iba «igual») al escribir el
    descriptor del diagrama. Detectada y corregida antes de compilar. La bitácora **no los
    reproduce**: `execution/verificar_texto.py` los marca como `cjk_unificado`, y con razón —
    un fichero trackeado con CJK literal está corrupto aunque el texto sea una cita.
11. `de\textbf{ROL}` pegado sin espacio; igual que «elqué/elcuándo/elcómo» en los títulos.
12. El número de páginas no se leía porque **el log de TeX parte las líneas a 79 caracteres**:
    «(16 pages…)» cae en la línea de continuación. Requiere `re.S`.

### Validación añadida (para que el error se vea antes de pagar la compilación)
- `validar_latex_guion`: `_`/`^` sin escapar fuera de math.
- `validar_llaves`: balance y profundidad negativa.
- `validar_una_pagina_por_diapositiva`: páginas == frames (post-compilación).

### Corregido: el entregable se publicaba sin su fuente (2026-10-05, commit posterior a `da55a68`)
El PDF del deck y el del handout se versionaban **sin su `.tex`**, así que no eran
regenerables. Los `.tex` no se habían perdido: estaban en `.tmp/charlada/<job>/`, junto al
PDF de origen, con el mismo nombre de base.

Causa real, y no era la que se sospechaba: **no era la capa 3**. `generar_charlada_latex.py`
escribe el `.tex` y compila los dos a `.tmp/charlada/<job>/`, y su `--salida-dir` es
decorativo (crea el directorio y lo anota en el informe; nunca escribe ahí). La capa 3
hacia bien. El bug estaba en el **paso 4 de la capa 2**, `flujo_charlada.py`, que se llama
«Publicar los PDF en la carpeta de entrega» y copiaba solo `Path(info["pdf"])`: el `.tex`
era hermano del PDF y se quedaba en `.tmp/`, que es justo el directorio que `flujo_disco`
puede purgar.

El error conceptual es que el flujo trataba el `.tex` como intermedio. No lo es: un
intermedio se regenera desde otra cosa; un `.tex` es **la fuente** del entregable. Y el
repo ya tenía el criterio resuelto — `pdf_stale` contaba 178 pares `.tex/.pdf`, todos los
entregables LaTeX versionan su fuente —, así que la charlada era el único que se salía de
la convención.

Corregido en `flujo_charlada.py`: el paso 4 publica `.pdf` **y** `.tex`, y si falta cualquiera
de los dos aborta con código 3. Sin la guarda, un `.tmp/` purgado entre compilar y publicar
volvería a dejar PDF huérfano en silencio, que es el fallo original.

Verificado ejecutando la capa 2 completa: publica 4 archivos en vez de 2, con el log de
compilación limpio y las cifras cuadrando contra el disco (628 MB de RAM disponible; la
compilación de 17 diapositivas entra justa).

Dos cosas que solo aparecieron al verificar y que merecen quedar escritas:

- **El `.tex` recuperaba pareja pero el par quedaba desincronizado.** Copiar el fuente con
  `cp` le mueve el mtime, de modo que el `.tex` pasa a ser más nuevo que su PDF y
  `pdf_stale` lo marca. Se resolvió **regenerando** (un `python3 flujo_charlada.py`), no
  retocando el mtime: retocar la marca de tiempo para silenciar una auditoría es fabricar
  la conformidad.
- **Regenerar cambió una línea: «66 sesiones» → «68 sesiones».** Es el comportamiento
  correcto y la demostración de la tesis de la propia charla: las cifras se miden en vivo
  (`medir_cifras()`), así que derivan cuando el repo crece. El deck `.tex` salió
  **byte-idéntico** al recuperado; el único diff en todo el material es ese contador.

Efecto colateral favorable: `pdf_stale` pasó de 178 a **180 pares**, porque antes los dos
PDF huérfanos le eran estructuralmente invisibles (recorre los `.tex`, así que un PDF sin
fuente nunca se visita). La dimensión que debía detectarlo no podía, por construcción.

## Cerrado: el punto ciego de `pdf_stale` (2026-10-05)

El pendiente de más abajo está **cerrado**: `pdf_stale` ahora recorre también los `.pdf`, no
solo los `.tex`. Lo que se zucchinió al arreglarlo:

- **El recorrido tenía dos sentidos y solo tenía uno.** El primero lo conduce el `.tex` y
  detecta deriva *dentro* de un par. El segundo lo conduce el `.pdf`: pregunta «de quién es
  este PDF y no veo a su fuente». Sin el segundo, un PDF sin fuente no era un dato
  faltante: era un fichero que la dimensión **nunca visitaba**, y el `ok` que reportaba
  («180 pares al día») era una afirmación sobre 180 pares, no sobre el repo. Un verde sobre
  una medición parcial.
- **Detectar «PDF sin .tex» a pelo daría 34 candidatos**, y 8 son libros y escaneos de
  terceros (`cursos/TESIS/.../PROYECTO-DIALISIS-PERITONIAL.pdf`, etc.). Una dimensión que
  llora lobo ocho veces enseña a ignorarla, que es peor que no tenerla. El discriminador son
  los metadatos: se declara LaTeX solo si `/Producer` o `/Creator` dice `pdfTeX`, `LuaTeX` o
  `XeTeX`. De 34 quedan **3**, y los tres son de este repo.
- **`None` no es `False`.** Si los metadatos no se pueden leer, el resultado es «no saber»,
  no «no es LaTeX». Sin `pypdf` (no está en `requirements.txt`, que solo declara `psutil` y
  `PyYAML`; el resto vive en el entorno conda) *todos* los candidatos caen en
  `pdf_sin_metadatos` y la dimensión **avisa**: degrada a «revisar a mano» en vez de ponerse
  verde. Se prefirió ese ruido a un `ok` mentiroso.
- **La función no diagnostica, mide y enseña.** La primera versión decía «no regenerables» y
  era **falso en los 3 casos**: los tres tienen su fuente, pero con otro nombre. Así que
  ahora cada huérfano lleva `tex_en_el_directorio` y la acción explica las dos ramas —con
  un `.tex` al lado lo probable es un PDF duplicado y sobra el PDF; sin ninguno, el
  entregable no se puede reproducir. Elegir entre las dos sin mirar sería inventar el fallo.
- **Gravedad `aviso`, no `fallo`.** Son 3 entregables preexistentes que el repo lleva
  arrastrando; subirlos a `fallo` dejaría el veredicto global en `con_fallos` y enseñaría
  que la auditoría naranja es el estado normal.
- Cobertura: **12 aserciones nuevas** (134 → **146**, todas en verde). Los tests fabrican
  PDF **reales** con `pypdf` (`/Producer: pdfTeX-1.40.25` y `/Producer: Adobe Acrobat 6.0`)
  porque un `b"%PDF-1.4"` a pelo no tiene Info y devolvería `None`: se habría probado el
  caso «no se», que no es el que se quería probar.

## Pendientes
- **Tres PDF entregables sin fuente de mismo nombre**, **preexistentes y no introducidos por
  esta sesión**; los acaba de sacar la dimensión ya corregida (no los produjo la charlada,
  que iba con su fuente):
  - `cursos/TESIS/.../IoT con Arduino y ESP32/IoT-con-Aeduino-y-ESP32.pdf` — **duplicado por
    errata**: existe `IoT-con-Arduino-y-ESP32.pdf` *y* su `.tex`. Sobra el que dice «Aeduino».
  - `docs/MANUAL/manual-2.pdf` — **copia vieja**: `manual.tex` y `manual.pdf` están al lado.
  - `cursos/DISP_ELECTRONICOS/.../PRACTICA-2/practica-2.pdf` — el `.tex` del directorio es
    de **otro** documento (`practica_11-1.tex`), así que este PDF sí es huérfano de verdad:
    o se recupera el fuente o el PDF se va. Además ese directorio tiene artefactos de
    compilación versionados (`.aux`, `.log`, `.fls`, `.fdb_latexmk`, `.synctex.gz`, `.toc`).
  Borrar un PDF del repo es decisión del profesor y además pasa por la barrera de disco;
  aquí solo queda medido y nombrado.
- **Autor real y título definitivo**: siguen los valores por defecto.
- **Confirmar Beamer** como formato (fue un supuesto, ver Decisión 8).
- **Ensayo cronometrado de 30 minutos**: no hecho. El generador avisa si 17 diapositivas
  exceden el presupuesto, pero el ensayo con cronómetro es del profesor.
- **Cuarta lección**: el plan original la planteaba como el fallo `.style` vs entorno de
  `tcolorbox` (`.agent/latex.md` entrada 17), pero el deck incluye tres fallos + álgebra de
  veredictos. Decidir si la cuarta es el `.style` o la álgebra.
- **No tocar** `TAREA_POR_TIPO["examen"]` en `execution/evaluar_rubrica.py` hasta que el
  profesor complete la ronda de corrección en papel (acordado el 2026-10-02).
- Avisos de higiene **preexistentes, no introducidos por esta sesión**: disco 85.6 %
  (33.5 GB libres, 175.6 MB recuperables), 252 MB trackeados con 8 ficheros ≥5 MB,
  9 estados de sesión sin log append-only, 11 capacidades declaradas sin implementar.