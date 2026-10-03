# Resultados del modelo (NO LEER ANTES DE ETIQUETAR)

**Fecha:** 2026-10-03 · **Estado:** Outputs conservados — el estudio está APARCADO

> ## 📌 Por qué no hay nada que contrastar todavía
> El etiquetado del profesor está aparcado hasta reunir muestra mayor (decisión suya
> 2026-10-03). Con n = 3 no hay comparación posible que valga. Esta página queda como
> **resultado histórico**: lo que el modelo dijo de estas tres entregas, congelado.
>
> **Si estás leyendo esto buscando una comparación:** no la hay todavía. Es el trabajo del
> modelo contándose a sí mismo, y eso no mide nada. Cuando el profesor etiquete una muestra
> mayor, esta página no se reutiliza: las entregas nuevas se evalúan desde cero.

---

## Cómo se evaluó

Las 3 entregas pasaron por el flujo de producción, sin adaptaciones:

```
flujo_evaluar_examen.py --tipo examen --api-backend openrouter \
  --modelo anthropic/claude-opus-5
```

El modelo no lo eligió el orquestador: lo decidió `execution/enrutador.py`, que clasifica
`examen` como razonamiento crítico y lo escala a tier `opus` incluso sin `--critico`
(las dos consultas, con y sin, dieron lo mismo).

Las tres escalas de los exámenes ya sumaban 10, así que el programa **no normalizó** la
nota, que es lo correcto.

| Alumno | Fichero | Nota | Nivel | Ítems | Tokens |
|---|---|---|---|---|---|
| C | `C_examen_electronica.pdf` | **4.3/10** | Deficiente | 4 × 2.5 = 10 | 21.570 |
| D | `D_examen_dispositivos.pdf` | **5.6/10** | Suficiente | 5 × 2 = 10 | 16.604 |
| A | `A_examen_electronica_4pag.pdf` | **8.8/10** | Bueno | 5 × 2 = 10 | 26.294 |

Coste total de las tres evaluaciones: **~$0.20** sobre un saldo previo de $20.89.

Informes completos: `.tmp/e2e_alumnos/`. JSON crudos: `.tmp/evaluacion_<alumno>.json`.

---

## Lo que produjo el modelo, ítem a ítem

### Alumno A — 8.8/10, Bueno

| Ítem | Puntaje | Enunciado según el modelo |
|---|---|---|
| 1 | 2.0/2 | Superposición: tensión total en el nodo A |
| 2 | 2.0/2 | Equivalente de Thévenin visto desde R2 |
| 3 | 2.0/2 | Máxima transferencia de potencia |
| 4 | 1.0/2 | Supernodo con fuente dependiente |
| 5 | 1.8/2 | Sistema de ecuaciones de malla (CCVS) |

**Errores detectados:** 1 conceptual + 3 procedimentales.

Lo relevante: el error de signo lo(localizó sin ambigüedad — el alumno obtuvo
`3V_b = V_a` donde debía obtener `V_a = -V_b`. Esa es una detección conceptual precisa y
puntual, no una vaga. El conceptual fue que el supernodo quedó incompleto, sin traducir la
ley de corrientes a ecuación nodal.

### Alumno C — 4.3/10, Deficiente

| Ítem | Puntaje | Enunciado según el modelo |
|---|---|---|
| 1 | 1.2/2.5 | Diodo real vs ideal, curva I-V |
| 2 | 1.3/2.5 | Rectificador de media onda, diagrama y salida |
| 3 (numerada 4 en el papel) | 1.3/2.5 | Ventaja de onda completa |
| 4 (numerada 5 en el papel) | 0.5/2.5 | Modelo lineal por tramos |

**Errores detectados:** 5 conceptuales + 4 procedimentales.

De los procedimentales, el más específico de todo el estudio:

> "Esquema del rectificador con el capacitor conectado en serie y la resistencia antes del
> diodo; no se cierra el lazo ni se define la carga."

Este es el ítem **más parecido al caso del diodo invertido de la fixture**, y el modelo
**sí detectó un error de conexión del circuito rectificador**. Anota con cuidado si el
alumno cometió exactamente eso: es la única oportunidad que tenemos de saber si detecta
ese tipo de fallo.

### Alumno D — 5.6/10, Suficiente

| Ítem | Puntaje | Enunciado según el modelo |
|---|---|---|
| 1 | 1.3/2 | Diferencia curva I-V diodo ideal vs real |
| 2 | **0.0/2** | Funcionamiento de un circuito rectificador |
| 3 | 1.7/2 | Ecuación de Shockley, polarización directa |
| 4 | 1.3/2 | Ventaja de onda completa frente a media onda |
| 5 | 1.3/2 | Modelo lineal por tramos |

**Errores detectados:** 3 conceptuales + 3 procedimentales.

El ítem 2 quedó **en blanco** y el modelo ya lo señala: "ausencia total de desarrollo". Si al
mirar la entrega confirmas que estaba vacía, **eso es una detección correcta**, no un fallo:
sin desarrollo no hay error conceptual que ver.

---

## El hallazgo, y hasta dónde llega

De los **19 enunciados de error** de los tres informes, **ninguno** formula la afirmación
del alumno como falsa. Todos describen el error en positivo:

- "**Creer que** el diodo ideal también presenta característica I-V exponencial…"
- "**Confusión en** el significado de V_T: se refiere a ella como 'la tensión V_T'…"
- "**Atribuir al** modelo lineal por tramos la descripción del 'comportamiento en el
  tiempo'…"

Ninguno dice "el alumno afirma X, y X es incorrecto". El modelo **sí detecta** los errores
conceptuales y los describe con precisión —el error de signo `3V_b = V_a` lo
localizó sin ambigüedad—, pero **nunca los formula como refutación de una afirmación**.

### Por qué esto todavía no es un veredicto

Tres razones, y las tres importan:

1. **n = 3.** Tres casos no distinguen patrón de azar.
2. **Ninguno de los tres presenta el caso del diodo invertido.** Es el caso que
   motivó la pregunta, y no está en la muestra.
3. **No hay verdad etiquetada.** Que el estilo sea descriptivo es un hecho; que eso cueste
   detecciones es una hipótesis sin comprobar.

Lo que sí puede afirmarse hoy, con honestidad: **en estos tres casos el modelo no perdió
información por no usar el estilo de refutación.** En el alumno A la descripción fue
precisa y completa; en C y D los errores se localizaron. El problema de la fixture, si es
que existe, no se ha reproducido fuera de ella.

---

## Qué decide el veredicto

Al cruzar con tu etiquetación:

- **Aparece algún error que el modelo no mencionó** → el estilo descriptivo está costando
  detecciones. Se añade a `TAREA_POR_TIPO["examen"]` que señale explícitamente la
  afirmación falsa que el estudiante sostiene, y se revalida con las 3 entregas.
- **No aparece ninguno** → la fixture era ruido y **el prompt no se toca**.

En ambos casos el cambio, si lo hay, entra con su prueba en
`execution/test_evaluar_rubrica.py` y su entrada en `.agent/python.md`.