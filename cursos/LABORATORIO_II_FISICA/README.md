# Laboratorio II de Física

Electricidad y magnetismo aplicados: instrumentación, circuitos y tratamiento de datos experimentales

- Autor: Prof. César Rodríguez
- Duración: 10 semanas
- Versión: 1 — 2 de noviembre de 2026

## Fuente de verdad

`curso.yaml` es el descriptor del curso. Todo el material de este árbol
(sílabo, plan semanal, guía, prácticas, evaluaciones y laboratorio) se
genera desde él con:

```bash
python3 flujo_disenar_curso.py --curso cursos/LABORATORIO_II_FISICA/curso.yaml
```

Editar a mano un `.tex` generado se pierde en la siguiente ejecución: el
cambio va al YAML.

## Estructura

```
curso.yaml                 descriptor (fuente de verdad)
plan_estudios/             silabo.pdf y plan_semanal.pdf
docs/                      guia_estudiante.pdf
practicas/                 practica_01.pdf .. una por semana
evaluaciones/              controles de fase y evaluacion_final
laboratorio/               docker-compose.yml y README
```

## Calendario

| Semana | Tema | Práctica |
| --- | --- | --- |
| 1 | Manejo del instrumental eléctrico y característica corriente-tensión | Característica corriente-tensión de un resistor |
| 2 | Determinación de una resistencia eléctrica por tres métodos | Comparación de tres métodos para medir una resistencia |
| 3 | Resistencia interna de instrumentos y de una fuente real | Caracterización de la fuente y de los instrumentos |
| 4 | Circuitos eléctricos y teoremas fundamentales | Circuitos serie, paralelo y red de dos mallas |
| 5 | Elementos no lineales y el diodo semiconductor | Característica estática del diodo y extracción de parámetros |
| 6 | Respuesta de R, L y C a la tensión senoidal | Determinación de reactancias, de C y de L en régimen senoidal |
| 7 | Circuitos resonantes serie y paralelo | Resonancia serie y paralelo con L y C del inventario |
| 8 | Carga y descarga de un capacitor | Carga y descarga de un capacitor con osciloscopio |
| 9 | Práctica integradora, caracterización completa de un circuito RLC | El mismo circuito por dos vías independientes |
| 10 | Evaluación final práctica y defensa del portafolio | Examen práctico individual y cierre del portafolio |

## Repositorio del grupo y entregas semanales

- Plataforma: GitHub
- Modalidad: Un repositorio privado por grupo, con el docente como colaborador de lectura. El repositorio es la entrega; no se reciben informes por correo ni impresos, salvo indicación expresa del docente.
- Revisión: El docente revisa el repositorio al finalizar cada semana de práctica y devuelve observaciones antes de la semana siguiente.
- Corte: Domingo a las 23:59 de la semana correspondiente. Lo entregado después del corte se corrige con la penalización prevista en las políticas.

### Estructura del repositorio

- README.md con integrantes, roles de la fase y tabla de semanas entregadas.
- semana_NN/informe.pdf con el informe de la práctica.
- semana_NN/datos/ con los CSV crudos, uno por ensayo, sin editar.
- semana_NN/analisis/ con los scripts de Python que reproducen cada figura.
- semana_NN/figuras/ con las gráficas en PDF o PNG generadas por los scripts.
- semana_NN/README.md con lo que se hizo, lo que no se pudo verificar y por qué.

### Reglas de entrega

- Los datos crudos no se editan nunca; toda corrección vive en el script de análisis.
- Cada cifra del informe debe salir de una tabla de datos o de un script entregado.
- Los scripts se ejecutan de punta a punta sin pasos manuales intermedios.
- Nada de credenciales ni tokens en el repositorio; las claves van en .env ignorado.
- El informe es grupal, pero las conclusiones se firman individualmente.
- Un resultado sin incertidumbre no se acepta como resultado.

## Reglas de uso

- La seguridad eléctrica es previa a cualquier medición; se corta la alimentación antes de modificar un montaje.
- Ningún instrumento se conecta sin verificar rango y polaridad, y ningún capacitor electrolítico se conecta invertido.
- Los datos crudos son inalterables; toda corrección se documenta en el script de análisis y se explica en el informe.
- Todo resultado se expresa en unidades del Sistema Internacional con cifras significativas coherentes con su incertidumbre.
- Un resultado sin incertidumbre no se acepta, y una conclusión sin contraste con el modelo tampoco.
- El informe es grupal, pero cada integrante firma sus propias conclusiones y debe poder defenderlas en la oral.
- La entrega fuera de corte pierde el 20 por ciento de la nota de la práctica por cada día de retraso, hasta tres días.
- Se considera falta grave fabricar, alterar o copiar datos, o entregar el informe de otro grupo; se aplica el reglamento disciplinario.
- El instrumental prestado se devuelve completo y revisado; un daño por mal uso se reporta de inmediato al docente.
- La asistencia al laboratorio es obligatoria; dos inasistencias injustificadas a prácticas invalidan la evaluación de esa fase.
- Los repositorios son privados y no contienen datos personales de terceros ni credenciales.
