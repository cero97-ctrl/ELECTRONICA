# Verdad etiquetada — deteccion de errores en entregas reales

**Fecha:** 2026-10-03 · **Estado:** APARCADO — esperando muestra mayor (decisión del profesor)

> ## 📌 Por qué está aparcado, y qué lo desbloquea
> Rellenar esto **no** es la vía para responder a la pregunta. Con **n = 3** el resultado es
> un caso anecdotal que no se va a volver a plantear, por muy bien documentado que esté. El
> profesor decidió (2026-10-03) no etiquetar todavía.
>
> **Condición de desbloqueo:** haber recolectado una muestra mayor de entregas reales de
> Electrónica / Dispositivos Electrónicos. Esto solo es posible una vez **iniciadas las
> actividades en la universidad**, cuando se vuelve a corregir en papel y el modelo tiene
> con qué contrastar.
>
> Con 3 alumnos rellenando, el estudio no se cierra: se archiva como antecedente.

> ## ⛔ No abras `resultados_modelo.md` hasta cerrar este archivo
> Está en la misma carpeta y contiene todo lo que el modelo dijo de cada entrega. Si lo
> lees antes de etiquetar, tiendes a confirmar lo que ya dijo y el estudio deja de medir
> nada. El sesgo de confirmación no es un riesgo teórico: es lo más probable que pase si
> las dos cosas están en la misma pantalla.

---

## Qué se está midiendo, y qué falta

En una fixture sintética (7 errores puestos a propósito) el modelo no señaló la afirmación
que el estudiante sostenía con seguridad y que era falsa. La pregunta era si eso era un
**patrón** o un **caso suelto**.

Aquí no hay respuestas inventadas: hay 3 entregas reales de alumnos de Electrónica y
Dispositivos Electrónicos, rescatadas de la papelera del sistema. El modelo ya las evaluó.
Lo que **no** existe todavía es la contraparte que da sentido a esa evaluación: la lectura
del profesor sobre qué error cometió cada alumno.

**Alcance de hoy: n = 3.** Con tres alumnos esto es un caso anecdotal. La pregunta original
—patrón o caso suelto— **queda sin responder**, y esa es la conclusión honesta de esta
fase: no se ha medido nada generalizable. Lo que sí queda es el precedente midiendo con
tres alumnos reales, que es lo que valía la pena descartar.

---

## Dónde están las entregas

> ⚠️ **Verificar que siguen ahí antes de este bloque.** Este material se rescató de la
> papelera del sistema y vive fuera del repo. Si no están, comprobar
> `~/.local/share/Trash/files/`; si ya no aparecen ahí, se perdieron y habría que
> reconstruir el corpus desde las entregas nuevas.

```
/home/cero/MEGA/ELECTRONICA_ENTREGAS/
├── entregas_examen/         ← 5 fichas: 3 entran al estudio, 2 quedan fuera (ver abajo)
├── informes_laboratorio/    ← 4 informes de Electrónica (fuera del estudio, otra vía)
└── enunciados_solucionarios/ ← 4 PDF
```

Ábrelas de ahí: son los originales a 300 dpi. No uses los PNG de
`.tmp/entregas_vista/`, que son un render a 110 dpi.

Llevan nombre y C.I. de alumnos reales, por eso viven fuera del repo. Aquí se citan por
seudónimo; los nombres quedan solo en el nombre de los ficheros.

---

## Cómo se rellenará (guía para el futuro, no hay nada que rellenar hoy)

Estas reglas no se aplicaron a nada: son el método que habrá que seguir cuando exista
muestra suficiente. Se dejan escritas ahora porque en meses nadie las recordará, y el sesgo
que previenen es precisamente el que se cuela sin que se note.

1. **Escribir el enunciado de cada ítem tal como lo lee el profesor**, antes de mirar
   ninguna salida del modelo. Si al final no coincide con el enunciado que entendió el
   modelo, eso es un hallazgo propio: significa que la evaluación atribuye un ítem al otro.
2. **Error real del alumno**: qué hizo mal, no solo qué falló. "No conectó la masa" es dato;
   "mal" no lo es.
3. **Marcar los ítems en blanco.** Distingue dos cosas que el estudio confunde con facilidad:
   *el modelo no vio un error* y *no había ningún error que ver*. Un ítem en blanco que
   el modelo no menciona no es una detección fallida.
4. **Si el alumno acertó**, escribir "correcto". El objetivo no es contar errores del
   alumno: es si el modelo los ve.
5. Poner los errores aunque parezcan obvios. Los obvios son los que más se pierden cuando
   alguien resume.

Los ítems que queden sin rellenar son hallazgos en sí mismos: un hueco en la verdad del
profesor es un límite del estudio, no un dato vacío.

---

## Por qué no hay tablas de ítems aquí

La versión anterior traía una tabla por alumno con los ítems ya identificados. Se quitaron a
propósito:

- Rellenarlas ahora, dentro de meses, no es posible: nadie recuerde qué ítems eran, ni los
  números del papel.
- Y hacerlo con la lista delante significa **estar leyendo las descripciones de los ítems
  en `resultados_modelo.md`**, porque los dos archivos están en la misma carpeta y el
  enunciado de cada ítem solo existe ahí. Es el sesgo que este diseño debía evitar,
  reintroducido por la puerta de atrás.

Cuando llegue el momento, la verdad del profesor se escribe desde cero, sobre las entregas
físicas, antes de abrir nada generado por el modelo.

---

## Fuera del estudio (y por qué)

Decisiones ya tomadas. No hacen falta cambios.

| Fichero | Motivo |
|---|---|
| `FIS_solo_respuestas.pdf` | No trae enunciado (empieza en el ítem 7 de un cuestionario más largo) y es de Lab II de **Física**, no de Electrónica. Sirve como caso "solo respuestas", no como examen evaluable. |
| `FIS_lab_fisica_2pag.pdf` (2 págs) | Es de Lab II de Física; el alumno A del estudio es el otro fichero, el de 4 págs. |
| `respuestas_1/2/3.pdf` | **No son entregas de alumno**: son informes que el propio sistema generó ("Evaluación de Respuestas — X / Evaluado por Prof. César Rodríguez"), de Seguridad Informática. Falso positivo descartado. |
| `evaluacion_examen_*.json` (papelera) | Salidas del modelo con la estructura antigua: 0 ítems, sin nota. No son verdad ni referencia. |

---

## Nota sobre el material

Los cuatro informes de laboratorio de Electrónica que se rescataron
(`/home/cero/MEGA/ELECTRONICA_ENTREGAS/informes_laboratorio/`) **no** entran en este
estudio: son de otra vía (`--tipo laboratorio`, con rúbrica) y mezclar aquí las dos
alteraría la comparación. Quedan para una segunda vuelta.