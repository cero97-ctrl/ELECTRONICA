#!/usr/bin/env python3
"""
generar_tareas_curso.py — Tareas por grupo y fase (Layer 3: Execution)

Lee el descriptor del curso y emite, de forma determinista, un documento por
grupo para una fase: el rol que le toca (según la rotación declarada en
`grupos.asignacion_inicial`), lo que ese rol hace en cada práctica y el trabajo
semana a semana de la fase. Todo el LaTeX usa el estilo infográfico del
workspace.

Uso:
    python3 execution/generar_tareas_curso.py --curso cursos/CYBERSEGURIDAD/curso.yaml --fase 1
    python3 execution/generar_tareas_curso.py --curso <yaml> --fase 2 --sin-compilar
    python3 execution/generar_tareas_curso.py --curso <yaml> --fase 1 --json

Salida (stdout, JSON):
    {"status": "ok", "fase": 1, "salida": "...", "artefactos": [...], "compilados": N}

Códigos de salida:
    0 — tareas generadas y verificadas
    1 — argumentos de línea de comandos inválidos
    2 — descriptor ilegible o que no es YAML
    3 — descriptor o fase inválidos (rol sin instrucciones, fase inexistente)
    4 — error de compilación LaTeX (se conserva el .log y se informa la línea)
    5 — error de escritura en disco

Por qué existe: el rol de un grupo no se deduce leyendo la práctica; se elige.
Asignarlo a mano invita a que dos documentos digan cosas distintas. Aquí la
rotación es una función de (fase, grupo) y el rol una tabla del descriptor.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import unicodedata
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
RAIZ = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(RAIZ))

from generar_material_curso import (  # noqa: E402
    FUENTE_FECHA,
    _compilar,
    _documento,
    _epoch,
    _lista,
    _metadatos_curso,
    _slug,
    _t,
    _tabla_datos,
    banda_titulo,
    seccion_con_icono,
)

EXIT_OK = 0
EXIT_USO = 1
EXIT_DESCRIPTOR = 2
EXIT_INVALIDO = 3
EXIT_LATEX = 4
EXIT_DISCO = 5


def _slug_rol(nombre: str) -> str:
    """Nombre de fichero estable sin acentos para un rol."""
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFKD", nombre) if not unicodedata.combining(c)
    )
    return _slug(sin_acentos)


def cargar_descriptor(curso: Path) -> dict[str, Any]:
    """Carga el descriptor YAML del curso.

    Args:
        curso: Ruta al `curso.yaml`.

    Returns:
        Descriptor como diccionario.

    Raises:
        ValueError: si el fichero no existe o no es un mapa YAML.
    """
    if not curso.exists():
        raise ValueError(f"no existe el descriptor {curso}")
    try:
        datos = yaml.safe_load(curso.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"el descriptor no es YAML válido: {exc}") from exc
    if not isinstance(datos, dict):
        raise ValueError("el descriptor no es un mapa YAML")
    return datos


def _fase(datos: dict[str, Any], numero: int) -> dict[str, Any]:
    """Devuelve el bloque de la fase pedida.

    Args:
        datos: Descriptor del curso.
        numero: Identificador de la fase.

    Returns:
        Bloque de la fase.

    Raises:
        ValueError: si la fase no existe.
    """
    for fase in datos.get("fases") or []:
        if int(fase.get("id", 0)) == numero:
            return fase
    raise ValueError(f"la fase {numero} no existe en el descriptor")


def _semanas_de_fase(datos: dict[str, Any], fase: dict[str, Any]) -> list[dict[str, Any]]:
    """Semanas del descriptor que pertenecen a la fase, en orden.

    Args:
        datos: Descriptor del curso.
        fase: Bloque de la fase.

    Returns:
        Lista de semanas ordenadas por número.
    """
    pedidas = {int(n) for n in fase.get("semanas") or []}
    return sorted(
        (s for s in datos.get("semanas") or [] if int(s.get("numero", 0)) in pedidas),
        key=lambda s: int(s["numero"]),
    )


def roles_de_la_fase(
    datos: dict[str, Any], fase: int
) -> list[tuple[int, dict[str, Any]]]:
    """Asigna un rol a cada grupo rotando una posición por fase.

    La rotación es una función pura de `(fase, grupo)` sobre el orden declarado
    en `grupos.asignacion_inicial`: el grupo `i` recibe el rol
    `(i + fase - 1) mod n`. Así cada grupo pasa por los cuatro roles en las
    fases con roles, y la asignación es reproducible sin sorteo.

    Args:
        datos: Descriptor del curso.
        fase: Número de fase (1-based).

    Returns:
        Lista de tuplas `(numero_de_grupo, rol)`.

    Raises:
        ValueError: si faltan roles o la asignación inicial no coincide.
    """
    grupos = datos.get("grupos") or {}
    roles = {r["nombre"]: r for r in grupos.get("roles") or []}
    inicial = grupos.get("asignacion_inicial") or []
    if not inicial or sorted(inicial) != sorted(roles):
        raise ValueError(
            "grupos.asignacion_inicial debe listar exactamente los roles de 'grupos.roles'"
        )
    turno = (fase - 1) % len(inicial)
    return [
        (i + 1, roles[inicial[(i + turno) % len(inicial)]]) for i in range(len(inicial))
    ]


def validar_tareas(datos: dict[str, Any], fase: int) -> list[str]:
    """Comprueba lo que el generador necesita para no inventar contenido.

    Args:
        datos: Descriptor del curso.
        fase: Número de fase a generar.

    Returns:
        Lista de problemas; vacía si la fase es generable.
    """
    problemas: list[str] = []
    meta = datos.get("meta") or {}
    for clave in ("codigo", "titulo", "autor", "fecha", "fecha_iso"):
        if not meta.get(clave):
            problemas.append(f"meta.{clave} es obligatorio para emitir la tarea")

    try:
        bloque = _fase(datos, fase)
    except ValueError as exc:
        return problemas + [str(exc)]

    fases_con_roles = [int(f) for f in (datos.get("grupos") or {}).get("fase_con_roles") or []]
    if fases_con_roles and fase not in fases_con_roles:
        problemas.append(
            f"la fase {fase} no está en grupos.fase_con_roles {fases_con_roles}: "
            "esa fase no tiene roles de grupo"
        )

    try:
        asignados = roles_de_la_fase(datos, fase)
    except ValueError as exc:
        problemas.append(str(exc))
        asignados = []

    for _, rol in asignados:
        if not rol.get("descripcion"):
            problemas.append(f"el rol {rol.get('nombre')!r} no tiene descripción")
        if not rol.get("en_la_practica"):
            problemas.append(
                f"el rol {rol.get('nombre')!r} no tiene 'en_la_practica': "
                "sin eso la tarea no le dice al grupo qué hacer"
            )

    semanas = _semanas_de_fase(datos, bloque)
    if not semanas:
        problemas.append(f"la fase {fase} no tiene semanas asociadas")
    for semana in semanas:
        practica = semana.get("practica") or {}
        for clave in ("titulo", "escenario", "pasos", "entregable"):
            if not practica.get(clave):
                problemas.append(f"semana {semana.get('numero')}: falta practica.{clave}")

    entregas = datos.get("entregas") or {}
    for clave in ("corte", "estructura", "reglas"):
        if not entregas.get(clave):
            problemas.append(f"entregas.{clave} es obligatorio para explicar la entrega")
        for item in entregas.get(clave) or []:
            if clave in ("estructura", "reglas") and not isinstance(item, str):
                problemas.append(
                    f"entregas.{clave} contiene un ítem que no es texto ({item!r})"
                )

    return problemas


def tex_tarea(
    datos: dict[str, Any], fase_num: int, grupo: int, rol: dict[str, Any]
) -> str:
    """Genera el documento de tarea de un grupo para una fase.

    Args:
        datos: Descriptor validado.
        fase_num: Número de fase.
        grupo: Número de grupo (1-based).
        rol: Bloque del rol asignado.

    Returns:
        Documento LaTeX completo.
    """
    meta = datos["meta"]
    fase = _fase(datos, fase_num)
    semanas = _semanas_de_fase(datos, fase)
    entregas = datos.get("entregas") or {}
    numeros = [int(s["numero"]) for s in semanas]

    partes: list[str] = [
        banda_titulo(
            _t(f"Tarea de la fase {fase_num} --- Grupo {grupo}: {rol['nombre']}"),
            _t(
                f"{fase['nombre']} --- semanas {numeros[0]} a {numeros[-1]}"
                f" --- {meta['titulo']}"
            ),
        ),
        _metadatos_curso(meta),
        _tabla_datos(
            [
                ("Curso", _t(f"{meta['codigo']} --- {meta['titulo']}")),
                ("Fase", _t(f"{fase_num} --- {fase['nombre']}")),
                ("Semanas", _t(", ".join(str(n) for n in numeros))),
                ("Grupo", _t(f"Grupo {grupo}")),
                ("Rol asignado", r"\textbf{" + _t(rol["nombre"]) + "}"),
                (
                    "Entrega",
                    _t(
                        f"{entregas.get('plataforma', 'Repositorio')} del grupo, "
                        f"carpeta {'/'.join(f'semana_{n:02d}' for n in numeros)}"
                    ),
                ),
                ("Corte", _t(str(entregas.get("corte", "")))),
            ]
        ),
        seccion_con_icono("user-shield", "Tu rol en esta fase"),
        _t(rol["descripcion"]),
        r"\textbf{En cada práctica te corresponde:}",
        _lista(rol["en_la_practica"]),
        "\\begin{cajaConcepto}"
        + r"\textbf{Qué aporta este rol al entregable:} "
        + _t(rol.get("aporta", ""))
        + "\n\\end{cajaConcepto}",
        seccion_con_icono("calendar-alt", f"Trabajo de las semanas {numeros[0]} a {numeros[-1]}"),
        _t(
            "Cada semana tiene su propia práctica y su propia entrega. El rol cambia el "
            "énfasis del trabajo, no el objetivo: todos los grupos resuelven la misma "
            "práctica y comparan resultados en clase."
        ),
    ]

    for semana in semanas:
        practica = semana["practica"]
        numero = int(semana["numero"])
        partes.append(
            f"\\begin{{tcolorbox}}[cajaContenido,title={{"
            + _t(f"Semana {numero} --- {practica['titulo']}")
            + "}]\n"
            + r"\textbf{Objetivo:} "
            + _t(semana["objetivo"])
            + "\n\n"
            + r"\textbf{Escenario:} "
            + _t(practica["escenario"])
            + "\n\n"
            + r"\textbf{Pasos:}"
            + "\n"
            + _lista(practica["pasos"], entorno="enumerate")
            + "\n"
            + r"\textbf{Entregable de la semana:} "
            + _t(practica["entregable"])
            + "\n\n"
            + r"\textbf{Tu aporte como "
            + _t(rol["nombre"])
            + r" al entregable de la semana:}" + " "
            + _t(rol.get("aporta", ""))
            + "\n\n"
            + r"\textbf{Ruta en el repositorio:} \texttt{semana\_"
            + f"{numero:02d}"
            + r"/} (informe, scripts y evidencia)."
            + "\n\\end{tcolorbox}"
        )

    partes.append(seccion_con_icono("code-branch", "Entrega y revisión"))
    partes.append(
        _lista(
            [
                f"Repositorio: {entregas.get('modalidad', '')}",
                f"Cadencia de revisión: {entregas.get('cadencia', '')}",
                f"Corte: {entregas.get('corte', '')}",
            ]
        )
    )
    partes.append(r"\textbf{Estructura mínima del repositorio:}")
    partes.append(_lista([str(e) for e in entregas.get("estructura") or []]))
    partes.append(r"\textbf{Reglas de la entrega:}")
    partes.append(_lista([str(r) for r in entregas.get("reglas") or []]))

    partes.append(seccion_con_icono("clipboard-check", "Lista de verificación"))
    partes.append(
        _lista(
            [
                f"Tu documento está en la carpeta de la semana correspondiente, no en la raíz.",
                f"La evidencia está anonimizada y sin secretos, datos personales ni imágenes de disco.",
                f"El informe explica qué se hizo, cómo se verificó y qué quedó fuera de alcance.",
                f"El commit de la semana está hecho antes del corte y describe el entregable.",
                f"El trabajo corresponde al rol {rol['nombre']} y se nota en el énfasis del informe.",
            ]
        )
    )

    partes.append(
        "\\begin{tcolorbox}[cajaMejora]\\textbf{Antes de empezar:} confirma que el objetivo es "
        "un contenedor del laboratorio o un sistema con autorización escrita del docente. "
        "Si no lo es, detente y consúltalo: la práctica no se corrige sin ese requisito."
        "\n\\end{tcolorbox}"
    )
    partes.append(
        "\\begin{cajaRecuerda}La práctica se corrige con la rúbrica de "
        + _t(str(meta.get("codigo", "")))
        + " (criterios y pesos publicados en el curso). Una entrega fuera de plazo no se "
        "evalúa; el repositorio es la única prueba de que el trabajo existió."
        "\n\\end{cajaRecuerda}"
    )

    return _documento(meta, _t(f"Tarea fase {fase_num} --- Grupo {grupo}"), "\n\n".join(partes))


def generar(
    datos: dict[str, Any], fase: int, salida: Path, compilar: bool
) -> tuple[list[dict[str, Any]], list[str]]:
    """Escribe y compila el documento de cada grupo de la fase.

    Args:
        datos: Descriptor validado.
        fase: Número de fase.
        salida: Directorio `tareas/` del curso.
        compilar: Si es False, escribe solo los `.tex`.

    Returns:
        Tupla `(artefactos, errores)`.
    """
    meta = datos["meta"]
    codigo = _slug(meta["codigo"])
    destino_dir = salida / f"fase_{fase}"
    destino_dir.mkdir(parents=True, exist_ok=True)
    build = RAIZ / ".tmp" / "latex_build" / f"tareas_{codigo}_fase_{fase}"
    build.mkdir(parents=True, exist_ok=True)
    os.environ[FUENTE_FECHA] = str(_epoch(meta))

    artefactos: list[dict[str, Any]] = []
    errores: list[str] = []
    for grupo, rol in roles_de_la_fase(datos, fase):
        job = f"grupo_{grupo}_{_slug_rol(rol['nombre'])}"
        tex = destino_dir / f"{job}.tex"
        tex.write_text(tex_tarea(datos, fase, grupo, rol), encoding="utf-8")
        artefacto: dict[str, Any] = {"job": job, "tex": str(tex), "pdf": None, "errores": [], "overfull": 0}
        if compilar:
            resultado = _compilar(tex.read_text(encoding="utf-8"), job, build, tex)
            artefacto.update(resultado)
            errores.extend(resultado.get("errores") or [])
        artefactos.append(artefacto)
    return artefactos, errores


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada del generador.

    Args:
        argv: Argumentos de línea de comandos (por defecto, sys.argv[1:]).

    Returns:
        Código de salida del proceso.
    """
    parser = argparse.ArgumentParser(
        description="Genera un documento de tarea por grupo para una fase del curso."
    )
    parser.add_argument("--curso", required=True, help="Ruta al descriptor curso.yaml")
    parser.add_argument("--fase", required=True, type=int, help="Número de fase a generar")
    parser.add_argument("--salida", default=None, help="Directorio de salida (por defecto <curso>/tareas)")
    parser.add_argument("--sin-compilar", action="store_true", help="Escribe los .tex sin invocar pdflatex")
    parser.add_argument("--json", action="store_true", help="Emite un único objeto JSON")
    args = parser.parse_args(argv)

    curso = Path(args.curso).resolve()
    try:
        datos = cargar_descriptor(curso)
    except ValueError as exc:
        print(json.dumps({"status": "error", "problemas": [str(exc)]}, ensure_ascii=False), file=sys.stderr)
        return EXIT_DESCRIPTOR

    problemas = validar_tareas(datos, args.fase)
    if problemas:
        print(json.dumps({"status": "invalido", "problemas": problemas}, ensure_ascii=False, indent=2))
        return EXIT_INVALIDO

    salida = Path(args.salida).resolve() if args.salida else curso.parent / "tareas"
    try:
        artefactos, errores = generar(datos, args.fase, salida, not args.sin_compilar)
    except OSError as exc:
        print(json.dumps({"status": "error", "problemas": [str(exc)]}, ensure_ascii=False), file=sys.stderr)
        return EXIT_DISCO

    if errores:
        print(
            json.dumps(
                {"status": "latex_error", "fase": args.fase, "salida": str(salida),
                 "artefactos": artefactos, "errores": errores},
                ensure_ascii=False, indent=2,
            )
        )
        return EXIT_LATEX

    salida_json = {
        "status": "ok",
        "fase": args.fase,
        "salida": str(salida),
        "tex_escritos": len(artefactos),
        "compilados": sum(1 for a in artefactos if a.get("pdf")),
        "artefactos": artefactos,
        "errores": [],
    }
    if args.json:
        print(json.dumps(salida_json, ensure_ascii=False, indent=2))
    else:
        print(f"Fase {args.fase}: {salida_json['tex_escritos']} tareas, {salida_json['compilados']} PDF")
        for artefacto in artefactos:
            print(f"  - {artefacto['job']}: {artefacto.get('pdf') or artefacto['tex']}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
