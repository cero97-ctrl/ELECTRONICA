# Resultados de evaluaciones — Laboratorio II de Física

Carpeta **local y privada**: contiene notas, informes de corrección y nombres de
estudiantes. El repositorio GitHub es PÚBLICO, por eso `.gitignore` excluye todo
`cursos/*/evaluaciones/resultados/**` salvo este README (misma convención que
`docs/REFERENCIA/`). Las notas no se suben nunca.

## Estructura

```
resultados/
|-- actas.csv                     # registro acumulado: una fila por entrega corregida
|-- semana_NN/
|   |-- grupo_1/
|   |   |-- <entrega>.pdf         # entrega recibida (copia local)
|   |   |-- informe_<entrega>.pdf # informe de corrección generado
|   |   `-- evaluacion_<entrega>.json  # JSON del modelo + nota calculada
|   |-- grupo_2/
|   `-- grupo_3/
```

El curso tiene **3 grupos**; las carpetas de grupo se crean por semana
(`semana_01/` … `semana_10/`, controles en `controles/fase_1/` etc. si aplica).

## Cómo evaluar una entrega y guardarla aquí

```bash
# 1. Evaluar (informe .tex/.pdf directo a la carpeta del grupo/semana):
python3 flujo_evaluar_examen.py \
  --pdf /ruta/a/entrega_grupo_1.pdf \
  --tipo laboratorio \
  --rubrica cursos/LABORATORIO_II_FISICA/evaluaciones/rubrica_practica.yaml \
  --output-dir cursos/LABORATORIO_II_FISICA/evaluaciones/resultados/semana_01/grupo_1

# 2. El JSON de evaluación queda en .tmp/evaluacion_<nombre>.pdf.json
#    (regenerable); copiarlo a la carpeta del grupo para el registro durable:
cp .tmp/evaluacion_entrega_grupo_1.pdf.json \
   cursos/LABORATORIO_II_FISICA/evaluaciones/resultados/semana_01/grupo_1/

# 3. Añadir la fila al acta:
#    fecha,semana,grupo,documento,nota_sobre_10,nota_fiable,informe
```

La nota la calcula el programa (suma de parciales normalizada a la escala de la
rúbrica), no el modelo: ver `.agent/python.md` entradas 22-23. Si
`nota_fiable=false` (escala indescifrable), revisar a mano antes de actar.

## actas.csv

Cabecera fija: `fecha,semana,grupo,documento,nota_sobre_10,nota_fiable,informe`.
Una fila por entrega corregida; es el acumulado del semestre y la fuente para el
cierre de notas (pesos del sílabo: prácticas 60 %, controles 20 %, final 20 %).
