# Laboratorio del curso

El docker-compose de esta carpeta es opcional. Cada grupo puede usar su propio entorno en su PC siempre que respete el alcance autorizado.

Cada grupo trabaja desde su propio equipo y conexión. Este laboratorio no
necesita red compartida: los servicios se publican solo en `localhost`.

Red Docker: `cyberlab` sobre `172.28.0.0/24`.

## Servicios

| Contenedor | Imagen | Puerto local | Propósito |
| --- | --- | --- | --- |
| `objetivo-web` | `vulnerables/web-dvwa:latest` | 8081 | Inyección SQL, XSS, LFI y control de acceso (semanas 5 y 7) |
| `objetivo-juice` | `bkimminich/juice-shop:latest` | 3000 | Retos guiados de OWASP Top 10 (semanas 5 y 7) |
| `objetivo-linux` | `ubuntu:24.04` | 2222 | Hardening, SSH y artefactos forenses (semanas 6, 8 y 9) |

Requisitos: Requiere ~2 GB de RAM libre y ~5 GB de disco; DVWA y Juice Shop juntos consumen menos de 700 MB.

## Puesta en marcha

```bash
docker compose -f laboratorio/docker-compose.yml up -d
docker compose -f laboratorio/docker-compose.yml ps
```

## Reinicio a estado inicial

```bash
docker compose -f laboratorio/docker-compose.yml down -v
```

## Reglas

- {'Cada grupo trabaja desde su propio equipo y red': 'no hay red compartida del curso.'}
- El laboratorio corre en localhost y nunca se expone a Internet.
- Solo se atacan contenedores del laboratorio o sistemas con autorización escrita y firmada.
- {'Las muestras de malware no se ejecutan': 'el análisis es estático y sobre copias inertes.'}
- La evidencia se anonimiza antes de entregarse; los datos personales no salen del laboratorio.
- Se prohíbe el uso de estas técnicas contra la infraestructura de la universidad o de terceros.
