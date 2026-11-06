# Laboratorio I de Física

Medición, análisis gráfico y propiedades de la materia: del error experimental al informe reproducible

- Autor: Prof. César Rodríguez
- Duración: 10 semanas
- Versión: 1 — 6 de noviembre de 2026

## Fuente de verdad

`curso.yaml` es el descriptor del curso. Todo el material de este árbol
(sílabo, plan semanal, guía, prácticas, evaluaciones y laboratorio) se
genera desde él con:

```bash
python3 flujo_disenar_curso.py --curso cursos/LABORATORIO_I_FISICA/curso.yaml
```

Editar a mano un `.tex` generado se pierde en la siguiente ejecución: el
cambio va al YAML.

## Estructura

```
curso.yaml                 descriptor (fuente de verdad)
plan_estudios/             silabo.pdf y plan_semanal.pdf
docs/                      guia_estudiante.pdf
practicas/                 un documento por semana (taller o practica)
evaluaciones/              controles de fase y evaluacion_final
laboratorio/               docker-compose.yml y README
```

## Calendario

| Semana | Tema | Documento semanal |
| --- | --- | --- |
| 1 | La medición, la apreciación y el error | Taller: Medición, apreciación y expresión de resultados |
| 2 | Propagación de incertidumbres y notación científica | Taller: Del objeto al resultado: propagar sin inventar cifras |
| 3 | Graficación, linealización y lectura de una recta | Taller: De la curva a la recta: linealizar para entender |
| 4 | Mínimos cuadrados y estructura del informe | Taller: Ajustar, juzgar y escribir: el cierre de la fase uno |
| 5 | Volumen de un sólido por dos métodos | Práctica: Volumen de un sólido por dos métodos |
| 6 | Densidad de un cuerpo sólido | Práctica: Densidad de un cuerpo sólido |
| 7 | Centro de masa de un sistema de dos cuerpos | Práctica: Centro de masa de un sistema de dos cuerpos |
| 8 | Ley de Hooke y constante elástica | Práctica: Ley de Hooke y constante elástica |
| 9 | Péndulo simple y determinación de la gravedad | Práctica: Péndulo simple y determinación de la gravedad |
| 10 | Enfriamiento de un cuerpo sólido | Práctica: Enfriamiento de un cuerpo sólido |

## Portafolio del grupo y entregas

- Plataforma: GitHub
- Modalidad: Un repositorio privado por grupo, con el docente como colaborador de lectura. El repositorio es la entrega; no se reciben informes por correo ni impresos, salvo indicación expresa del docente.
- Revisión: El docente revisa el repositorio al finalizar cada semana y devuelve observaciones antes de la semana siguiente.
- Corte: Domingo a las 23:59 de la semana correspondiente. Lo entregado después del corte se corrige con la penalización prevista en las políticas.

### Estructura del portafolio

- README.md con integrantes, roles de la fase y tabla de semanas entregadas.
- semana_NN/informe.pdf con el informe de la práctica o el taller resuelto.
- semana_NN/datos/ con los CSV crudos, uno por ensayo, sin editar.
- semana_NN/analisis/ con los scripts que reproducen cada figura.
- semana_NN/figuras/ con las gráficas en PDF o PNG generadas por los scripts.
- semana_NN/README.md con lo que se hizo, lo que no se pudo verificar y por qué.

### Reglas de entrega

- Los datos crudos no se editan nunca; toda corrección vive en el script de análisis.
- Cada cifra del informe debe salir de una tabla de datos o de un script entregado.
- Los scripts se ejecutan de punta a punta sin pasos manuales intermedios.
- Ninguna tabla se entrega sin unidades ni sin la resolución del instrumento.
- El informe es grupal, pero las conclusiones se firman individualmente.
- Un resultado sin incertidumbre no se acepta como resultado.

## Reglas de uso

- Seguridad: no se energiza ningún equipo ni se manipula vidrio caliente sin autorización y sin el equipo de protección indicado.
- Honestidad académica: los datos se toman en la sesión y se declaran tal como se obtuvieron; fabricar o alterar datos anula la entrega y se reporta.
- Puntualidad: la entrega cierra el domingo a las 23:59; lo entregado después se corrige con la penalización prevista.
- Cuidado del material: cada instrumento se devuelve limpio y en su estuche; el material roto se reporta de inmediato.
- Trabajo en equipo: todos los integrantes firman las conclusiones y deben poder explicar cualquier parte del informe.
