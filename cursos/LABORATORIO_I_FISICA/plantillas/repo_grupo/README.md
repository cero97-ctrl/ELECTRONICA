# Laboratorio I de Física — Repositorio del grupo

> Plantilla semilla. Sustituye los marcadores `[Nombre del integrante N]` por los
> datos reales **en tu repositorio privado**. Esta plantilla no contiene datos
> personales y puede versionarse en el repo público del curso.

## Integrantes y roles

| Rol | Integrante |
| --- | --- |
| Medición | [Nombre del integrante 1] |
| Análisis | [Nombre del integrante 2] |
| Documentación | [Nombre del integrante 3] |
| Verificación | [Nombre del integrante 4] |

Los roles rotan al inicio de cada fase según lo publicado por el docente. Cada
semana debe quedar claro quién hizo la medición, el análisis, la documentación
y la verificación.

## Semanas entregadas

| Carpeta | Práctica | Entregada | Observaciones del docente |
| --- | --- | --- | --- |
| semana_01 | Taller 01 — Medición, apreciación y expresión de resultados | [ ] | | |
| semana_02 | Taller 02 — Del objeto al resultado: propagar sin inventar cifras | [ ] | | |
| semana_03 | Taller 03 — De la curva a la recta: linealizar para entender | [ ] | | |
| semana_04 | Taller 04 — Ajustar, juzgar y escribir: el cierre de la fase uno | [ ] | | |
| semana_05 | Práctica 05 — Volumen de un sólido por dos métodos | [ ] | | |
| semana_06 | Práctica 06 — Densidad de un cuerpo sólido | [ ] | | |
| semana_07 | Práctica 07 — Centro de masa de un sistema de dos cuerpos | [ ] | | |
| semana_08 | Práctica 08 — Ley de Hooke y constante elástica | [ ] | | |
| semana_09 | Práctica 09 — Péndulo simple y determinación de la gravedad | [ ] | | |
| semana_10 | Práctica 10 — Enfriamiento de un cuerpo sólido | [ ] | | |

**Corte:** Domingo a las 23:59 de la semana correspondiente. Lo entregado después del corte se corrige con la penalización prevista en las políticas.

## Estructura obligatoria de cada semana

```text
semana_NN/
|-- informe.pdf          # el informe de la práctica
|-- datos/               # CSV crudos, uno por ensayo, sin editar
|-- analisis/            # scripts de Python que reproducen cada figura
|-- figuras/             # gráficas en PDF o PNG generadas por los scripts
`-- README.md            # qué se hizo, qué no se pudo verificar y por qué
```

La entrega es el repositorio, no un archivo suelto. Un informe sin sus datos
crudos y sin el script que genera sus figuras no es trazable y se corrige como
incompleto.

## Reglas de entrega

- Los datos crudos no se editan nunca; toda corrección vive en `analisis/`.
- Cada cifra del informe debe salir de un CSV o de un script entregado.
- Los scripts se ejecutan de punta a punta sin pasos manuales intermedios.
- Nada de credenciales ni tokens en el repositorio; las claves van en `.env` ignorado.
- El informe es grupal, pero las conclusiones se firman individualmente.
- Un resultado sin incertidumbre no se acepta como resultado.

## Contrato de salida de los scripts

Cada script de `analisis/` imprime un único objeto JSON por la salida estándar:

```json
{
  "status": "ok",
  "practica": 1,
  "magnitud": "resistencia",
  "valor": 99.4,
  "unidad": "ohm",
  "incertidumbre": 0.6,
  "metodo": "ajuste_lineal_minimos_cuadrados",
  "n_puntos": 8,
  "residual_max": 0.012,
  "fuente_datos": "semana_01/datos/iv_resistor_220.csv",
  "errores": []
}
```

`status` vale `ok` o `error`; si es `error`, `errores` explica el motivo y el
programa sale con código distinto de cero. Toda magnitud lleva unidad explícita
e incertidumbre, y las figuras se generan desde el script, nunca a mano.

## Privacidad

Este repositorio es privado y el docente es colaborador de lectura. No subir
cédulas, correos ni credenciales. Las conclusiones se firman individualmente.
