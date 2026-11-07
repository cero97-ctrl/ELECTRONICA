#!/usr/bin/env python3
"""
generar_instrucciones_semana.py — Instrucciones paso a paso de una semana (Layer 3)

Emite el documento que se entrega a todo el curso al inicio de una semana: qué
hacer antes de la sesión, el objetivo, los contenidos, el procedimiento paso a
paso, el rol de cada grupo, qué se entrega, cómo se corrige y una lista de
verificación antes del corte.

Uso:
    python3 execution/generar_instrucciones_semana.py --curso cursos/CYBERSEGURIDAD/curso.yaml --semana 1
    python3 execution/generar_instrucciones_semana.py --curso <yaml> --semana 2 --sin-compilar
    python3 execution/generar_instrucciones_semana.py --curso <yaml> --semana 1 --json

Salida (stdout, JSON):
    {"status": "ok", "semana": 1, "tex": "...", "pdf": "...", "errores": []}

Códigos de salida:
    0 — instrucciones generadas y verificadas
    1 — argumentos de línea de comandos inválidos
    2 — descriptor ilegible o que no es YAML
    3 — descriptor o semana inválidos (semana inexistente o práctica incompleta)
    4 — error de compilación LaTeX (se conserva el .log)
    5 — error de escritura en disco

Por qué existe: el enunciado de la práctica dice QUÉ se evalúa; las instrucciones
de la semana dicen QUÉ HACER HOY, en orden, con el rol de cada grupo y el corte.
Son dos documentos con dos lectores distintos (docente y estudiante) y deben salir
del mismo descriptor para no contradecirse.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
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
    _n,
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

INSTRUMENTO = {
    "formativa": "Actividad formativa",
    "control_fase_1": "Control de fase 1",
    "control_fase_2": "Control de fase 2",
    "control_fase_3": "Control de fase 3",
    "final": "Evaluación final",
}


def _instrumento(valor: Any) -> str:
    """Nombre legible del instrumento de evaluación de la semana."""
    clave = str(valor)
    return INSTRUMENTO.get(clave, clave.replace("_", " "))


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


def _semana(datos: dict[str, Any], numero: int) -> dict[str, Any]:
    """Devuelve el bloque de la semana pedida.

    Args:
        datos: Descriptor del curso.
        numero: Número de semana.

    Returns:
        Bloque de la semana.

    Raises:
        ValueError: si la semana no existe.
    """
    for semana in datos.get("semanas") or []:
        if int(semana.get("numero", 0)) == numero:
            return semana
    raise ValueError(f"la semana {numero} no existe en el descriptor")


def _fase(datos: dict[str, Any], numero: int) -> dict[str, Any]:
    """Devuelve el bloque de la fase pedida."""
    for fase in datos.get("fases") or []:
        if int(fase.get("id", 0)) == numero:
            return fase
    raise ValueError(f"la fase {numero} no existe en el descriptor")


def roles_de_la_semana(datos: dict[str, Any], numero: int) -> list[tuple[int, dict[str, Any]]]:
    """Rol de cada grupo durante la semana, según su fase y la rotación.

    Args:
        datos: Descriptor del curso.
        numero: Número de semana.

    Returns:
        Lista de tuplas `(numero_de_grupo, rol)`; vacía si la semana no tiene roles.
    """
    semana = _semana(datos, numero)
    grupos = datos.get("grupos") or {}
    if int(semana["fase"]) not in [int(f) for f in grupos.get("fase_con_roles") or []]:
        return []
    roles = {r["nombre"]: r for r in grupos.get("roles") or []}
    inicial = grupos.get("asignacion_inicial") or []
    if not inicial:
        return []
    turno = (int(semana["fase"]) - 1) % len(inicial)
    return [(i + 1, roles[inicial[(i + turno) % len(inicial)]]) for i in range(len(inicial))]


def validar_semana(datos: dict[str, Any], numero: int) -> list[str]:
    """Comprueba que la semana tiene todo lo que el documento afirma.

    Args:
        datos: Descriptor del curso.
        numero: Número de semana.

    Returns:
        Lista de problemas; vacía si la semana es emitible.
    """
    problemas: list[str] = []
    meta = datos.get("meta") or {}
    for clave in ("codigo", "titulo", "autor", "fecha", "fecha_iso"):
        if not meta.get(clave):
            problemas.append(f"meta.{clave} es obligatorio para emitir la semana")

    try:
        semana = _semana(datos, numero)
        _fase(datos, int(semana["fase"]))
    except ValueError as exc:
        return problemas + [str(exc)]

    for clave in ("titulo", "objetivo", "contenidos", "herramientas"):
        if not semana.get(clave):
            problemas.append(f"semana {numero}: falta {clave}")
    practica = semana.get("practica") or {}
    for clave in ("titulo", "escenario", "pasos", "entregable", "criterios"):
        if not practica.get(clave):
            problemas.append(f"semana {numero}: falta practica.{clave}")
    if practica.get("criterios"):
        total = sum(float(c.get("peso", 0)) for c in practica["criterios"])
        if abs(total - 10.0) > 0.01:
            problemas.append(f"semana {numero}: los criterios suman {total}, no 10")

    entregas = datos.get("entregas") or {}
    for clave in ("plataforma", "corte", "estructura", "reglas"):
        if not entregas.get(clave):
            problemas.append(f"entregas.{clave} es obligatorio para explicar la entrega")
    for clave in ("estructura", "reglas"):
        for item in entregas.get(clave) or []:
            if not isinstance(item, str):
                problemas.append(
                    f"entregas.{clave} contiene un ítem que no es texto ({item!r}); "
                    "falta entrecomillar el valor que lleva ':'"
                )
    catalogo: dict[str, str] = {}
    for entrada in datos.get("glosario") or []:
        if not isinstance(entrada, dict):
            problemas.append(f"glosario: una entrada no es un mapa ({entrada!r})")
            continue
        termino = str(entrada.get("termino", "")).strip()
        definicion = str(entrada.get("definicion", "")).strip()
        if not termino or not definicion:
            problemas.append(f"glosario: entrada incompleta ({entrada!r})")
            continue
        if termino in catalogo:
            problemas.append(f"glosario: el término {termino!r} está repetido")
        catalogo[termino] = definicion

    for semana in datos.get("semanas") or []:
        elegidos = semana.get("glosario") or []
        if not isinstance(elegidos, list):
            problemas.append(
                f"semana {semana.get('numero')}: glosario debe ser una lista de términos"
            )
            elegidos = []
        for termino in elegidos:
            if not isinstance(termino, str):
                problemas.append(
                    f"semana {semana.get('numero')}: término de glosario no textual ({termino!r})"
                )
            elif termino not in catalogo:
                problemas.append(
                    f"semana {semana.get('numero')}: el término {termino!r} no está en el glosario del curso"
                )
        for contenido in semana.get("contenidos") or []:
            if not isinstance(contenido, str):
                problemas.append(
                    f"semana {semana.get('numero')}: un contenido no es texto ({contenido!r})"
                )
    return problemas


def _glosario(datos: dict[str, Any], semana: dict[str, Any]) -> list[tuple[str, str]]:
    """Resuelve los términos que la semana declara contra el glosario del curso.

    Args:
        datos: Descriptor del curso.
        semana: Bloque de la semana.

    Returns:
        Lista de pares (término, definición), en el orden declarado por la semana.
        Vacía si la semana no declara glosario.
    """
    catalogo = {
        str(entrada.get("termino", "")).strip(): str(entrada.get("definicion", "")).strip()
        for entrada in datos.get("glosario") or []
        if isinstance(entrada, dict)
    }
    return [
        (nombre, catalogo[nombre])
        for nombre in semana.get("glosario") or []
        if nombre in catalogo
    ]


def _antes_de_la_sesion(datos: dict[str, Any], semana: dict[str, Any]) -> list[str]:
    """Tareas previas: semana 1 crea el repositorio; el resto lo mantiene."""
    numero = int(semana["numero"])
    codigo = str((datos.get("meta") or {}).get("codigo", "curso")).lower()
    if numero == 1:
        return [
            f"Crear el repositorio privado del grupo en GitHub, con nombre {codigo}-grupo-<n>.",
            "Añadir al docente como colaborador con permiso de lectura.",
            "Escribir README.md con los integrantes, el rol de cada uno y la tabla de semanas.",
            "Instalar Docker y nmap en el equipo, y comprobar que ambos responden al pedir la versión.",
            "Clonar el repositorio y crear la carpeta semana_01 con scripts y evidencia.",
            "Verificar que docker compose up -d levanta los tres contenedores del laboratorio.",
        ]
    return [
        f"Comprobar que el repositorio del grupo tiene la carpeta semana_{numero:02d} creada.",
        "Revisar la retroalimentación del docente sobre la semana anterior y corregir lo pendiente.",
        f"Traer instaladas las herramientas de la semana: {', '.join(str(h) for h in semana.get('herramientas') or [])}.",
        "Confirmar que el laboratorio arranca y que los tres servicios responden antes de la sesión.",
        "Leer el objetivo y los contenidos para llegar con el vocabulario de la práctica.",
    ]


def tex_semana(datos: dict[str, Any], numero: int) -> str:
    """Genera el documento de instrucciones de una semana.

    Args:
        datos: Descriptor validado.
        numero: Número de semana.

    Returns:
        Documento LaTeX completo.
    """
    meta = datos["meta"]
    semana = _semana(datos, numero)
    fase = _fase(datos, int(semana["fase"]))
    practica = semana["practica"]
    entregas = datos.get("entregas") or {}
    grupos = datos.get("grupos") or {}
    asignados = roles_de_la_semana(datos, numero)

    partes: list[str] = [
        banda_titulo(
            _t(f"Semana {numero:02d} --- {semana['titulo']}"),
            _t(f"Fase {fase['id']}: {fase['nombre']} --- instrucciones paso a paso"),
        ),
        _metadatos_curso(meta),
        _tabla_datos(
            [
                ("Curso", _t(f"{meta['codigo']} --- {meta['titulo']}")),
                ("Semana", _t(f"{numero:02d} de {meta.get('semanas', '')}")),
                ("Fase", _t(f"{fase['id']} --- {fase['nombre']}")),
                ("Modalidad", _t(f"{grupos.get('cantidad', 0)} grupos, trabajo desde sus propios equipos")),
                ("Dedicación", _t(str(meta.get("dedicacion_semanal", "")))),
                ("Instrumento", _t(_instrumento(semana.get("evaluacion", "")))),
                (
                    "Entrega",
                    _t(f"{entregas.get('plataforma', '')}, carpeta semana_{numero:02d}/"),
                ),
                ("Corte", _t(str(entregas.get("corte", "")))),
            ]
        ),
        seccion_con_icono("clock", "Antes de la sesión"),
        _t(
            "Estas tareas se hacen en casa, antes de la práctica. Si el repositorio o el "
            "laboratorio no están listos al empezar, la sesión se va en arreglarlos y no "
            "alcanza para el informe."
        ),
        _lista(_antes_de_la_sesion(datos, semana), entorno="enumerate"),
        seccion_con_icono("bullseye", "Objetivo de la semana"),
        _t(semana["objetivo"]),
        seccion_con_icono("clipboard-list", "Contenidos que se aplican"),
        _lista([str(c) for c in semana["contenidos"]]),
        seccion_con_icono("flask", "Escenario"),
        _t(practica["escenario"]),
        seccion_con_icono("list-ol", "Paso a paso de la práctica"),
        _lista([str(p) for p in practica["pasos"]], entorno="enumerate"),
        "\\begin{cajaConcepto}"
        + r"\textbf{Regla de oro de la evidencia:} guarda la salida de cada paso en "
        + f"\\texttt{{semana\\_{numero:02d}/evidencia/}} "
        + r"en el momento en que la obtienes. Reconstruirla después no es evidencia, es memoria."
        + "\n\\end{cajaConcepto}",
        "\\textbf{Herramientas de la semana:} "
        + ", ".join(_t(str(h)) for h in semana["herramientas"])
        + ".",
    ]

    if asignados:
        partes.append(seccion_con_icono("users", "Rol de cada grupo esta semana"))
        partes.append(
            _t(
                "Todos los grupos resuelven la misma práctica. El rol cambia el énfasis del "
                "trabajo y lo que cada grupo aporta al comparar resultados en clase."
            )
        )
        partes.append(
            "\\begin{tabularx}{\\linewidth}{@{}l l X@{}}\n\\toprule\n"
            "Grupo & Rol & Aporte principal\\\\\n\\midrule\n"
            + "\n".join(
                _t(f"Grupo {grupo}")
                + " & \\textbf{"
                + _t(rol["nombre"])
                + "} & "
                + _t(
                    str(rol.get("aporta", "")).replace(
                        "semana_NN", f"semana_{numero:02d}"
                    )
                )
                + r" \\"
                for grupo, rol in asignados
            )
            + "\n\\bottomrule\n\\end{tabularx}"
        )
    else:
        partes.append(seccion_con_icono("user", "Trabajo individual"))
        partes.append(
            _t(
                "Esta semana no hay roles de grupo: la actividad es individual y cada "
                "estudiante entrega su propio trabajo."
            )
        )

    partes.append(seccion_con_icono("box-open", "Qué se entrega"))
    partes.append(_t(practica["entregable"]))
    partes.append(r"\textbf{Estructura de la carpeta} \texttt{semana\_" + f"{numero:02d}" + r"/}\textbf{:}")
    partes.append(
        _lista(
            [
                str(e).replace("semana_NN", f"semana_{numero:02d}")
                for e in entregas.get("estructura") or []
            ]
        )
    )
    partes.append(r"\textbf{Reglas que se verifican al corregir:}")
    partes.append(_lista([str(r) for r in entregas.get("reglas") or []]))

    partes.append(seccion_con_icono("ruler-combined", "Cómo se corrige"))
    partes.append(
        "\\begin{tabularx}{\\linewidth}{@{}X r@{}}\n\\toprule\n"
        "Criterio & Peso\\\\\n\\midrule\n"
        + "\n".join(
            _t(c["criterio"]) + " & " + _n(c["peso"]) + r" \\"
            for c in practica["criterios"]
        )
        + "\n\\midrule\n\\textbf{Total} & \\textbf{"
        + _n(sum(float(c["peso"]) for c in practica["criterios"]))
        + "}\\\\\n\\bottomrule\n\\end{tabularx}"
    )

    partes.append(seccion_con_icono("clipboard-check", "Lista de verificación antes del corte"))
    partes.append(
        _lista(
            [
                f"El repositorio del grupo existe, es privado y el docente aparece como colaborador.",
                f"La carpeta semana_{numero:02d}/ está en el repositorio, no solo en el equipo.",
                "El informe explica qué se hizo, con qué comandos y qué se obtuvo.",
                "La evidencia está anonimizada: sin datos personales, credenciales ni secretos.",
                "Cada hallazgo tiene su hash o su salida cruda que permite reproducirlo.",
                f"El commit 'semana {numero:02d}: <entregable>' está hecho antes del corte.",
            ]
        )
    )

    bloque_glosario: list[str] = []
    glosario = _glosario(datos, semana)
    if glosario:
        bloque_glosario.append("\\clearpage")
        bloque_glosario.append(seccion_con_icono("book", "Glosario de la semana"))
        bloque_glosario.append(
            "\\small\n"
            "\\begin{longtable}{@{}>{\\raggedright\\arraybackslash}p{4.2cm}"
            ">{\\raggedright\\arraybackslash}p{\\dimexpr\\linewidth-4.2cm-12pt\\relax}@{}}\n"
            "\\toprule\n\\textbf{Término} & \\textbf{Definición}\\\\\n"
            "\\midrule\n\\endhead\n\\bottomrule\n\\endlastfoot\n"
            + "\n".join(f"\\textbf{{{_t(t)}}} & {_t(d)}\\\\" for t, d in glosario)
            + "\n\\end{longtable}"
        )

    partes.append(
        "\\begin{tcolorbox}[cajaMejora]\\textbf{Alcance y autorización:} solo se trabaja sobre "
        "los contenedores del laboratorio o sobre sistemas con autorización escrita. Si el "
        "objetivo no está en ese conjunto, se detiene la práctica y se consulta al docente. "
        "El uso de estas técnicas fuera del alcance tiene consecuencias académicas y legales."
        "\n\\end{tcolorbox}"
    )
    partes.append(
        "\\begin{cajaRecuerda}Dudas de la semana: se responden en clase o en el repositorio. "
        "Corte: "
        + _t(str(entregas.get("corte", "")).rstrip("."))
        + "."
        "\n\\end{cajaRecuerda}"
    )
    partes.extend(bloque_glosario)

    return _documento(meta, _t(f"Semana {numero:02d}"), "\n\n".join(partes))


def generar(
    datos: dict[str, Any], numero: int, salida: Path, compilar: bool
) -> tuple[Path, dict[str, Any]]:
    """Escribe y compila las instrucciones de la semana.

    Args:
        datos: Descriptor validado.
        numero: Número de semana.
        salida: Directorio `docs/` del curso.
        compilar: Si es False, escribe solo el `.tex`.

    Returns:
        Tupla `(ruta_tex, artefacto)`.
    """
    meta = datos["meta"]
    codigo = _slug(meta["codigo"])
    salida.mkdir(parents=True, exist_ok=True)
    build = RAIZ / ".tmp" / "latex_build" / f"semana_{codigo}_{numero:02d}"
    build.mkdir(parents=True, exist_ok=True)
    os.environ[FUENTE_FECHA] = str(_epoch(meta))

    tex = salida / f"semana_{numero:02d}.tex"
    tex.write_text(tex_semana(datos, numero), encoding="utf-8")
    artefacto: dict[str, Any] = {"job": f"semana_{numero:02d}", "tex": str(tex), "pdf": None, "errores": [], "overfull": 0}
    if compilar:
        artefacto.update(_compilar(tex.read_text(encoding="utf-8"), f"semana_{numero:02d}", build, tex))
    return tex, artefacto


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada del generador."""
    parser = argparse.ArgumentParser(
        description="Genera las instrucciones paso a paso de una semana del curso."
    )
    parser.add_argument("--curso", required=True, help="Ruta al descriptor curso.yaml")
    parser.add_argument("--semana", required=True, type=int, help="Número de semana")
    parser.add_argument("--salida", default=None, help="Directorio de salida (por defecto <curso>/docs)")
    parser.add_argument("--sin-compilar", action="store_true", help="Escribe el .tex sin invocar pdflatex")
    parser.add_argument("--json", action="store_true", help="Emite un único objeto JSON")
    args = parser.parse_args(argv)

    curso = Path(args.curso).resolve()
    try:
        datos = cargar_descriptor(curso)
    except ValueError as exc:
        print(json.dumps({"status": "error", "problemas": [str(exc)]}, ensure_ascii=False), file=sys.stderr)
        return EXIT_DESCRIPTOR

    problemas = validar_semana(datos, args.semana)
    if problemas:
        print(json.dumps({"status": "invalido", "problemas": problemas}, ensure_ascii=False, indent=2))
        return EXIT_INVALIDO

    salida = Path(args.salida).resolve() if args.salida else curso.parent / "docs"
    try:
        _, artefacto = generar(datos, args.semana, salida, not args.sin_compilar)
    except OSError as exc:
        print(json.dumps({"status": "error", "problemas": [str(exc)]}, ensure_ascii=False), file=sys.stderr)
        return EXIT_DISCO

    salida_json = {
        "status": "ok",
        "semana": args.semana,
        "tex": artefacto["tex"],
        "pdf": artefacto["pdf"],
        "errores": artefacto["errores"],
        "overfull": artefacto["overfull"],
    }
    print(json.dumps(salida_json, ensure_ascii=False, indent=2))
    return EXIT_LATEX if artefacto["errores"] else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
