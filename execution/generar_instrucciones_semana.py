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
    _tabla_columnas,
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


def _ejemplo_de(
    datos: dict[str, Any], numero: int, grupo: int
) -> dict[str, Any] | None:
    """Devuelve el ejemplo de trabajo declarado para ese grupo y semana.

    Args:
        datos: Descriptor del curso.
        numero: Número de semana.
        grupo: Número de grupo.

    Returns:
        El bloque `ejemplo` o `None` si la semana no lo declara.
    """
    semana = _semana(datos, numero)
    for ejemplo in semana.get("ejemplos") or []:
        if int(ejemplo.get("grupo", 0)) == grupo:
            return ejemplo
    return None


def validar_ejemplo(datos: dict[str, Any], numero: int, grupo: int) -> list[str]:
    """Comprueba que el ejemplo del grupo existe y está completo.

    Args:
        datos: Descriptor del curso.
        numero: Número de semana.
        grupo: Número de grupo.

    Returns:
        Lista de problemas; vacía si el ejemplo se puede emitir.
    """
    problemas = validar_semana(datos, numero)
    ejemplo = _ejemplo_de(datos, numero, grupo)
    if ejemplo is None:
        disponibles = sorted(
            int(e.get("grupo", 0)) for e in _semana(datos, numero).get("ejemplos") or []
        )
        problemas.append(
            f"la semana {numero:02d} no declara ejemplo para el grupo {grupo} "
            f"(declarados: {disponibles or 'ninguno'})"
        )
        return problemas
    for clave in ("titulo", "intro", "bloques", "entregable"):
        if not ejemplo.get(clave):
            problemas.append(f"semana {numero:02d}, grupo {grupo}: falta ejemplo.{clave}")
    for bloque in ejemplo.get("bloques") or []:
        if not isinstance(bloque, dict) or not bloque.get("titulo"):
            problemas.append(
                f"semana {numero:02d}, grupo {grupo}: un bloque del ejemplo no tiene título"
            )
        elif not (bloque.get("texto") or bloque.get("comandos")):
            problemas.append(
                f"semana {numero:02d}, grupo {grupo}: el bloque {bloque.get('titulo')!r} está vacío"
            )
    tabla = ejemplo.get("tabla") or {}
    if tabla:
        columnas = tabla.get("columnas") or []
        if not columnas:
            problemas.append(f"semana {numero:02d}, grupo {grupo}: la tabla no tiene columnas")
        anchos = tabla.get("anchos") or []
        if anchos and len(anchos) != len(columnas):
            problemas.append(
                f"semana {numero:02d}, grupo {grupo}: la tabla declara "
                f"{len(anchos)} anchos para {len(columnas)} columnas"
            )
        if anchos and sum(float(a) for a in anchos) + 0.42 * len(columnas) > 16.6:
            problemas.append(
                f"semana {numero:02d}, grupo {grupo}: los anchos de la tabla suman "
                f"{sum(float(a) for a in anchos):.2f} cm y no caben en el margen"
            )
        if len(columnas) > 4 and len(anchos) != len(columnas):
            problemas.append(
                f"semana {numero:02d}, grupo {grupo}: una tabla de {len(columnas)} "
                "columnas necesita 'anchos' (cm) para no salirse del margen"
            )
        for fila in tabla.get("filas") or []:
            if len(fila) != len(columnas):
                problemas.append(
                    f"semana {numero:02d}, grupo {grupo}: una fila de la tabla tiene "
                    f"{len(fila)} celdas y la cabecera {len(columnas)}"
                )
    return problemas


def _tabla_ejemplo(tabla: dict[str, Any]) -> str:
    """Tabla del ejemplo con columnas de ancho fijo y texto justificado.

    Las tablas de siete columnas no caben con celdas `c`: el texto se sale del
    margen. Aquí cada columna recibe su ancho en cm (`anchos` del descriptor) y la
    tabla se compone en `\footnotesize`; la validación exige un ancho por columna.

    Args:
        tabla: Bloque `tabla` del ejemplo.

    Returns:
        LaTeX de la tabla, o cadena vacía si no hay columnas.
    """
    columnas = [_t(str(c)) for c in tabla.get("columnas") or []]
    filas = tabla.get("filas") or []
    if not columnas:
        return ""
    anchos = [float(a) for a in tabla.get("anchos") or []]
    if len(anchos) != len(columnas):
        # 16,0 cm útiles menos los dos \tabcolsep de cada columna.
        ancho = max(1.0, (16.0 - 0.45 * len(columnas)) / max(1, len(columnas)))
        anchos = [ancho for _ in columnas]
    especificacion = "".join(
        r">{\raggedright\arraybackslash}p{" + f"{a:.2f}" + "cm}" for a in anchos
    )
    cuerpo = "\n".join(
        " & ".join(_t(str(c)) for c in fila) + r" \\" for fila in filas
    )
    partes = [
        r"\begin{center}",
        r"\begin{minipage}{\linewidth}",
        r"\centering",
        r"{\footnotesize",
    ]
    if tabla.get("titulo"):
        partes.append(r"\textbf{" + _t(str(tabla["titulo"])) + r"}\par\smallskip")
    partes.extend(
        [
            r"\begin{tabular}{@{}" + especificacion + "@{}}",
            r"\toprule",
            " & ".join(r"\textbf{" + c + "}" for c in columnas) + r" \\",
            r"\midrule",
            cuerpo,
            r"\bottomrule",
            r"\end{tabular}",
            "}",
        ]
    )
    if tabla.get("nota"):
        partes.append(r"\par\smallskip{\footnotesize " + _t(str(tabla["nota"])) + "}")
    partes.extend([r"\end{minipage}", r"\end{center}"])
    return "\n".join(partes)


def _seccion_ejemplo(icono: str, texto: str) -> str:
    """Título de sección que no se queda solo al pie de página.

    Args:
        icono: Nombre del icono FontAwesome.
        texto: Texto del título.

    Returns:
        LaTeX del título, precedido de `\needspace`.
    """
    return "\\needspace{5\\baselineskip}\n" + seccion_con_icono(icono, texto)


def tex_ejemplo_grupo(datos: dict[str, Any], numero: int, grupo: int) -> str:
    """Genera el documento con el ejemplo de trabajo de un grupo en una semana.

    Args:
        datos: Descriptor validado.
        numero: Número de semana.
        grupo: Número de grupo.

    Returns:
        Documento LaTeX completo.
    """
    meta = datos["meta"]
    semana = _semana(datos, numero)
    fase = _fase(datos, int(semana["fase"]))
    entregas = datos.get("entregas") or {}
    roles = {int(n): r for n, r in roles_de_la_semana(datos, numero)}
    rol = roles.get(grupo) or {"nombre": "individual", "descripcion": "", "en_la_practica": []}
    ejemplo = _ejemplo_de(datos, numero, grupo) or {}
    practica = semana["practica"]

    partes: list[str] = [
        banda_titulo(
            _t(f"Semana {numero:02d} --- {ejemplo['titulo']}"),
            _t(f"Grupo {grupo} · rol {rol.get('nombre')} · ejemplo de trabajo"),
        ),
        _metadatos_curso(meta),
        _tabla_datos(
            [
                ("Curso", _t(f"{meta['codigo']} --- {meta['titulo']}")),
                ("Semana", _t(f"{numero:02d} de {meta.get('semanas', '')}")),
                ("Fase", _t(f"{fase['id']} --- {fase['nombre']}")),
                ("Grupo", _t(str(grupo))),
                ("Rol", _t(str(rol.get("nombre", "")))),
                ("Entrega", _t(f"{entregas.get('plataforma', '')}, carpeta semana_{numero:02d}/")),
                ("Corte", _t(str(entregas.get("corte", "")))),
            ]
        ),
        _seccion_ejemplo("user-shield", "Tu rol en la práctica"),
        _t(str(rol.get("descripcion", ""))),
        _lista([str(a) for a in rol.get("en_la_practica") or []]),
        _seccion_ejemplo("flag", "Qué aporta este rol al entregable"),
        _t(str(rol.get("aporta", ""))),
        _seccion_ejemplo("list-ol", "Ejemplo paso a paso"),
        _t(str(ejemplo["intro"])),
    ]

    for bloque in ejemplo.get("bloques") or []:
        partes.append("\\subsection{" + _t(str(bloque["titulo"])) + "}")
        if bloque.get("texto"):
            partes.append(_t(str(bloque["texto"])))
        if bloque.get("comandos"):
            partes.append(
                "\\begin{lstlisting}[style=estiloCodigo]\n"
                + str(bloque["comandos"]).strip("\n")
                + "\n\\end{lstlisting}"
            )

    tabla = ejemplo.get("tabla") or {}
    if tabla:
        partes.append(
            "\\needspace{8\\baselineskip}"
            "\\subsection{" + _t(str(tabla.get("titulo", "Tabla de ejemplo"))) + "}"
        )
        partes.append(_tabla_ejemplo(tabla))

    partes.append(_seccion_ejemplo("box-open", "Qué guardar en el repositorio"))
    partes.append(_t(str(ejemplo["entregable"])))
    if ejemplo.get("estructura"):
        partes.append(
            "\\begin{lstlisting}[style=estiloCodigo]\n"
            + str(ejemplo["estructura"]).strip("\n")
            + "\n\\end{lstlisting}"
        )
    if ejemplo.get("comprobaciones"):
        partes.append(_lista([str(c) for c in ejemplo["comprobaciones"]]))

    partes.append(_seccion_ejemplo("ruler-combined", "Cómo se corrige"))
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

    if ejemplo.get("avisos"):
        partes.append(_lista([str(a) for a in ejemplo["avisos"]]))

    partes.append(
        "\\begin{cajaRecuerda}El trabajo es independiente: cada grupo usa su propio "
        "repositorio y su propio laboratorio, y la comparación de resultados es en clase. "
        "Corte: "
        + _t(str(entregas.get("corte", "")).rstrip("."))
        + "."
        "\n\\end{cajaRecuerda}"
    )

    return _documento(meta, _t(f"Semana {numero:02d}"), "\n\n".join(partes))


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
                "Todos los grupos resuelven la misma práctica, cada uno en su propio "
                "repositorio y su propio laboratorio: el trabajo de un grupo no depende "
                "del de otro. El rol cambia el énfasis del trabajo y lo que cada grupo "
                "aporta al comparar resultados en clase, al final."
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
    datos: dict[str, Any],
    numero: int,
    salida: Path,
    compilar: bool,
    grupo: int | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Escribe y compila las instrucciones de la semana (o el ejemplo de un grupo).

    Args:
        datos: Descriptor validado.
        numero: Número de semana.
        salida: Directorio `docs/` del curso.
        compilar: Si es False, escribe solo el `.tex`.
        grupo: Si se indica, emite el ejemplo de trabajo de ese grupo en vez del
            documento de la semana.

    Returns:
        Tupla `(ruta_tex, artefacto)`.
    """
    meta = datos["meta"]
    codigo = _slug(meta["codigo"])
    salida.mkdir(parents=True, exist_ok=True)
    job = f"grupo_{grupo}_{numero:02d}" if grupo else f"semana_{numero:02d}"
    build = RAIZ / ".tmp" / "latex_build" / job
    build.mkdir(parents=True, exist_ok=True)
    os.environ[FUENTE_FECHA] = str(_epoch(meta))

    tex = salida / f"{job}.tex"
    contenido = (
        tex_ejemplo_grupo(datos, numero, grupo) if grupo else tex_semana(datos, numero)
    )
    tex.write_text(contenido, encoding="utf-8")
    artefacto: dict[str, Any] = {"job": job, "tex": str(tex), "pdf": None, "errores": [], "overfull": 0}
    if compilar:
        artefacto.update(_compilar(contenido, job, build, tex))
    return tex, artefacto


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada del generador."""
    parser = argparse.ArgumentParser(
        description="Genera las instrucciones paso a paso de una semana del curso."
    )
    parser.add_argument("--curso", required=True, help="Ruta al descriptor curso.yaml")
    parser.add_argument("--semana", required=True, type=int, help="Número de semana")
    parser.add_argument(
        "--grupo",
        type=int,
        default=None,
        help="Emite el ejemplo de trabajo de ese grupo (docs/grupo_N_NN.tex) en vez de la semana",
    )
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

    problemas = (
        validar_ejemplo(datos, args.semana, args.grupo)
        if args.grupo
        else validar_semana(datos, args.semana)
    )
    if problemas:
        print(json.dumps({"status": "invalido", "problemas": problemas}, ensure_ascii=False, indent=2))
        return EXIT_INVALIDO

    salida = Path(args.salida).resolve() if args.salida else curso.parent / "docs"
    try:
        _, artefacto = generar(
            datos, args.semana, salida, not args.sin_compilar, grupo=args.grupo
        )
    except OSError as exc:
        print(json.dumps({"status": "error", "problemas": [str(exc)]}, ensure_ascii=False), file=sys.stderr)
        return EXIT_DISCO

    salida_json = {
        "status": "ok",
        "semana": args.semana,
        "grupo": args.grupo,
        "tex": artefacto["tex"],
        "pdf": artefacto["pdf"],
        "errores": artefacto["errores"],
        "overfull": artefacto["overfull"],
    }
    print(json.dumps(salida_json, ensure_ascii=False, indent=2))
    return EXIT_LATEX if artefacto["errores"] else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
