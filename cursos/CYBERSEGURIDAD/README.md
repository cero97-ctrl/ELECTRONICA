# Ciberseguridad Aplicada

Ofensiva controlada, defensa, forense y marco legal sobre un laboratorio propio

- Autor: Prof. César Rodríguez
- Duración: 10 semanas
- Versión: 1 — 1 de noviembre de 2026

## Fuente de verdad

`curso.yaml` es el descriptor del curso. Todo el material de este árbol
(sílabo, plan semanal, guía, prácticas, evaluaciones y laboratorio) se
genera desde él con:

```bash
python3 flujo_disenar_curso.py --curso cursos/CYBERSEGURIDAD/curso.yaml
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
| 1 | Panorama de la ciberseguridad y superficie de ataque | Práctica: Inventario de superficie de ataque del laboratorio |
| 2 | Criptografía aplicada y gestión de secretos | Práctica: Caja de herramientas criptográficas |
| 3 | Marco legal, ético y normativo | Práctica: Carta de autorización y análisis de caso |
| 4 | Reconocimiento, OSINT y escaneo de puertos | Práctica: Huella digital + escáner propio contra el laboratorio |
| 5 | Vulnerabilidades web según OWASP Top 10 | Práctica: Explotación guiada y evidencia |
| 6 | Hardening, firewall y detección | Práctica: Línea base, hardening, firewall y detección |
| 7 | Desarrollo seguro y cadena de suministro | Práctica: Parchear y demostrar la mitigación |
| 8 | Forense digital: adquisición, artefactos y línea de tiempo | Práctica: Imagen forense, reconstrucción y línea de tiempo |
| 9 | Respuesta a incidentes y triage estático de malware | Práctica: Playbook y triage estático |
| 10 | Evaluación final práctica de alcance cerrado | Práctica: Auditoría de alcance cerrado |

## Repositorio GitHub y entregas

- Plataforma: GitHub
- Modalidad: Un repositorio privado por grupo, con el docente como colaborador de lectura.
- Revisión: El docente revisa el repositorio al finalizar cada semana de práctica.
- Corte: Domingo 23:59 de la semana correspondiente; lo posterior no se corrige.

### Estructura del repositorio

- README.md con integrantes, roles y tabla de semanas entregadas.
- semana_NN/informe.md o informe.pdf con el entregable de esa práctica.
- semana_NN/scripts/ con el código, con type hints y docstrings.
- semana_NN/evidencia/ con salidas, capturas y hashes anonimizados.
- semana_NN/README.md con el resumen de lo hecho y lo que no se pudo verificar.

### Reglas de entrega

- Nada de secretos, tokens ni contraseñas en el repositorio; las claves van en .env ignorado.
- Nada de imágenes de disco, muestras de malware ni binarios: solo hashes y enlaces.
- Evidencia anonimizada: sin datos personales de terceros ni credenciales reales.
- Un commit por entrega con mensaje "semana NN: <entregable>".
- La práctica cuenta como entregada solo si está en el repositorio antes del corte.

## Reglas de uso

- Cada grupo mantiene su propio repositorio GitHub y lo entrega actualizado antes del corte semanal; el docente revisa ese repositorio.
- {'El trabajo se hace desde el equipo y la conexión de cada grupo': 'solo objetivos propios, el laboratorio provisto o sistemas con autorización escrita; nunca infraestructura de la universidad ni de terceros.'}
- Solo se atacan objetivos propios o con autorización escrita y firmada.
- El laboratorio es local y nunca se expone a Internet.
- Las muestras de malware no se ejecutan y se manejan como copias inertes.
- La evidencia se anonimiza antes de entregarse.
- El uso indebido de las técnicas del curso tiene consecuencias académicas y legales.
- El código entregado usa type hints, docstrings estilo Google y manejo explícito de errores.
