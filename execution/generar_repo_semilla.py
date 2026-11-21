#!/usr/bin/env python3
"""
generar_repo_semilla.py — Generador determinista del repo semilla de grupos (Layer 3)

Lee el descriptor `curso.yaml` y produce, sin red ni reloj, el árbol que cada
grupo debe clonar para entregar sus informes: README raíz con integrantes/roles
y tabla de semanas, README por semana con los títulos reales de las prácticas,
.gitignore, y las carpetas `datos/`, `analisis/` y `figuras/` con .gitkeep.

La plantilla NO contiene datos personales: los integrantes son marcadores.
Nunca borra archivos existentes; `--forzar` solo sobrescribe los que genera.

Arquitectura: directiva crear_repo_semilla_estudiantes.yaml (L1) →
flujo_crear_repo_semilla.py (L2) → este script (L3).

Uso:
  python3 execution/generar_repo_semilla.py --check --json
  python3 execution/generar_repo_semilla.py --salida DIR --forzar --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CURSO_POR_DEFECTO = PROJECT_ROOT / "cursos/LABORATORIO_II_FISICA/curso.yaml"
SALIDA_POR_DEFECTO = PROJECT_ROOT / "cursos/LABORATORIO_II_FISICA/plantillas/repo_grupo"
N_SEMANAS = 10
CARPETAS_SEMANA = ("datos", "analisis", "figuras")

GITIGNORE = """# Secretos y entornos (nunca subir credenciales al repo del grupo)
.env
.env.*
*.dev.vars

# Python
__pycache__/
*.py[cod]
.pytest_cache/
.venv/
venv/

# Auxiliares de LaTeX. El informe.pdf SÍ se entrega: no se ignora.
*.aux
*.log
*.out
*.toc
*.synctex.gz
*.fls
*.fdb_latexmk

# Sistemas operativos
.DS_Store
Thumbs.db
"""

REGLAS_ENTREGA = """- Los datos crudos no se editan nunca; toda corrección vive en `analisis/`.
- Cada cifra del informe debe salir de un CSV o de un script entregado.
- Los scripts se ejecutan de punta a punta sin pasos manuales intermedios.
- Nada de credenciales ni tokens en el repositorio; las claves van en `.env` ignorado.
- El informe es grupal, pero las conclusiones se firman individualmente.
- Un resultado sin incertidumbre no se acepta como resultado.
"""

CONTRATO_JSON = """```json
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
```"""


def cargar_descriptor(ruta: Path) -> dict:
    """Carga el YAML del curso; falla ruidosamente si no es un mapa."""
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"no se pudo leer el descriptor {ruta}: {exc}") from exc
    if not isinstance(datos, dict):
        raise ValueError(f"el descriptor {ruta} no es un objeto YAML")
    return datos


def titulos_practicas(datos: dict) -> dict[int, str]:
    """Devuelve {numero: titulo de la práctica} para las 10 semanas."""
    semanas = datos.get("semanas")
    if not isinstance(semanas, list) or not semanas:
        raise ValueError("el descriptor no declara una lista de `semanas`")
    titulos: dict[int, str] = {}
    for semana in semanas:
        if not isinstance(semana, dict):
            raise ValueError("cada entrada de `semanas` debe ser un mapa")
        numero = semana.get("numero")
        titulo = (semana.get("practica") or {}).get("titulo")
        if not isinstance(numero, int) or not isinstance(titulo, str) or not titulo.strip():
            raise ValueError("toda semana debe tener `numero` entero y `practica.titulo`")
        titulos[numero] = titulo.strip()
    esperadas = set(range(1, N_SEMANAS + 1))
    if set(titulos) != esperadas:
        faltan = sorted(esperadas - set(titulos))
        sobran = sorted(set(titulos) - esperadas)
        raise ValueError(
            f"se esperaban las semanas 1..{N_SEMANAS}; faltan {faltan}, sobran {sobran}"
        )
    return titulos


def nombres_roles(datos: dict) -> list[str]:
    """Nombres de los roles del curso, en el orden declarado."""
    grupos = datos.get("grupos") or {}
    roles = grupos.get("roles")
    if not isinstance(roles, list) or not roles:
        raise ValueError("el descriptor no declara `grupos.roles`")
    nombres = [(r or {}).get("nombre") for r in roles]
    if any(not isinstance(n, str) or not n.strip() for n in nombres):
        raise ValueError("todo rol debe tener un `nombre` no vacío")
    return [n.strip() for n in nombres]


def corte_entrega(datos: dict) -> str:
    """Texto del corte semanal, tal como lo declara el descriptor."""
    entregas = datos.get("entregas") or {}
    corte = entregas.get("corte")
    if not isinstance(corte, str) or not corte.strip():
        raise ValueError("el descriptor no declara `entregas.corte`")
    return " ".join(corte.split())


def readme_raiz(titulos: dict[int, str], roles: list[str], corte: str) -> str:
    filas_roles = "\n".join(f"| {rol} | [Nombre del integrante {i}] |" for i, rol in enumerate(roles, 1))
    filas_semanas = "\n".join(
        f"| semana_{n:02d} | {titulos[n]} | [ ] | | |" for n in range(1, N_SEMANAS + 1)
    )
    return f"""# Laboratorio II de Física — Repositorio del grupo

> Plantilla semilla. Sustituye los marcadores `[Nombre del integrante N]` por los
> datos reales **en tu repositorio privado**. Esta plantilla no contiene datos
> personales y puede versionarse en el repo público del curso.

## Integrantes y roles

| Rol | Integrante |
| --- | --- |
{filas_roles}

Los roles rotan al inicio de cada fase según lo publicado por el docente. Cada
semana debe quedar claro quién hizo la medición, el análisis, la documentación
y la verificación.

## Semanas entregadas

| Carpeta | Práctica | Entregada | Observaciones del docente |
| --- | --- | --- | --- |
{filas_semanas}

**Corte:** {corte}

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

{REGLAS_ENTREGA}
## Contrato de salida de los scripts

Cada script de `analisis/` imprime un único objeto JSON por la salida estándar:

{CONTRATO_JSON}

`status` vale `ok` o `error`; si es `error`, `errores` explica el motivo y el
programa sale con código distinto de cero. Toda magnitud lleva unidad explícita
e incertidumbre, y las figuras se generan desde el script, nunca a mano.

## Privacidad

Este repositorio es privado y el docente es colaborador de lectura. No subir
cédulas, correos ni credenciales. Las conclusiones se firman individualmente.
"""


def readme_semanal(numero: int, titulo: str, corte: str, es_cierre: bool) -> str:
    extra = ""
    if es_cierre:
        extra = """
## Cierre del semestre

- [ ] `informe.pdf` individual, con las conclusiones firmadas por su autor.
- [ ] `portafolio/` con las diez semanas corregidas y el README raíz al día.
"""
    return f"""# Semana {numero:02d} — {titulo}

## Qué se hizo

[Describir el montaje, las mediciones y el análisis. Una frase por rol.]

## Qué no se pudo verificar y por qué

[Anotar lo que falló, qué se intentó y qué queda pendiente. Si no hubo
limitaciones, decirlo explícitamente.]

## Entregable de esta semana

- [ ] `informe.pdf` con las secciones obligatorias en el orden fijado.
- [ ] `datos/` con los CSV crudos, uno por ensayo, sin editar.
- [ ] `analisis/` con los scripts que generan cada figura y su JSON de salida.
- [ ] `figuras/` con las gráficas producidas por esos scripts.
- [ ] Este README completo.
{extra}
## Trazabilidad de cifras

| Cifra del informe | Origen (CSV o script) |
| --- | --- |
| [valor, unidad, incertidumbre] | [semana_{numero:02d}/datos/... o analisis/...] |

## Antes del corte

Corte: {corte}. Verificar que los datos crudos siguen intactos, que cada cifra
del texto sale de un CSV o de un script, y que los scripts corren de punta a
punta sin pasos manuales. Nada de credenciales en el repositorio; ningún
resultado sin incertidumbre.
"""


def plan_de_archivos(datos: dict) -> dict[str, str]:
    """Construye el mapa {ruta relativa: contenido}. Función pura."""
    titulos = titulos_practicas(datos)
    roles = nombres_roles(datos)
    corte = corte_entrega(datos)
    plan: dict[str, str] = {
        "README.md": readme_raiz(titulos, roles, corte),
        ".gitignore": GITIGNORE,
    }
    for numero in range(1, N_SEMANAS + 1):
        base = f"semana_{numero:02d}"
        plan[f"{base}/README.md"] = readme_semanal(
            numero, titulos[numero], corte, es_cierre=(numero == N_SEMANAS)
        )
        for carpeta in CARPETAS_SEMANA:
            plan[f"{base}/{carpeta}/.gitkeep"] = ""
    plan["semana_10/portafolio/.gitkeep"] = ""
    return plan


def verificar_plan(plan: dict[str, str], raiz: Path) -> list[str]:
    """Comprueba que cada archivo del plan exista y tenga el contenido exacto."""
    problemas: list[str] = []
    for ruta_relativa, contenido in plan.items():
        destino = raiz / ruta_relativa
        if not destino.is_file():
            problemas.append(f"falta {ruta_relativa}")
        elif destino.read_text(encoding="utf-8") != contenido:
            problemas.append(f"contenido distinto en {ruta_relativa}")
    return problemas


def escribir_plan(plan: dict[str, str], raiz: Path, forzar: bool = False) -> list[str]:
    """Escribe el plan. Nunca elimina archivos; con `forzar` sobrescribe los generados."""
    if raiz.exists() and not raiz.is_dir():
        raise ValueError(f"la salida existe y no es un directorio: {raiz}")
    existentes = [r for r in plan if (raiz / r).exists()]
    if existentes and not forzar:
        raise ValueError(
            "la salida ya contiene archivos generados; usa --forzar para "
            f"sobrescribir solo estos: {', '.join(existentes[:5])}"
        )
    for ruta_relativa, contenido in plan.items():
        destino = raiz / ruta_relativa
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporal = destino.with_name(destino.name + ".tmp")
        temporal.write_text(contenido, encoding="utf-8", newline="\n")
        temporal.replace(destino)
    problemas = verificar_plan(plan, raiz)
    if problemas:
        raise OSError("verificación fallida: " + "; ".join(problemas[:5]))
    return problemas


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genera el repo semilla de grupos del Laboratorio II de Física."
    )
    parser.add_argument("--curso", type=Path, default=CURSO_POR_DEFECTO)
    parser.add_argument("--salida", type=Path, default=SALIDA_POR_DEFECTO)
    parser.add_argument("--forzar", action="store_true", help="Sobrescribe solo los archivos generados.")
    parser.add_argument("--check", action="store_true", help="Valida sin escribir.")
    parser.add_argument("--json", action="store_true", help="Salida JSON.")
    args = parser.parse_args()

    try:
        datos = cargar_descriptor(args.curso)
        plan = plan_de_archivos(datos)
    except ValueError as exc:
        print(json.dumps({"status": "error", "code": 2, "message": str(exc)}) if args.json else f"error: {exc}")
        return 2

    problemas: list[str] = []
    if not args.check:
        try:
            problemas = escribir_plan(plan, args.salida, forzar=args.forzar)
        except (ValueError, OSError) as exc:
            print(json.dumps({"status": "error", "code": 3, "message": str(exc)}) if args.json else f"error: {exc}")
            return 3
    else:
        # En modo check solo se valida el descriptor y el plan en memoria.
        if len(plan) != 2 + N_SEMANAS * (1 + len(CARPETAS_SEMANA)) + 1:
            problemas.append("el plan no tiene el número esperado de archivos")

    resultado = {
        "status": "ok" if not problemas else "error",
        "code": 0 if not problemas else 4,
        "curso": str(args.curso),
        "salida": str(args.salida),
        "semanas": N_SEMANAS,
        "archivos": len(plan),
        "roles": nombres_roles(datos),
        "check": args.check,
        "problemas": problemas,
    }
    print(json.dumps(resultado, ensure_ascii=False, indent=2) if args.json else
          f"semilla {'validada' if args.check else 'generada'}: {len(plan)} archivos en {args.salida}")
    return 0 if not problemas else 4


if __name__ == "__main__":
    sys.exit(main())
