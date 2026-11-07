# Resultados de evaluaciones — Ciberseguridad Aplicada

Carpeta **local y privada**: contiene entregas corregidas, notas y nombres de
estudiantes. El repositorio GitHub es **público**, por eso `.gitignore` excluye todo
`cursos/*/evaluaciones/resultados/**` salvo este README. Las notas no se suben nunca
(misma convención que `cursos/LABORATORIO_II_FISICA/evaluaciones/resultados/`).

## Estructura

```
resultados/
|-- actas.csv                     # acumulado: una fila por entrega corregida
|-- semana_NN/
|   |-- grupo_1/
|   |   |-- <informe>.pdf         # entrega corregida (copia local)
|   |-- grupo_2/
|   |-- grupo_3/
|   `-- grupo_4/
```

El curso tiene **cuatro grupos** y **10 semanas**. La carpeta `semana_NN/grupo_N/`
se crea sola al registrar la primera entrega de esa semana; no hace falta prepararla.

## Cómo registrar una entrega

```bash
python3 flujo_registrar_resultado.py \
  --curso cursos/CYBERSEGURIDAD/curso.yaml \
  --semana 1 --grupo 2 --nota 7.5 \
  --documento /ruta/al/informe_corregido_grupo_2.pdf
```

- El **rol** de la fila se calcula de la rotación del descriptor (`grupos.asignacion_inicial`
  y `grupos.fase_con_roles`); no se teclea. En la fase 5 (semana 10) la fila sale
  `individual`.
- El **informe** se copia a `semana_NN/grupo_N/` conservando el nombre original.
  `--documento` es opcional: sin él la fila se anota igual.
- La **nota** la calcula `execution/evaluar_examen.py` (suma de parciales normalizada
  a 10, `.agent/python.md` entradas 22-23); aquí solo se registra, entre 0 y 10.
  Si la escala no era fiable, registra con `--no-fiable` y revisa a mano antes del
  cierre.
- Una segunda entrega de la misma semana y grupo se **rechaza** (código 4) para que
  el acta no acumule filas contradictorias. Para corregir una nota:
  `--reemplazar`.
- `--observaciones "..."` deja una nota breve en el acta (p. ej. «entrega tardía»).

## actas.csv

Cabecera fija: `fecha,semana,grupo,rol,documento,nota_sobre_10,nota_fiable,observaciones`.

Una fila por entrega corregida. Es la fuente del cierre: los pesos del sílabo son
prácticas 35 %, controles de fase 15 %, informes técnicos 15 %, evaluación final 25 %
y ética/autorizaciones 10 %; la nota mínima de aprobación es 5 sobre 10.

El CSV lo escribe el registro de forma atómica (temporal + rename): una interrupción
no deja un acta a medias. No editarlo a mano mientras haya una corrida en curso.
