#!/usr/bin/env python3
"""token_resultados.py — qué variable de `.env` lleva el token de un repo de resultados.

Una sola regla para los dos scripts que la necesitan, porque la derivan por caminos
distintos y el mismo curso tiene que acabar en el mismo nombre:

  - `flujo_desplegar_worker_cuestionarios.py` sube el token al Worker y elige por
    **entorno de wrangler** (`--env lab2`).
  - `execution/descargar_resultados.py` lo lee para bajar las entregas y elige por
    **repo** (`cero97-ctrl/cuestionarios-resultados-lab2`).

Si cada uno derivara el nombre a su manera, un curso podría desplegar con un token y
leer con otro. Ese fallo no se ve al desplegar: wrangler acepta el secreto, `/salud`
responde `ok`, y el 404 aparece en la primera entrega o al sacar el acta, donde el
mensaje habla del repo y no del nombre de la variable. Por eso la derivación es una
función pura y vive aquí.

Regla: `GITHUB_TOKEN_RESULTADOS` para el repo base (el de los roles de
ciberseguridad); `GITHUB_TOKEN_RESULTADOS_<SUFIJO>` para un repo con sufijo
(`-lab2` → `_LAB2`) o un entorno de wrangler (`lab2` → `_LAB2`). El sufijo se
normaliza a mayúsculas y `-` → `_`, igual que la clave del entorno.
"""

from __future__ import annotations

BASE = "GITHUB_TOKEN_RESULTADOS"
FAMILIA = "cuestionarios-resultados"


def variable(sufijo: str | None) -> str:
    """Nombre de la variable para `sufijo` (entorno o sufijo de repo)."""
    if sufijo is None:
        return BASE
    limpio = sufijo.strip().upper().replace("-", "_")
    return f"{BASE}_{limpio}" if limpio else BASE


def sufijo_de_repo(repo: str | None) -> str | None:
    """Sufijo del repo dentro de la familia de resultados; `None` para el base.

    `cero97-ctrl/cuestionarios-resultados` → `None` (token genérico)
    `cero97-ctrl/cuestionarios-resultados-lab2` → `"lab2"`
    Cualquier otro repo (uno de prácticas, o vacío) → `None`: no se inventa un
    sufijo a partir de un nombre que no pertenece a la familia.
    """
    if not repo:
        return None
    nombre = repo.strip().rstrip("/").rsplit("/", 1)[-1]
    prefijo = f"{FAMILIA}-"
    if nombre.startswith(prefijo):
        sufijo = nombre[len(prefijo):].strip()
        return sufijo or None
    return None
