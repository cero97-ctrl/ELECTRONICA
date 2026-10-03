# 2026-10-03 — deteccion_errores_alumnos_reales

## Tema
deteccion_errores_alumnos_reales

## Contexto
El usuario quería medir si el modelo detecta los errores conceptuales de exámenes REALES,
porque en la fixture sintética (`execution/generar_fixture_examen.py`, 7 errores
deliberados) el modelo detectó 5/7 y pasó por alto el diodo invertido que el estudiante
afirmaba correcto. Pregunta abierta: ¿es el fallo del prompt un patrón o un caso suelto?
Sin PDFs de alumnos no había forma de responderla, y el repo no tenía ninguno
(`examenes/*/examen_estudiantes/` vacío).

**El giro de la sesión:** el usuario dijo que no lograba conseguir exámenes viejos. Al
buscar fuera del repo aparecieron en **la papelera del sistema**
(`~/.local/share/Trash/files/`): 4 entregas escaneadas de alumnos de Electrónica y
Dispositivos Electrónicos, borradas entre 2025-11 y 2026-02 junto con las carpetas
originales. El riesgo era urgente: `~/.local/share/Trash/files` está en
`execution/catalogo_disco.py:108-113` con `tier="seguro"` y `min_edad_dias=1`, así que
cualquier `flujo_disco.py` las destruía (llevan 8-10 meses ahí).

## Decisiones (usuario)
1. **Rescatar fuera del repo**: `/home/cero/MEGA/ELECTRONICA_ENTREGAS/`. Los PDFs llevan
   nombre y C.I. de alumnos reales; el `.gitignore` patea `examen*` por casualidad, no por
   diseño, y subir datos de terceros a GitHub no es opción.
2. **La verdad la etiqueta el profesor a ojo**, no derivarla del solucionario. Sin
   etiquetas no hay tasa de detección, solo la autoinforme del modelo sobre sí mismo.
3. **Estudio de caso, no métrica**: con 4 alumnos no sale un porcentaje defendible. Se
   documenta qué vio y qué no vio el modelo en cada caso.
4. **No tocar `catalogo_disco.py`.** El usuario eligió rescatar, no sacar la papelera del
   catálogo de purga (que habría exigido `test_barrera_disco.py`).
5. **El prompt de `--tipo examen` NO se toca** hasta tener el etiquetado. Ajustar
   comportamiento a ciegas es exactamente el fallo que este trabajo evita.

## Actividades

### Rescate (Fase 0) — 14 MB, 13 ficheros
- `entregas_examen/`: `FIS_lab_fisica_2pag.pdf` (2p), `A_examen_electronica_4pag.pdf` (4p),
  `FIS_solo_respuestas.pdf` (1p), `C_examen_electronica.pdf` (3p), `D_examen_dispositivos.pdf` (2p)
- `informes_laboratorio/`: 4 informes con capa de texto
- `enunciados_solucionarios/`: `Examen_Semana_8.pdf` + `sol_Examen_Semana_8.pdf`,
  `examen_razonamiento_unidad_IV.pdf`, `sol_examen_Electronica.pdf`

### Falso positivo descartado
`respuestas_1.pdf`, `respuestas_2.pdf`, `respuestas_3.pdf` **no son
entregas de alumno**: son informes que el propio sistema generó ("Evaluación de Respuestas
— X / Evaluado por Prof. César Rodríguez"), de Seguridad Informática. Los
`evaluacion_examen_*.json` de la papelera vienen de la estructura antigua (0 ítems, sin
nota): no son verdad.

### Nuevo flujo de 3 capas: inspección visual de entregas escaneadas
Por qué existía: `evaluar_examen.py` toma **un solo PDF** y no tiene campo para el
enunciado aparte (`directives/evaluar_examen_estudiante.yaml:8-12`). Un escaneo no tiene
capa de texto, así que "no trae enunciado" **no se ve leyendo el PDF**: hay que mirar la
imagen. `tesseract` no está instalado y no hace falta: el pipeline ya renderiza con
PyMuPDF y manda imágenes.

- `execution/inspeccionar_entrega.py` — inventario visual, NO evalúa.
- `directives/inspeccionar_entrega.yaml` — 7 edge cases.
- `execution/test_inspeccionar_entrega.py` — 41 aserciones, todas OK.
- `AGENTS.md` — comando y test en la tabla.

### Dos bugs reales encontrados y corregidos
1. **`INSTRUCCION` nunca se enviaba.** El script construía el mensaje de usuario con
   `construir_prompt()` y se olvidaba de adjuntar la instrucción; el modelo recibía solo
   "devuelve SOLO el JSON" y devolvió `{"text": "<todo el documento transcrito>"}` sin
   ninguna clave pedida. Fix: instrucción en `role: "system"`, imágenes en `user`, el
   patrón que ya usa `evaluar_examen.py`.
2. **`incluye_enunciado` era la única clave no obligatoria en `validar()`.** Tres tests
   nuevos fallaron a la primera: un modelo que omitiera la clave pasaba por inspección
   válida y el orquestador leía `None` creyendo que era «el modelo no sabe». Es la única
   celda que decide si el flujo es viable sobre ese documento. Ahora su ausencia es
   error; el valor `null` explícito sí es «no sé» y sí se acepta.

Documentado en `.agent/python.md` entrada 24.

### Inventario (Fase 1) — el riesgo de ensamblado desapareció
| Fichero | Págs | Enunciado | Asignatura | Tema |
|---|---|---|---|---|
| C_examen_electronica | 3 | sí | Electrónica | diodos y rectificadores |
| D_examen_dispositivos | 2 | sí | Dispositivos Electrónicos | diodos y rectificadores |
| A_examen_electronica_4pag | 4 | sí | Electrónica | circuitos, Thévenin, mallas |
| FIS_lab_fisica_2pag | 2 | sí | Lab II Física | corriente/tensión |
| FIS_solo_respuestas | 1 | **no** (empieza en ítem 7) | Lab II Física | corriente/tensión |

Las 3 de Electrónica **traen enunciado**, así que no hizo falta el script de ensamblado que
el plan contemplaba como contingencia. `FIS_solo_respuestas` es el caso "solo respuestas" y queda
como tal: no es evaluable sin las preguntas 1-6.

### Evaluación (Fase 3) — 3 alumnos, opus por decisión del enrutador
`execution/enrutador.py --task examen --vision` → `tier: opus`,
`anthropic/claude-opus-5`, en los dos casos (con y sin `--critico`), porque `examen` es de
razonamiento crítico. Saldo previo $20.89. Tokens: C 21.570 · D 16.604 · A 26.294.

| Alumno | Nota | Nivel | Ítems |
|---|---|---|---|
| C | 4.3/10 | Deficiente | 4 × 2.5 = 10 |
| D | 5.6/10 | Suficiente | 5 × 2 = 10 |
| A | 8.8/10 | Bueno | 5 × 2 = 10 |

Las tres escalas ya eran 10, así que el programa **no normalizó** (correcto).

### Hallazgo central (Fase 4, parcial)
De los **19 enunciados de error** de los tres informes, **ninguno** formula la afirmación
del alumno como falsa. Todos describen el error en positivo: "creer que…", "confusión
en…", "atribuir al modelo…". El modelo **sí detecta** los errores conceptuales y los
localiza con precisión (en Ailis detectó el error de signo `3V_b = V_a` donde debía ser
`V_a = -V_b`), pero **nunca los formula como refutación**. El prompt no lo pide.

**Pero esto NO es evidencia de patrón todavía**: n = 3, y ninguno de los tres presenta el
caso del diodo invertido. En C, el modelo sí detectó un error de conexión del rectificador
("el capacitor conectado en serie y la resistencia antes del diodo; no se cierra el
lazo"), que es el caso más parecido al de la fixture.

### Entregable para desbloquear — partido en dos archivos
El primer intento metió en un solo archivo las tablas en blanco **y** los resultados del
modelo, con una advertencia de no mirar. Era una contradicción: el sesgo de confirmación no
es un riesgo que se corrige con una nota al principio si los datos están tres líneas más
abajo. Ahora hay dos archivos:

- **`verdad_etiquetada.md`** — para el profesor, sin NINGÚN dato del modelo. Solo
  contexto, dónde están los PDFs (nombres reales en el fichero, seudónimo en el texto) y
  tablas vacías. Verificado por script: sin notas, sin niveles, sin puntajes, sin conteos de
  errores, sin citas textuales, sin tokens.
- **`resultados_modelo.md`** — notas, errores ítem a ítem, el hallazgo de las 0/19
  refutaciones y sus tres límites. No leer antes de cerrar el anterior.

Mejora de diseño que salió al partirlo: **el enunciado de cada ítem lo transcribe el
profesor**, no el modelo. La versión anterior traía los títulos que el modelo inventó
("Superposición: tensión total en el nodo A"), lo que filtraba su interpretación del
documento y además invalidaba la columna "¿el modelo lo vio?" porque el PROFESOR ya estaba
mirando la lectura del modelo antes de decidir. Con el enunciado en blanco, si al final no
coincide con el que entendió el modelo, es un hallazgo adicional.

## Pendientes

### ⭐ Tarea importante a futuro: repetir el estudio con muestra mayor
**Decisión del profesor (2026-10-03):** NO etiquetar las 3 entregas actuales. Rellenar el
etiquetado a n = 3 no responde la pregunta original y produce un caso anecdotal que no se
va a volver a plantear. Se aparca hasta poder reunir más entregas reales.

**Condición de desbloqueo:** actividades en la universidad iniciadas y una ronda de
corrección en papel hecha, que es de donde sale el material con el que contrastar. El
rescate de hoy vino de la papelera del sistema; lo que falta es un flujo
periódico: **corregir en papel y pasar el mismo papel por el modelo**, para tener verdad y
salida sobre el mismo documento.

**Cómo se retoma, sin repetir lo que ya está hecho:**
1. Reunir muestra (cuántas entregas, de qué unidades — la cifra la fija el profesor).
2. Evaluar por lote con `flujo_evaluar_examen.py --tipo examen`, **inspeccionando cada PDF
   antes** con `inspeccionar_entrega.py`: una entrega sin enunciado no es evaluable y produce
   una corrección sin sentido que luego alguien tomó por dato.
3. Escribir la verdad del profesor sobre el papel, ítem a ítem, en un archivo que no contenga
   nada del modelo.
4. Solo entonces contrastar.

**Lo que NO hay que hacer:** abrir `resultados_modelo.md` antes de cerrar el etiquetado. Con
n = 3 el sesgo era un riesgo; con 30 entregas, reservarlo todo en un mismo archivo es
directamente invalidante.

**Activos que quedan para ese día:**
- `docs/AGENTE_IA/estudio_deteccion_errores/verdad_etiquetada.md` — aparcado, con el método
  escrito pero sin tablas de ítems (se quitaron: rellenarlas ahora ya no es posible y sus
  descripciones vivían en el archivo del modelo, que reintroducía el sesgo).
- `docs/AGENTE_IA/estudio_deteccion_errores/resultados_modelo.md` — salida histórica de las
  3 entregas de hoy. No se reutiliza: las nuevas se evalúan desde cero.
- `/home/cero/MEGA/ELECTRONICA_ENTREGAS/` — corpus de hoy, **fuera del repo**, con nombres
  seudónimos y el mapa real en `_MAPEO_PRIVADO.txt`. Respaldo: el profesor declara que su
  contenido se sube automáticamente a la nube.

### Decisión sobre el prompt: sigue en espera
`TAREA_POR_TIPO["examen"]` **no se toca**. Con 3 casos no hay evidencia de que el estilo
descriptivo cueste detecciones: en los tres, el modelo localizó bien lo que había. Sin
contraste con verdad etiquetada no se justifica tocar el prompt, y tocarlo "por si acaso" es
exactamente el sesgo que este trabajo existe para evitar.

### Otros pendientes
- **Sin commit**: `execution/inspeccionar_entrega.py` (nuevo),
  `execution/test_inspeccionar_entrega.py` (nuevo), `directives/inspeccionar_entrega.yaml`
  (nuevo), los 2 `.md` del estudio (nuevos), `.agent/python.md`, `AGENTS.md`, esta bitácora
  — más los cambios de la sesión anterior (ajustes 1-3 de la nota) y los de tier que ya
  venían en el working tree.
- **Límite del modelo que hay que tener presente**: el motor de opencode de esta sesión
  **no acepta imágenes ni PDF como entrada**. Todo el examen visual de PDFs tiene que
  hacerlo el LLM del script; el orquestador no puede "mirar" un informe generado. La
  revisión final de los informes PDF la tiene que hacer el usuario.
- `FIS_solo_respuestas.pdf` queda sin evaluar por falta de enunciado. Si el profesor tiene el
  cuestionario completo, se puede reintentar con el PDF ensamblado.
- Los 4 informes de laboratorio de `informes_laboratorio/` no se han tocado: son de otra
  vía (`--tipo laboratorio`) y quedan para una segunda vuelta.