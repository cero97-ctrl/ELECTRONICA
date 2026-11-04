# Laboratorio del curso

El laboratorio físico es presencial y obligatorio: los montajes se hacen en la mesa con instrumentos reales. El contenedor es opcional y sirve solo para el análisis de datos cuando el equipo del grupo no tiene Python instalado.

Cada grupo trabaja desde su propio equipo y conexión. Este laboratorio no
necesita red compartida: los servicios se publican solo en `localhost`.

Red Docker: `labfisica` sobre `172.29.0.0/24`.

## Servicios

| Contenedor | Imagen | Puerto local | Propósito |
| --- | --- | --- | --- |
| `analisis` | `jupyter/scipy-notebook:latest` | 8888 | Entorno Jupyter con NumPy, SciPy y Matplotlib para ajustar datos, propagar incertidumbres y generar las figuras del informe. |

Requisitos: Requiere alrededor de 2 GB de RAM libre y 3 GB de disco. La imagen incluye NumPy, SciPy, Matplotlib y Pandas, suficientes para todos los ajustes del curso.

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

- El contenedor procesa datos; nunca sustituye una medición real en la mesa.
- Se accede en localhost y no se expone a Internet.
- Los CSV crudos se montan de solo lectura para impedir edición accidental.
- Cada grupo usa su propio equipo; no hay red ni servidores compartidos del curso.
- Lo que no se midió no se simula como si se hubiera medido.
