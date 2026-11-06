#!/usr/bin/env python3
"""
generar_material_curso.py — Genera el material completo de un curso (Layer 3: Execution)

Lee un descriptor YAML (fuente única de verdad) y emite, de forma determinista,
el sílabo, el plan semanal, la guía del estudiante, una práctica por semana, los
controles de fase, la evaluación final, la rúbrica de prácticas, el laboratorio
Docker y el README del curso. Todo el LaTeX usa el estilo infográfico del
workspace (`execution/estilo_infografia.py`).

Uso:
    python3 execution/generar_material_curso.py --curso cursos/CYBERSEGURIDAD/curso.yaml
    python3 execution/generar_material_curso.py --curso <yaml> --solo silabo,guia --sin-compilar
    python3 execution/generar_material_curso.py --curso <yaml> --json

Salida (stdout, JSON):
    {"status": "ok", "curso": "...", "artefactos": [...], "compilados": N, "errores": []}

Códigos de salida:
    0 — material generado y verificado
    1 — argumentos de línea de comandos inválidos
    2 — descriptor ilegible o que no es YAML
    3 — descriptor inválido (semana faltante, pesos que no suman, etc.)
    4 — error de compilación LaTeX (se conserva el .log y se informa la línea)
    5 — error de escritura en disco

Por qué existe: el material de un curso son decenas de documentos que deben
contar la misma historia. Escritos a mano divergen en la semana tres; generados
desde un descriptor, la coherencia es una propiedad del programa, no disciplina
del autor.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
RAIZ = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(RAIZ))

from compile_latex import compile_latex_code  # noqa: E402
from estilo_infografia import (  # noqa: E402
    PREAMBULO_INFOGRAFIA,
    banda_titulo,
    seccion_con_icono,
)

NOTA_MAXIMA = 10.0
PESO_TOTAL_CURSO = 100.0
ARTEFACTOS = (
    "silabo",
    "plan_semanal",
    "guia",
    "practicas",
    "controles",
    "final",
    "rubrica",
    "laboratorio",
    "readme",
)

# Fichero con el que se fija /CreationDate y /ID del PDF: sin esto, dos
# ejecuciones del mismo descriptor producen PDFs distintos byte a byte y el
# material deja de ser reproducible.
FUENTE_FECHA = "SOURCE_DATE_EPOCH"


def etiqueta_semana(sem: dict[str, Any]) -> str:
    """Nombre del documento semanal: ``Taller`` para teoría, ``Práctica`` si no.

    Un curso puede dedicar las primeras semanas a teoría de errores y análisis
    gráfico antes de entrar al laboratorio. Llamar «Práctica 01» a un taller de
    teoría es una etiqueta falsa: el alumno cree que va a medir y no mide.
    """
    return "Taller" if str(sem.get("tipo", "practica")).lower() == "teoria" else "Práctica"


# ── Escape a LaTeX ────────────────────────────────────────────────────────────

# Variante para los campos que admiten matemática en línea ($...$): no se tocan la
# barra invertida, el dólar, el subíndice, el superíndice ni las llaves, porque son
# parte de la notación. Se escapa solo lo que rompería el documento aun dentro de
# matemática (&, #, % ~ < >), con lookbehind para no duplicar un escape ya escrito:
# un `\%` del docente se queda en `\%` y no se convierte en `\\%`, que en LaTeX es
# salto de línea más comentario y desbalancea el modo matemático (el error aparece
# como "Command \item invalid in math mode" tres líneas más abajo).
_ESCAPE_MATH = [
    (re.compile(r"(?<!\\)&"), r"\\&"),
    (re.compile(r"(?<!\\)#"), r"\\#"),
    (re.compile(r"(?<!\\)%"), r"\\%"),
    (re.compile(r"~"), r"\textasciitilde{}"),
    (re.compile(r"<"), r"\textless{}"),
    (re.compile(r">"), r"\textgreater{}"),
]

_ESCAPE = [
    ("\\", r"\textbackslash{}"),
    ("&", r"\&"),
    ("%", r"\%"),
    ("$", r"\$"),
    ("#", r"\#"),
    ("_", r"\_"),
    ("{", r"\{"),
    ("}", r"\}"),
    ("~", r"\textasciitilde{}"),
    ("^", r"\textasciicircum{}"),
    ("<", r"\textless{}"),
    (">", r"\textgreater{}"),
]

# Se aplican DESPUÉS del escape: sus reemplazos son LaTeX legítimo y no deben
# volver a escaparse.
_UNICODE = [
    ("—", "---"),
    ("–", "--"),
    ("“", "``"),
    ("”", "''"),
    ("‘", "`"),
    ("’", "'"),
    ("•", r"\textbullet{}"),
    ("…", r"\ldots{}"),
    ("→", r"$\rightarrow$"),
    ("←", r"$\leftarrow$"),
    ("·", r"$\cdot$"),
    ("≥", r"$\geq$"),
    ("≤", r"$\leq$"),
    ("×", r"$\times$"),
    ("±", r"$\pm$"),
    ("°", r"$^{\circ}$"),
    ("Ω", r"$\Omega$"),
    ("μ", r"$\mu$"),
    ("µ", r"$\mu$"),
    ("τ", r"$\tau$"),
    ("θ", r"$\theta$"),
    ("φ", r"$\varphi$"),
    ("ω", r"$\omega$"),
    ("α", r"$\alpha$"),
    ("β", r"$\beta$"),
    ("π", r"$\pi$"),
    ("λ", r"$\lambda$"),
    ("Δ", r"$\Delta$"),
    ("≈", r"$\approx$"),
    ("≠", r"$\neq$"),
    ("∞", r"$\infty$"),
]


def _t(texto: Any) -> str:
    """Convierte texto plano del descriptor en texto seguro para pdflatex.

    Args:
        texto: Valor del descriptor; se convierte a str si no lo es.

    Returns:
        Cadena escapada, lista para interpolar en el documento.
    """
    if texto is None:
        return ""
    s = str(texto)
    for crudo, escapado in _ESCAPE:
        s = s.replace(crudo, escapado)
    for crudo, latex in _UNICODE:
        s = s.replace(crudo, latex)
    return s


def _tm(texto: Any) -> str:
    """Como `_t`, pero conserva la matemática en línea escrita por el docente.

    Los campos de prosa de una práctica (escenario, pasos, análisis, entregable)
    necesitan nombrar magnitudes, y en texto plano un subíndice no se puede
    escribir: `_t` convierte `$V_C$` en dólares literales. Aquí se dejan intactos
    `$`, `\\`, `_`, `^` y las llaves, y se escapa solo lo que rompería el
    documento aun dentro de matemática (`&`, `#`, `%`).

    La contrapartida es que un subíndice fuera de `$...$` sí rompe la compilación;
    `_validar_matematica` lo detecta antes de compilar y lo reporta con el campo.

    Args:
        texto: Valor del descriptor; se convierte a str si no lo es.

    Returns:
        Cadena lista para interpolar, con la matemática en línea preservada.
    """
    if texto is None:
        return ""
    s = str(texto)
    for patron, escapado in _ESCAPE_MATH:
        s = re.sub(patron, escapado, s)
    for crudo, latex in _UNICODE:
        s = s.replace(crudo, latex)
    return s


def _validar_matematica(texto: Any, donde: str) -> list[str]:
    """Verifica que la matemática en línea de un campo de prosa esté bien formada.

    Reglas, todas comprobables sin compilar: número par de `$`, llaves
    balanceadas, y `_`, `^` o `\\` solo dentro de un segmento matemático. Un
    subíndice suelto en modo texto es el error más caro de este tipo porque solo
    aparece tras una compilación completa.

    Args:
        texto: Valor del descriptor.
        donde: Ruta legible del campo, para el mensaje de error.

    Returns:
        Lista de problemas encontrados (vacía si el campo es válido).
    """
    problemas: list[str] = []
    if texto is None:
        return problemas
    s = str(texto)
    if s.count("$") % 2:
        problemas.append(f"{donde}: número impar de '$'; la matemática en línea debe abrirse y cerrarse")
        return problemas
    segmentos = s.split("$")
    for i, seg in enumerate(segmentos):
        en_mate = i % 2 == 1
        if seg.count("{") != seg.count("}"):
            problemas.append(f"{donde}: llaves desbalanceadas en «{seg[:40]}»")
        if not en_mate and re.search(r"[_^]", seg):
            problemas.append(
                f"{donde}: '_' o '^' fuera de $...$ en «{seg[:40]}»; escribe la magnitud como $V_C$"
            )
    return problemas


def _n(valor: float) -> str:
    """Formatea un número con coma decimal y un decimal fijo (3,0)."""
    return f"{float(valor):.1f}".replace(".", ",")


def _slug(texto: str) -> str:
    """Normaliza un texto a un identificador ASCII apto para nombres de job."""
    limpio = re.sub(r"[^a-z0-9]+", "_", str(texto).lower())
    return limpio.strip("_") or "documento"


# ── Carga y validación del descriptor ─────────────────────────────────────────


def cargar_descriptor(ruta: Path) -> dict[str, Any]:
    """Lee el descriptor YAML del curso.

    Args:
        ruta: Ruta al fichero `curso.yaml`.

    Returns:
        Diccionario con el descriptor.

    Raises:
        FileNotFoundError: Si la ruta no existe.
        ValueError: Si el fichero no es YAML o no es un mapa.
    """
    if not ruta.exists():
        raise FileNotFoundError(f"Descriptor no encontrado: {ruta}")
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Descriptor ilegible como YAML ({ruta}): {exc}") from exc
    if not isinstance(datos, dict):
        raise ValueError(f"El descriptor debe ser un mapa YAML, no {type(datos).__name__}")
    return datos


_ASCII_SEGURO = set("áéíóúüñÁÉÍÓÚÜÑ")


def _unicode_crudo(texto: Any, etiqueta: str) -> list[str]:
    """Avisa de caracteres que rompen pdflatex dentro de LaTeX crudo.

    Las celdas de tabla y los campos ``*_tex`` NO pasan por ``_t()``, así que un
    ``Ω`` o un ``·`` escritos tal cual llegan a pdflatex y rompen la compilación
    con "Unicode character ... not set up for use with LaTeX". Los acentos del
    español sí los resuelve ``inputenc``; el resto debe escribirse como macro.

    También caza el ``%`` sin escapar, que en una celda convierte el resto de la
    fila en comentario (se come el ``\\\\`` y el error aparece dos filas más abajo
    como ``Misplaced \\noalign``). Detectar ambas cosas aquí cuesta milisegundos y
    evita un ciclo completo de compilación.
    """
    crudo = str(texto)
    mapa = dict(_UNICODE)
    vistos = dict.fromkeys(
        ch for ch in crudo if ord(ch) > 127 and ch not in _ASCII_SEGURO
    )
    problemas: list[str] = []
    for ch in vistos:
        sugerencia = mapa.get(ch)
        problemas.append(
            f"{etiqueta}: el carácter {ch!r} (U+{ord(ch):04X}) está en LaTeX crudo y "
            "pdflatex no lo compone; "
            + (f"escribir {sugerencia}" if sugerencia else "usar su macro LaTeX")
        )
    if re.search(r"(?<!\\)%", crudo):
        problemas.append(
            f"{etiqueta}: hay un '%' sin escapar en LaTeX crudo; en TeX comenta el "
            "resto de la línea y en una tabla se come el separador de fila. "
            r"Escribir '\%'"
        )
    return problemas


def _validar_tabla(tabla: Any, etiqueta: str) -> list[str]:
    """Comprueba que una tabla del descriptor tenga cabecera y filas coherentes."""
    if tabla in (None, {}):
        return []
    if not isinstance(tabla, dict):
        return [f"{etiqueta}: 'tabla' debe ser un mapa con columnas y filas"]
    columnas = tabla.get("columnas") or []
    filas = tabla.get("filas") or []
    if not columnas:
        return [f"{etiqueta}: la tabla no declara 'columnas'"]
    if not filas:
        return [f"{etiqueta}: la tabla no declara 'filas'"]
    problemas: list[str] = []
    for columna in columnas:
        problemas.extend(_unicode_crudo(columna, f"{etiqueta}: cabecera"))
    for indice, fila in enumerate(filas, start=1):
        if not isinstance(fila, list) or len(fila) != len(columnas):
            problemas.append(
                f"{etiqueta}: la fila {indice} tiene {len(fila) if isinstance(fila, list) else '?'} "
                f"celdas y la cabecera tiene {len(columnas)}"
            )
        if isinstance(fila, list):
            for celda in fila:
                problemas.extend(_unicode_crudo(celda, f"{etiqueta}: fila {indice}"))
    return problemas


def validar(datos: dict[str, Any]) -> list[str]:
    """Comprueba la coherencia interna del descriptor.

    Valida lo que un revisor humano no ve: que las semanas sean contiguas, que
    las fases cubran el calendario sin huecos ni solapes, que los pesos sumen y
    que no haya dos servicios en el mismo puerto.

    Args:
        datos: Descriptor cargado.

    Returns:
        Lista de problemas encontrados; vacía si el descriptor es válido.
    """
    problemas: list[str] = []
    meta = datos.get("meta") or {}
    for clave in ("codigo", "titulo", "subtitulo", "autor", "fecha", "fecha_iso", "semanas"):
        if not meta.get(clave):
            problemas.append(f"meta.{clave} es obligatorio y está vacío")
    if problemas:
        return problemas

    try:
        total_semanas = int(meta["semanas"])
        date.fromisoformat(str(meta["fecha_iso"]))
    except (TypeError, ValueError) as exc:
        return [f"meta.semanas o meta.fecha_iso inválidos: {exc}"]

    semanas = datos.get("semanas") or []
    if not isinstance(semanas, list) or not semanas:
        return ["'semanas' debe ser una lista no vacía"]
    if len(semanas) != total_semanas:
        problemas.append(
            f"meta.semanas declara {total_semanas} y hay {len(semanas)} entradas en 'semanas'"
        )

    numeros = [sem.get("numero") for sem in semanas]
    if numeros != list(range(1, len(semanas) + 1)):
        problemas.append(f"las semanas deben ser contiguas desde 1; se recibió {numeros}")

    fases = {fase.get("id"): fase for fase in datos.get("fases") or []}
    if not fases:
        problemas.append("'fases' no puede estar vacío")

    cubiertas: list[int] = []
    for fase in datos.get("fases") or []:
        for numero in fase.get("semanas") or []:
            cubiertas.append(numero)
    if sorted(cubiertas) != list(range(1, len(semanas) + 1)):
        problemas.append(
            f"las fases deben cubrir las semanas 1..{len(semanas)} exactamente una vez; "
            f"cubren {sorted(cubiertas)}"
        )

    for sem in semanas:
        etiqueta = f"semana {sem.get('numero')}"
        tipo = str(sem.get("tipo", "practica")).lower()
        if tipo not in ("practica", "teoria"):
            problemas.append(
                f"{etiqueta}: tipo {tipo!r} no válido; use 'practica' o 'teoria'"
            )
        if sem.get("fase") not in fases:
            problemas.append(f"{etiqueta}: fase {sem.get('fase')!r} no existe en 'fases'")
        for clave in ("titulo", "objetivo", "contenidos", "herramientas", "evaluacion"):
            if not sem.get(clave):
                problemas.append(f"{etiqueta}: falta '{clave}'")
        practica = sem.get("practica") or {}
        for clave in ("titulo", "escenario", "pasos", "entregable", "criterios"):
            if not practica.get(clave):
                problemas.append(f"{etiqueta}: falta practica.{clave}")
        pesos = [float(c.get("peso", 0)) for c in practica.get("criterios") or []]
        if pesos and abs(sum(pesos) - NOTA_MAXIMA) > 0.01:
            problemas.append(
                f"{etiqueta}: los criterios de la práctica suman {sum(pesos):.2f} "
                f"y deben sumar {NOTA_MAXIMA:g}"
            )
        problemas.extend(
            _validar_tabla(practica.get("tabla_datos"), f"{etiqueta}: practica.tabla_datos")
        )
        if practica.get("ampliacion") is not None:
            ampliacion = practica["ampliacion"]
            if not isinstance(ampliacion, list) or not all(
                isinstance(item, str) and item.strip() for item in ampliacion
            ):
                problemas.append(
                    f"{etiqueta}: practica.ampliacion debe ser una lista de textos no vacíos"
                )
        tabla = practica.get("tabla_datos") or {}
        if tabla.get("nota"):
            problemas.extend(
                _validar_matematica(tabla["nota"], f"{etiqueta}: practica.tabla_datos.nota")
            )
        for campo in ("fundamento_tex", "figura_tex"):
            if practica.get(campo):
                problemas.extend(
                    _unicode_crudo(practica[campo], f"{etiqueta}: practica.{campo}")
                )
        problemas.extend(_validar_matematica(sem.get("objetivo"), f"{etiqueta}: objetivo"))
        for campo in ("escenario", "entregable"):
            problemas.extend(
                _validar_matematica(practica.get(campo), f"{etiqueta}: practica.{campo}")
            )
        for campo in ("materiales", "pasos", "analisis", "ampliacion"):
            for i, item in enumerate(practica.get(campo) or []):
                problemas.extend(
                    _validar_matematica(item, f"{etiqueta}: practica.{campo}[{i}]")
                )

    pesos_curso = [float(p.get("peso", 0)) for p in (datos.get("evaluacion") or {}).get("pesos") or []]
    if pesos_curso and abs(sum(pesos_curso) - PESO_TOTAL_CURSO) > 0.01:
        problemas.append(
            f"los pesos de evaluación suman {sum(pesos_curso):.2f} y deben sumar "
            f"{PESO_TOTAL_CURSO:g}"
        )

    rubrica = (datos.get("evaluacion") or {}).get("rubrica") or []
    if rubrica:
        pesos_rubrica: list[float] = []
        for criterio in rubrica:
            if not isinstance(criterio, dict) or not criterio.get("criterio"):
                problemas.append("evaluacion.rubrica: cada criterio necesita 'criterio'")
                continue
            if not re.fullmatch(r"[a-z][a-z0-9_]*", str(criterio["criterio"])):
                problemas.append(
                    f"evaluacion.rubrica: la clave {criterio['criterio']!r} debe ser un "
                    "identificador ASCII (minúsculas, dígitos y guion bajo)"
                )
            if criterio.get("peso") in (None, ""):
                problemas.append(
                    f"evaluacion.rubrica: el criterio {criterio['criterio']!r} no declara 'peso'"
                )
                continue
            pesos_rubrica.append(float(criterio["peso"]))
            if not criterio.get("descripcion"):
                problemas.append(
                    f"evaluacion.rubrica: el criterio {criterio['criterio']!r} no declara "
                    "'descripcion'"
                )
        if pesos_rubrica and abs(sum(pesos_rubrica) - NOTA_MAXIMA) > 0.01:
            problemas.append(
                f"evaluacion.rubrica: los pesos suman {sum(pesos_rubrica):.2f} y deben sumar "
                f"{NOTA_MAXIMA:g}"
            )

    for indice, apendice in enumerate(datos.get("apendices") or [], start=1):
        etiqueta = f"apéndice {indice}"
        if not isinstance(apendice, dict) or not apendice.get("titulo"):
            problemas.append(f"{etiqueta}: falta 'titulo'")
            continue
        if not apendice.get("texto") and not apendice.get("tabla"):
            problemas.append(f"{etiqueta}: necesita 'texto' o 'tabla'")
        problemas.extend(_validar_tabla(apendice.get("tabla"), f"{etiqueta}: tabla"))
        if apendice.get("texto"):
            problemas.extend(_validar_matematica(apendice["texto"], f"{etiqueta}: texto"))
        nota_tabla = (apendice.get("tabla") or {}).get("nota")
        if nota_tabla:
            problemas.extend(_validar_matematica(nota_tabla, f"{etiqueta}: tabla.nota"))

    puertos: list[int] = []
    for imagen in (datos.get("laboratorio") or {}).get("imagenes") or []:
        for clave in ("nombre", "imagen", "puerto", "puerto_contenedor", "proposito"):
            if imagen.get(clave) in (None, ""):
                problemas.append(f"laboratorio: imagen {imagen.get('nombre')!r} sin '{clave}'")
        puertos.append(int(imagen.get("puerto", 0)))
    if len(set(puertos)) != len(puertos):
        problemas.append(f"laboratorio: puertos repetidos en el host: {puertos}")

    for control in datos.get("controles") or []:
        if control.get("fase") not in fases:
            problemas.append(f"control de fase {control.get('fase')!r} no corresponde a una fase")
        puntos = [float(p.get("puntaje", 0)) for p in control.get("preguntas") or []]
        if puntos and abs(sum(puntos) - float((datos.get("evaluacion") or {}).get("escala", 20))) > 0.01:
            problemas.append(
                f"control de fase {control.get('fase')}: los puntajes suman {sum(puntos):.2f} "
                "y deben cerrar en la escala declarada"
            )
        for i, pregunta in enumerate(control.get("preguntas") or [], 1):
            problemas.extend(
                _validar_matematica(
                    pregunta.get("enunciado"),
                    f"control de fase {control.get('fase')}: pregunta {i}.enunciado",
                )
            )

    final = datos.get("evaluacion_final") or {}
    puntos_final = [float(s.get("puntaje", 0)) for s in final.get("secciones") or []]
    if puntos_final and abs(sum(puntos_final) - float((datos.get("evaluacion") or {}).get("escala", 20))) > 0.01:
        problemas.append(
            f"evaluacion_final: las secciones suman {sum(puntos_final):.2f} y deben cerrar "
            "en la escala declarada"
        )

    ra = datos.get("resultados_aprendizaje") or []
    if not isinstance(ra, list) or not ra:
        problemas.append("'resultados_aprendizaje' debe ser una lista no vacía")
    else:
        for indice, item in enumerate(ra, start=1):
            if not isinstance(item, dict) or not item.get("id") or not item.get("texto"):
                problemas.append(
                    f"resultados_aprendizaje[{indice}] debe ser un mapa con 'id' y "
                    "'texto'; el sílabo los numera por 'id'"
                )

    grupos = datos.get("grupos") or {}
    roles = [r.get("nombre") for r in grupos.get("roles") or []]
    if roles:
        try:
            cantidad = int(grupos.get("cantidad", 0))
        except (TypeError, ValueError):
            cantidad = 0
        if cantidad < 1:
            problemas.append("grupos.cantidad debe ser un entero mayor que cero")
        inicial = grupos.get("asignacion_inicial") or []
        if inicial and sorted(inicial) != sorted(roles):
            problemas.append(
                "grupos.asignacion_inicial debe listar exactamente los mismos roles que 'roles'"
            )
        for fase in grupos.get("fase_con_roles") or []:
            if fase not in fases:
                problemas.append(f"grupos.fase_con_roles: la fase {fase!r} no existe")
        rotaciones = grupos.get("rotaciones") or []
        if rotaciones:
            if not all(isinstance(r, str) and r.strip() for r in rotaciones):
                problemas.append(
                    "grupos.rotaciones debe ser una lista de etiquetas de texto no vacías"
                )
            elif len(rotaciones) < len(roles):
                problemas.append(
                    f"grupos.rotaciones: hay {len(rotaciones)} rotaciones y {len(roles)} roles; "
                    "con menos rotaciones que roles algún integrante quedaría sin cubrir algún rol"
                )

    entregas = datos.get("entregas") or {}
    for clave in ("plataforma", "modalidad", "cadencia", "corte"):
        if not entregas.get(clave):
            problemas.append(f"entregas.{clave} es obligatorio y está vacío")
    for clave in ("estructura", "reglas"):
        if not entregas.get(clave):
            problemas.append(f"entregas.{clave} no puede estar vacío")

    return problemas


# ── Piezas de documento ───────────────────────────────────────────────────────


def _documento(meta: dict[str, Any], encabezado: str, cuerpo: str) -> str:
    """Envuelve un cuerpo LaTeX con el preámbulo infográfico y su cabecera.

    Args:
        meta: Bloque `meta` del descriptor.
        encabezado: Texto corto de la cabecera derecha (ya escapado).
        cuerpo: Contenido LaTeX del documento.

    Returns:
        Documento completo, listo para compilar.
    """
    titulo = _t(meta["titulo"])
    icono = re.sub(r"[^a-z0-9-]", "", str(meta.get("icono") or "shield-alt").lower()) or "shield-alt"
    extra = "\n".join(
        [
            r"\renewcommand{\iconoBanda}{" + icono + "}",
            r"\fancyhead[L]{\footnotesize\color{grisTexto}\faIcon{" + icono + "}~" + _t(meta["codigo"]) + "}",
            r"\fancyhead[R]{\footnotesize\color{grisTexto}" + encabezado + "}",
            r"\hypersetup{pdftitle={" + titulo + "},pdfauthor={" + _t(meta["autor"]) + "}",
            r"  pdfsubject={" + _t(meta["codigo"]) + "}}",
            "",
        ]
    )
    return (
        PREAMBULO_INFOGRAFIA
        + extra
        + "\n\\begin{document}\n"
        + cuerpo
        + "\n\\end{document}\n"
    )


def _metadatos_curso(meta: dict[str, Any]) -> str:
    """Línea de autoría bajo la banda de título."""
    return (
        r"\begin{center}\small\color{grisTexto}"
        + _t(meta["autor"])
        + r" \textbar{} "
        + _t(meta.get("institucion", ""))
        + r" \textbar{} "
        + _t(meta["fecha"])
        + r"\end{center}"
    )


def _lista(elementos: list[str], entorno: str = "itemize", math: bool = False) -> str:
    """Construye una lista LaTeX escapando cada elemento.

    Args:
        elementos: Textos del descriptor.
        entorno: `itemize` o `enumerate`.
        math: Si es cierto, conserva la matemática en línea (`_tm`).
    """
    escapar = _tm if math else _t
    cuerpo = "\n".join(r"  \item " + escapar(e) for e in elementos)
    return f"\\begin{{{entorno}}}[leftmargin=1.4em,itemsep=2pt,topsep=3pt]\n{cuerpo}\n\\end{{{entorno}}}"


def _tabla_datos(filas: list[tuple[str, str]]) -> str:
    """Tabla de dos columnas (etiqueta, valor) para fichas técnicas."""
    cuerpo = "\n".join(
        r"\textbf{" + _t(k) + "} & " + v + r" \\" for k, v in filas
    )
    return (
        "\\begin{tabularx}{\\linewidth}{@{}>{\\raggedright\\arraybackslash}p{4.6cm}X@{}}\n"
        "\\toprule\n" + cuerpo + "\n\\bottomrule\n\\end{tabularx}"
    )


def _texto(datos: dict[str, Any], clave: str, defecto: str) -> str:
    """Devuelve un texto de `textos:` del descriptor o su valor por defecto."""
    return str((datos.get("textos") or {}).get(clave) or defecto)


def _carpeta_entrega(datos: dict[str, Any], numero: int) -> str:
    """Nombre de la carpeta de entrega de una semana.

    La plantilla vive en `entregas.carpeta` (por ejemplo ``semana_{n:02d}``)
    y se formatea con el número de semana. Si la plantilla es inválida se cae
    al patrón histórico para no romper los cursos existentes.
    """
    entregas = datos.get("entregas") or {}
    plantilla = str(entregas.get("carpeta") or "semana_{n:02d}")
    try:
        return plantilla.format(n=numero, numero=numero)
    except (KeyError, IndexError, ValueError):
        return f"semana_{numero:02d}"


def _tabla_columnas(
    columnas: list[str],
    filas: list[list[str]],
    caption: str = "",
    nota: str = "",
) -> str:
    """Tabla de N columnas con celdas LaTeX crudas (unidades y matemática).

    A diferencia de `_lista`/`_t`, aquí no se escapa el contenido: el descriptor
    usa LaTeX deliberado (``\\si{\\ohm}``, ``$V$``) porque estas tablas son datos
    de laboratorio. El validador exige que cada fila tenga el mismo número de
    celdas que la cabecera.
    """
    alineacion = "".join("c" for _ in columnas)
    cabecera = " & ".join(columnas) + r" \\"
    cuerpo = "\n".join(" & ".join(fila) + r" \\" for fila in filas)
    # El bloque entero va en una minipage: así el pie de tabla no se queda
    # huérfano en una página y la tabla en la siguiente (pasó con el apéndice de
    # 18 filas del Keithley 175). Una minipage no se parte, de modo que LaTeX
    # mueve título, tabla y nota juntos o los deja juntos.
    partes = [r"\begin{center}", r"\begin{minipage}{\linewidth}", r"\centering", r"{\small"]
    if caption:
        partes.append(r"\textbf{" + _t(caption) + r"}\par\smallskip")
    partes.extend(
        [
            "\\begin{tabular}{@{}" + alineacion + "@{}}",
            r"\toprule",
            cabecera,
            r"\midrule",
            cuerpo,
            r"\bottomrule",
            r"\end{tabular}",
            r"}"
            + (r"\par\smallskip{\footnotesize " + _tm(nota) + "}" if nota else ""),
            r"\end{minipage}",
            r"\end{center}",
        ]
    )
    return "\n".join(partes)


# ── Generadores de documento ──────────────────────────────────────────────────


def tex_silabo(datos: dict[str, Any]) -> str:
    """Genera el sílabo del curso."""
    meta = datos["meta"]
    lab = datos.get("laboratorio") or {}
    entregas = datos.get("entregas") or {}
    fases = datos.get("fases") or []

    partes: list[str] = [
        banda_titulo(_t(meta["titulo"]), _t(meta["subtitulo"])),
        _metadatos_curso(meta),
    ]

    partes.append(seccion_con_icono("id-card", "Identificación"))
    partes.append(
        _tabla_datos(
            [
                ("Código", _t(meta["codigo"])),
                ("Duración", _t(f'{meta["semanas"]} semanas')),
                ("Grupos", _t(f'{meta.get("grupos", "")} grupos de trabajo')),
                ("Modalidad", _t(meta.get("modalidad", ""))),
                (
                    "Entrega",
                    _t(
                        f'{entregas.get("plataforma", "GitHub")} por grupo, '
                        "revisado al finalizar cada semana"
                    ),
                ),
                ("Dedicación", _t(meta.get("dedicacion_semanal", ""))),
                ("Versión", _t(meta.get("version", 1))),
            ]
        )
    )

    partes.append(seccion_con_icono("bullseye", "Objetivo general"))
    partes.append(_t(datos.get("objetivo_general", "")))

    partes.append(seccion_con_icono("tasks", "Resultados de aprendizaje"))
    ra = datos.get("resultados_aprendizaje") or []
    partes.append(
        _lista([f'{r["id"]}: {r["texto"]}' for r in ra], entorno="enumerate")
    )

    partes.append(seccion_con_icono("sitemap", "Estructura por fases"))
    for fase in fases:
        semanas = fase.get("semanas") or []
        rango = f"semanas {semanas[0]} a {semanas[-1]}" if len(semanas) > 1 else f"semana {semanas[0]}"
        partes.append(
            "\\begin{tcolorbox}[cajaContenido,title={"
            + _t(f'Fase {fase["id"]} --- {fase["nombre"]}')
            + "}]"
            + _t(f"{rango.capitalize()}.")
            + " "
            + _t(fase.get("enfoque", ""))
            + "\n\\end{tcolorbox}"
        )

    partes.append(seccion_con_icono("clipboard-check", "Sistema de evaluación"))
    evaluacion = datos.get("evaluacion") or {}
    filas = "\n".join(
        _t(p["concepto"]) + " & " + _n(p["peso"]) + r" \\"
        for p in evaluacion.get("pesos") or []
    )
    partes.append(
        "\\begin{tabularx}{\\linewidth}{@{}X r@{}}\n\\toprule\n"
        "Concepto & Peso (\\%)\\\\\n\\midrule\n"
        + filas
        + "\n\\midrule\n\\textbf{Total} & \\textbf{"
        + _n(sum(float(p["peso"]) for p in evaluacion.get("pesos") or []))
        + "}\\\\\n\\bottomrule\n\\end{tabularx}"
    )
    partes.append(
        "\\begin{cajaRecuerda}La escala de calificación es de "
        + _t(evaluacion.get("escala", 20))
        + " puntos y la nota mínima aprobatoria es "
        + _t(evaluacion.get("nota_minima", 10))
        + ". La nota del curso se calcula ponderando los conceptos de la tabla; "
        "no se promedian notas de distinta escala.\n\\end{cajaRecuerda}"
    )

    partes.append(seccion_con_icono("code-branch", "Entrega y revisión semanal"))
    if entregas:
        partes.append(
            _lista(
                [
                    f'Plataforma: {entregas.get("plataforma", "")}.',
                    f'Modalidad: {entregas.get("modalidad", "")}',
                    f'Cadencia: {entregas.get("cadencia", "")}',
                    f'Corte: {entregas.get("corte", "")}',
                ]
            )
        )
        partes.append(r"\textbf{Estructura del repositorio}")
        partes.append(_lista(entregas.get("estructura") or []))
        partes.append(r"\textbf{Reglas de entrega}")
        partes.append(_lista(entregas.get("reglas") or []))
        partes.append(
            r"\begin{cajaRecuerda}La entrega se considera válida solo cuando está "
            r"en el repositorio del grupo antes del corte. Un enlace, una captura suelta o "
            r"un archivo enviado por mensajería no sustituyen el repositorio.\end{cajaRecuerda}"
        )

    partes.append(seccion_con_icono("server", "Laboratorio"))
    if lab.get("imagenes"):
        partes.append(
            "\\begin{tabularx}{\\linewidth}{@{}l l r X@{}}\n\\toprule\n"
            "Contenedor & Imagen & Puerto & Propósito\\\\\n\\midrule\n"
            + "\n".join(
                _t(i["nombre"])
                + " & \\texttt{"
                + _t(i["imagen"])
                + "} & "
                + _t(i["puerto"])
                + " & "
                + _t(i["proposito"])
                + r" \\"
                for i in lab.get("imagenes") or []
            )
            + "\n\\bottomrule\n\\end{tabularx}"
        )
    partes.append(_t(lab.get("recursos", "")))
    if lab.get("caracter"):
        partes.append(_t(lab["caracter"]))
    partes.append(_lista(lab.get("reglas") or []))

    partes.append(seccion_con_icono("balance-scale", "Políticas de uso"))
    partes.append(_lista(datos.get("politicas") or []))

    partes.append(seccion_con_icono("book", "Bibliografía"))
    partes.append(
        _lista(
            [
                f'{b["autor"]}. {b["titulo"]}. {b.get("detalle", "")}'
                for b in datos.get("bibliografia") or []
            ]
        )
    )

    return _documento(meta, "Sílabo", "\n\n".join(partes))


def tex_plan_semanal(datos: dict[str, Any]) -> str:
    """Genera el plan semanal con una caja por semana."""
    meta = datos["meta"]
    fases = {f["id"]: f for f in datos.get("fases") or []}
    partes: list[str] = [
        banda_titulo("Plan semanal", _t(f'{meta["titulo"]} --- {meta["semanas"]} semanas')),
        _metadatos_curso(meta),
    ]
    entregas = datos.get("entregas") or {}
    if entregas:
        carpeta = _carpeta_entrega(datos, 0)
        if carpeta.endswith("00"):
            carpeta = carpeta[:-2] + "NN"
        defecto = (
            f'Cada práctica se entrega en {entregas.get("plataforma", "GitHub")}, dentro de '
            f'la carpeta {carpeta}, antes del corte: '
            f'{entregas.get("corte", "")} El docente revisa esa entrega al finalizar la semana.'
        )
        partes.append(_t(_texto(datos, "plan_entrega", defecto)))

    for sem in datos["semanas"]:
        fase = fases[sem["fase"]]
        practica = sem["practica"]
        bloques = [
            r"\textbf{Fase " + _t(fase["id"]) + "} --- " + _t(fase["nombre"]),
            r"\textbf{Objetivo.} " + _tm(sem["objetivo"]),
            r"\textbf{Contenidos}",
            _lista(sem["contenidos"]),
            r"\textbf{Herramientas:} " + _t(", ".join(sem["herramientas"])) + ".",
            r"\textbf{" + _t(etiqueta_semana(sem)) + ".} \emph{" + _t(practica["titulo"]) + "}. " + _tm(practica["escenario"]),
            r"\textbf{Entregable:} " + _tm(practica["entregable"]),
        ]
        instrumento = str(sem.get("evaluacion", "")).replace("_", " ")
        bloques.append(r"\textbf{Instrumento de evaluación:} " + _t(instrumento) + ".")
        partes.append(
            "\\begin{tcolorbox}[cajaContenido,title={"
            + _t(f'Semana {sem["numero"]} --- {sem["titulo"]}')
            + "}]\n"
            + "\n\n".join(bloques)
            + "\n\\end{tcolorbox}"
        )

    return _documento(meta, "Plan semanal", "\n\n".join(partes))


def _contrato_datos(datos: dict[str, Any] | None = None) -> str:
    """Caja con el contrato JSON que deben cumplir los scripts del curso."""
    ejemplo = (
        (datos or {}).get("textos", {}).get("contrato_ejemplo")
        if isinstance((datos or {}).get("textos"), dict)
        else None
    ) or (
        "{\n"
        '  "status": "ok",\n'
        '  "objetivo": "172.28.0.10",\n'
        '  "duracion_s": 12.4,\n'
        '  "hallazgos": [\n'
        '    {"puerto": 80, "servicio": "http", "version": "nginx"}\n'
        "  ],\n"
        '  "errores": []\n'
        "}"
    )
    return (
        "\\begin{cajaConcepto}Todo script entregado imprime \\textbf{un solo objeto JSON} "
        "por la salida estándar y devuelve un diccionario con estas claves. "
        "\\texttt{status} vale \\texttt{ok} o \\texttt{error}; si es \\texttt{error}, "
        "\\texttt{errores} explica el motivo y el programa sale con código distinto de cero."
        "\n\\begin{lstlisting}[language=Python,style=estiloPython]\n"
        + ejemplo
        + "\n\\end{lstlisting}\n\\end{cajaConcepto}"
    )


def tex_guia(datos: dict[str, Any]) -> str:
    """Genera la guía del estudiante."""
    meta = datos["meta"]
    lab = datos.get("laboratorio") or {}
    grupos = datos.get("grupos") or {}
    entregas = datos.get("entregas") or {}
    evaluacion = datos.get("evaluacion") or {}
    partes: list[str] = [
        banda_titulo("Guía del estudiante", _t(f'{meta["titulo"]} --- cómo se trabaja y se entrega')),
        _metadatos_curso(meta),
    ]

    partes.append(seccion_con_icono("info-circle", "Cómo funciona el curso"))
    defecto_como_funciona = (
        f"El curso se organiza en {meta['semanas']} semanas agrupadas en "
        f"{len(datos.get('fases') or [])} fases. Cada semana tiene una práctica de laboratorio "
        "que se entrega al terminar la sesión. No hay proyecto integrador: lo que se evalúa es "
        "el trabajo de cada semana y la capacidad de sostener el criterio en la evaluación final."
    )
    partes.append(_t(_texto(datos, "como_funciona", defecto_como_funciona)))

    partes.append(seccion_con_icono("users", "Grupos y roles"))
    partes.append(
        _t(
            f'El curso trabaja con {grupos.get("cantidad", 0)} grupos. '
            + str(grupos.get("asignacion", ""))
        )
    )
    partes.append(
        _lista(
            [
                f'{r["nombre"]}: {r["descripcion"]} Aporta: {r.get("aporta", "")}'
                for r in grupos.get("roles") or []
            ]
        )
    )
    partes.append(_t(grupos.get("rotacion", "")))
    inicial = grupos.get("asignacion_inicial") or []
    rotaciones = [str(r) for r in (grupos.get("rotaciones") or [])]
    fases_roles = grupos.get("fase_con_roles") or []
    if rotaciones:
        etiquetas, turnos = rotaciones, list(range(len(rotaciones)))
    else:
        etiquetas = [f"Fase {f}" for f in fases_roles]
        turnos = [int(f) - 1 for f in fases_roles]
    if inicial and etiquetas:
        filas = []
        for etiqueta, turno in zip(etiquetas, turnos):
            asignados = [inicial[(i + turno) % len(inicial)] for i in range(len(inicial))]
            filas.append(
                _t(etiqueta) + " & " + " & ".join(_t(a) for a in asignados) + r" \\"
            )
        partes.append(r"\textbf{Asignación de roles por rotación (idéntica en cada grupo)}")
        partes.append(
            "\\begin{tabularx}{\\linewidth}{@{}l " + " ".join(["X"] * len(inicial)) + "@{}}\n\\toprule\n"
            "Rotación & "
            + " & ".join(_t(f"Integrante {i}") for i in range(1, len(inicial) + 1))
            + r" \\"
            + "\n\\midrule\n"
            + "\n".join(filas)
            + "\n\\bottomrule\n\\end{tabularx}"
        )
    if grupos.get("repositorio"):
        partes.append(_t(grupos["repositorio"]))

    if entregas:
        partes.append(
            seccion_con_icono(
                "code-branch", _texto(datos, "titulo_entregas", "Repositorio GitHub y entregas")
            )
        )
        partes.append(
            _t(
                f'La entrega se hace en {entregas.get("plataforma", "GitHub")}. '
                + str(entregas.get("modalidad", ""))
            )
        )
        partes.append(_t(str(entregas.get("cadencia", ""))))
        partes.append(_t(f'Corte de cada semana: {entregas.get("corte", "")}'))
        partes.append(
            r"\textbf{"
            + _t(_texto(datos, "titulo_estructura", "Estructura del repositorio"))
            + "}"
        )
        partes.append(_lista(entregas.get("estructura") or []))
        partes.append(r"\textbf{Reglas de entrega}")
        partes.append(_lista(entregas.get("reglas") or []))
        aviso_entrega = _texto(
            datos,
            "aviso_entrega",
            "el trabajo se hace desde el equipo y la conexión de cada grupo. El único "
            "objetivo permitido es el laboratorio local (o el entorno propio declarado) y "
            "los sistemas con autorización escrita; nunca la infraestructura de la "
            "universidad ni de terceros.",
        )
        partes.append(
            r"\begin{tcolorbox}[cajaMejora]\textbf{Antes de empezar:} "
            + _t(aviso_entrega)
            + "\n\\end{tcolorbox}"
        )

    partes.append(seccion_con_icono("cube", "Puesta en marcha del laboratorio"))
    if lab.get("caracter"):
        partes.append(_t(lab["caracter"]))
    if lab.get("recursos"):
        partes.append(_t(lab["recursos"]))
    if lab.get("imagenes"):
        partes.append(
            _t(
                "Si se usa el laboratorio de la carpeta del curso, se levanta con "
                "docker compose -f laboratorio/docker-compose.yml up -d. "
                "Los servicios quedan accesibles solo en localhost y en la red doméstica de "
                "cada grupo."
            )
        )
        partes.append(
            "\\begin{tabularx}{\\linewidth}{@{}l l r@{}}\n\\toprule\n"
            "Servicio & Imagen & URL local\\\\\n\\midrule\n"
            + "\n".join(
                _t(i["nombre"])
                + " & \\texttt{"
                + _t(i["imagen"])
                + "} & \\texttt{localhost:"
                + _t(i["puerto"])
                + "}"
                + r" \\"
                for i in lab.get("imagenes") or []
            )
            + "\n\\bottomrule\n\\end{tabularx}"
        )
        partes.append(
            "\\begin{cajaRecuerda}Para reiniciar el laboratorio a su estado inicial: "
            "\\texttt{docker compose down -v} y volver a levantarlo. Ningún cambio debe "
            "sobrevivir entre prácticas sin documentarse.\n\\end{cajaRecuerda}"
        )
    partes.append(_lista(lab.get("reglas") or []))

    if (datos.get("textos") or {}).get("contrato_datos", True):
        partes.append(seccion_con_icono("code", "Contrato de datos de los scripts"))
        partes.append(_contrato_datos(datos))
        reglas_codigo = (datos.get("textos") or {}).get("reglas_codigo") or [
            "Type hints en todas las funciones públicas y docstrings estilo Google.",
            "Errores manejados explícitamente: nunca se devuelve una lista vacía para ocultar un fallo.",
            "Sin rutas absolutas ni credenciales en el código.",
            "Salida determinista: mismo objetivo y mismas opciones producen la misma estructura.",
        ]
        partes.append(_lista(reglas_codigo))

    partes.append(seccion_con_icono("clipboard-check", "Evaluación"))
    partes.append(
        "\\begin{tabularx}{\\linewidth}{@{}X r@{}}\n\\toprule\n"
        "Concepto & Peso (\\%)\\\\\n\\midrule\n"
        + "\n".join(
            _t(p["concepto"]) + " & " + _n(p["peso"]) + r" \\"
            for p in evaluacion.get("pesos") or []
        )
        + "\n\\bottomrule\n\\end{tabularx}"
    )
    partes.append(
        _t(
            _texto(
                datos,
                "nota_correccion",
                "Cada práctica se corrige con la rúbrica de diez puntos incluida en su propio "
                "documento. Entregar fuera de plazo descuenta según el reglamento de la "
                "asignatura; entregar sin evidencia anonimizada se devuelve sin corregir.",
            )
        )
    )

    partes.append(
        seccion_con_icono(
            "balance-scale", _texto(datos, "titulo_politicas", "Ética y legalidad")
        )
    )
    partes.append(_lista(datos.get("politicas") or []))

    partes.append(seccion_con_icono("calendar-alt", "Calendario resumido"))
    partes.append(
        "\\begin{tabularx}{\\linewidth}{@{}r p{4.1cm} X@{}}\n\\toprule\n"
        "Sem. & Tema & Entregable\\\\\n\\midrule\n"
        + "\n".join(
            _t(sem["numero"])
            + " & "
            + _t(sem["titulo"])
            + " & "
            + _tm(sem["practica"]["entregable"])
            + r" \\"
            for sem in datos["semanas"]
        )
        + "\n\\bottomrule\n\\end{tabularx}"
    )

    for apendice in datos.get("apendices") or []:
        partes.append(seccion_con_icono("paperclip", _t(apendice["titulo"])))
        if apendice.get("texto"):
            partes.append(_tm(apendice["texto"]))
        tabla = apendice.get("tabla") or {}
        if tabla:
            partes.append(
                _tabla_columnas(
                    tabla.get("columnas") or [],
                    tabla.get("filas") or [],
                    tabla.get("caption", ""),
                    tabla.get("nota", ""),
                )
            )

    return _documento(meta, "Guía del estudiante", "\n\n".join(partes))


def tex_practica(datos: dict[str, Any], sem: dict[str, Any]) -> str:
    """Genera el enunciado de una práctica semanal con su rúbrica."""
    meta = datos["meta"]
    fases = {f["id"]: f for f in datos.get("fases") or []}
    fase = fases[sem["fase"]]
    practica = sem["practica"]
    grupos = datos.get("grupos") or {}
    entregas = datos.get("entregas") or {}
    documento = f'{etiqueta_semana(sem)} {sem["numero"]:02d}'

    partes: list[str] = [
        banda_titulo(
            _t(f'{documento} --- {practica["titulo"]}'),
            _t(f'Semana {sem["numero"]} --- Fase {fase["id"]}: {fase["nombre"]}'),
        ),
        _metadatos_curso(meta),
        _tabla_datos(
            [
                (
                    "Duración",
                    _t(meta.get("duracion_sesion", "3 horas de laboratorio")),
                ),
                ("Modalidad", _t(f'{grupos.get("cantidad", 0)} grupos con roles rotativos')),
                (
                    "Entrega",
                    _t(
                        f'{entregas.get("plataforma", "GitHub")} del grupo, carpeta '
                        f'{_carpeta_entrega(datos, sem["numero"])}, antes del corte semanal'
                    ),
                ),
                ("Instrumento", _t(str(sem.get("evaluacion", "")).replace("_", " "))),
            ]
        ),
        seccion_con_icono("bullseye", "Objetivo"),
        _tm(sem["objetivo"]),
        seccion_con_icono("clipboard-list", "Contenidos que se aplican"),
        _lista(sem["contenidos"]),
    ]

    if practica.get("fundamento_tex"):
        partes.append(seccion_con_icono("book-open", "Fundamento teórico"))
        partes.append(str(practica["fundamento_tex"]).strip())

    if practica.get("figura_tex"):
        caption = _t(practica.get("figura_caption", "Montaje de la práctica"))
        partes.append(
            "\\begin{center}\n"
            + str(practica["figura_tex"]).strip()
            + "\n\\par\\smallskip{\\small\\itshape "
            + caption
            + "}\n\\end{center}"
        )

    if practica.get("materiales"):
        partes.append(seccion_con_icono("box-open", "Materiales y equipos"))
        partes.append(_lista(practica["materiales"], math=True))

    partes.extend(
        [
            seccion_con_icono("flask", "Escenario"),
            _tm(practica["escenario"]),
            seccion_con_icono("list-ol", "Procedimiento"),
            _lista(practica["pasos"], entorno="enumerate", math=True),
        ]
    )

    tabla = practica.get("tabla_datos") or {}
    if tabla:
        partes.append(seccion_con_icono("table", "Tabla de datos"))
        partes.append(
            _tabla_columnas(
                tabla.get("columnas") or [],
                tabla.get("filas") or [],
                tabla.get("caption", ""),
                tabla.get("nota", ""),
            )
        )

    if practica.get("analisis"):
        partes.append(seccion_con_icono("calculator", "Análisis y tratamiento de datos"))
        partes.append(_lista(practica["analisis"], entorno="enumerate", math=True))

    if practica.get("ampliacion"):
        partes.append(seccion_con_icono("plus-circle", "Ampliación (opcional)"))
        partes.append(_lista(practica["ampliacion"], math=True))

    partes.extend(
        [
            seccion_con_icono("box-open", "Entregable"),
            _tm(practica["entregable"]),
            seccion_con_icono("ruler-combined", "Rúbrica de corrección"),
            "\\begin{tabularx}{\\linewidth}{@{}X r@{}}\n\\toprule\n"
            "Criterio & Peso\\\\\n\\midrule\n"
            + "\n".join(
                _t(c["criterio"]) + " & " + _n(c["peso"]) + r" \\"
                for c in practica["criterios"]
            )
            + "\n\\midrule\n\\textbf{Total} & \\textbf{"
            + _n(sum(float(c["peso"]) for c in practica["criterios"]))
            + "}\\\\\n\\bottomrule\n\\end{tabularx}",
        ]
    )

    if practica.get("requiere_codigo"):
        partes.append(seccion_con_icono("code", "Contrato del script"))
        partes.append(_contrato_datos(datos))

    aviso_practica = _texto(
        datos,
        "aviso_practica",
        "confirma que el objetivo es un contenedor del laboratorio o un sistema con "
        "autorización escrita. Si no lo es, detente y consulta al docente: la práctica no "
        "se corrige sin ese requisito.",
    )
    partes.append(
        "\\begin{tcolorbox}[cajaMejora]\\textbf{Antes de empezar:} "
        + _t(aviso_practica)
        + "\n\\end{tcolorbox}"
    )

    return _documento(meta, _t(documento), "\n\n".join(partes))


def tex_control(datos: dict[str, Any], control: dict[str, Any]) -> str:
    """Genera el instrumento de un control de fase."""
    meta = datos["meta"]
    fases = {f["id"]: f for f in datos.get("fases") or []}
    fase = fases.get(control.get("fase"))
    total = sum(float(p["puntaje"]) for p in control["preguntas"])

    partes: list[str] = [
        banda_titulo(_t(control["titulo"]), _t(f'Fase {fase["id"]} --- {fase["nombre"]}')),
        _metadatos_curso(meta),
        _tabla_datos(
            [
                ("Instrumento", _t(control.get("instrumento", ""))),
                ("Duración", _t(f'{control.get("duracion_min", 0)} minutos')),
                ("Puntaje total", _t(_n(total))),
                ("Carácter", _t(control.get("caracter", "Individual"))),
                (
                    "Entrega",
                    _t(
                        "En papel al cierre de la sesión; copia digitalizada en el "
                        f'{((datos.get("entregas") or {}).get("plataforma", "GitHub"))} '
                        "del grupo antes del corte semanal"
                    ),
                ),
            ]
        ),
        seccion_con_icono("info-circle", "Instrucciones"),
        "\\begin{cajaRecuerda}"
        + _t(
            _texto(
                datos,
                "instrucciones_control",
                "Responda de forma individual y sin apuntes. Cada respuesta debe justificar la "
                "decisión técnica, no solo nombrarla. Se valoran la precisión del vocabulario, la "
                "coherencia con el laboratorio y el reconocimiento de los límites legales.",
            )
        )
        + "\n\\end{cajaRecuerda}",
        seccion_con_icono("question-circle", "Preguntas"),
        _lista(
            [f'({_n(p["puntaje"])} pt) {p["enunciado"]}' for p in control["preguntas"]],
            entorno="enumerate",
            math=True,
        ),
    ]

    partes.append(seccion_con_icono("ruler-combined", "Distribución del puntaje"))
    partes.append(
        "\\begin{tabularx}{\\linewidth}{@{}r X r@{}}\n\\toprule\n"
        "Pregunta & Tema evaluado & Puntaje\\\\\n\\midrule\n"
        + "\n".join(
            _t(i + 1)
            + " & "
            + _t(p.get("tema") or _tema_de(p["enunciado"]))
            + " & "
            + _n(p["puntaje"])
            + r" \\"
            for i, p in enumerate(control["preguntas"])
        )
        + "\n\\midrule\n\\textbf{Total} & & \\textbf{"
        + _n(total)
        + "}\\\\\n\\bottomrule\n\\end{tabularx}"
    )

    return _documento(meta, _t(control["titulo"]), "\n\n".join(partes))


def _tema_de(enunciado: str) -> str:
    """Deriva una etiqueta corta de tema a partir del enunciado.

    Es solo el respaldo cuando la pregunta no declara `tema`. El texto
    automático (primeras palabras significativas) suele quedar telegráfico,
    así que la etiqueta editorial vive en el descriptor y esta función es
    puramente mecánica para que la tabla no quede vacía.
    """
    palabras = [p for p in re.split(r"[\s,.;:]+", enunciado) if len(p) > 4]
    return " ".join(palabras[:4]).rstrip(",")


def _condiciones_final(final: dict[str, Any]) -> str:
    """Renderiza `evaluacion_final.condiciones` como lista o párrafo.

    El descriptor admite la lista de condiciones (forma natural, y la que usa
    el curso de referencia) o un párrafo suelto. Pasar la lista a `_t()` la
    convertía en `str(lista)` y el PDF mostraba los corchetes y las comillas de
    Python en vez de las condiciones.
    """
    condiciones = final.get("condiciones")
    if isinstance(condiciones, list) and condiciones:
        return _lista(condiciones)
    if condiciones:
        return _t(condiciones)
    return _t(
        "Solo se evalúa lo que está dentro del alcance entregado en la hoja de la "
        "evaluación. Salirse de ese alcance anula la prueba, con independencia del "
        "resultado técnico. Firme la aceptación del alcance antes de empezar."
    )


def tex_evaluacion_final(datos: dict[str, Any]) -> str:
    """Genera el enunciado de la evaluación final práctica."""
    meta = datos["meta"]
    final = datos.get("evaluacion_final") or {}
    entregas = datos.get("entregas") or {}
    total = sum(float(s["puntaje"]) for s in final.get("secciones") or [])
    semana_final = int(final.get("semana", meta["semanas"]))

    partes: list[str] = [
        banda_titulo(_t(final["titulo"]), _t(f'{meta["titulo"]} --- cierre del curso')),
        _metadatos_curso(meta),
        _tabla_datos(
            [
                ("Instrumento", _t(final.get("instrumento", ""))),
                ("Duración", _t(f'{final.get("duracion_min", 0)} minutos')),
                ("Puntaje total", _t(_n(total))),
                (
                    "Carácter",
                    _t(final.get("caracter", "Individual, con alcance definido por el docente")),
                ),
                (
                    "Entrega",
                    _t(
                        f'{entregas.get("plataforma", "GitHub")} del grupo, carpeta '
                        f'{_carpeta_entrega(datos, semana_final)}, antes del corte semanal'
                    ),
                ),
            ]
        ),
        seccion_con_icono("exclamation-triangle", "Condiciones del alcance"),
        "\\begin{tcolorbox}[cajaMejora]\n"
        + _condiciones_final(final)
        + "\n\\end{tcolorbox}",
        seccion_con_icono("clipboard-check", "Secciones y puntaje"),
        "\\begin{tabularx}{\\linewidth}{@{}X r@{}}\n\\toprule\n"
        "Sección & Puntaje\\\\\n\\midrule\n"
        + "\n".join(
            _t(s["nombre"]) + " & " + _n(s["puntaje"]) + r" \\"
            for s in final.get("secciones") or []
        )
        + "\n\\midrule\n\\textbf{Total} & \\textbf{"
        + _n(total)
        + "}\\\\\n\\bottomrule\n\\end{tabularx}",
        seccion_con_icono("list-ul", "Detalle de cada sección"),
        _lista(
            [f'{s["nombre"]}: {s.get("detalle", "")}' for s in final.get("secciones") or []]
        ),
        seccion_con_icono("box-open", "Entregables"),
        _lista(
            final.get("entregables")
            or [
                "Informe técnico con hallazgos, evidencia y recomendaciones verificables.",
                "Resumen ejecutivo de una página, comprensible sin jerga.",
                "Evidencia preservada con su hash y su registro de custodia.",
                "Defensa oral de diez minutos sobre las decisiones y las limitaciones.",
                "Todo lo anterior, versionado en el repositorio GitHub del grupo antes del "
                "corte semanal.",
            ]
        ),
        seccion_con_icono("check-circle", "Criterios de aprobación"),
        _lista(
            final.get("criterios_aprobacion")
            or [
                "Cobertura completa del alcance declarado, sin inventar hallazgos.",
                "Evidencia reproducible y anonimizada.",
                "Recomendaciones que un tercero pueda aplicar sin preguntar.",
                "Reconocimiento explícito de lo que no se pudo verificar.",
            ]
        ),
    ]

    return _documento(meta, "Evaluación final", "\n\n".join(partes))


def yaml_rubrica(datos: dict[str, Any]) -> str:
    """Genera la rúbrica de prácticas en el formato de `evaluar_examen.py`.

    Los criterios salen de `evaluacion.rubrica` del descriptor; si el curso no
    los declara se usan los cinco históricos para no romper los descriptores
    anteriores. Las descripciones se serializan como JSON (YAML válido) para
    que dos puntos, comas o comillas no rompan el fichero.
    """
    declarados = (datos.get("evaluacion") or {}).get("rubrica") or []
    if declarados:
        criterios = [
            (str(c["criterio"]), float(c["peso"]), str(c.get("descripcion", "")))
            for c in declarados
        ]
    else:
        criterios = [
            (
                "cobertura_del_alcance",
                3.0,
                "Se ejecutaron todos los pasos del procedimiento sobre el objetivo declarado.",
            ),
            (
                "evidencia_reproducible",
                2.5,
                "Cada afirmación se sostiene con una salida, captura o hash que otro puede repetir.",
            ),
            (
                "causa_raiz_y_mitigacion",
                2.0,
                "Se identifica la causa técnica y el control que la elimina, no solo el síntoma.",
            ),
            (
                "analisis_y_conclusion",
                1.5,
                "La conclusión se deriva de la evidencia y reconoce los límites de la práctica.",
            ),
            (
                "calidad_del_informe",
                1.0,
                "Redacción clara, vocabulario correcto y evidencia anonimizada.",
            ),
        ]
    lineas = [
        "# Rúbrica genérica de prácticas — generada desde curso.yaml.",
        "# Compatible con execution/evaluar_examen.py (los pesos deben sumar 10).",
        f"nombre: Rúbrica de prácticas de {_t(datos['meta']['titulo'])}",
        "escala: 10",
        "criterios:",
    ]
    for nombre, peso, descripcion in criterios:
        lineas.append(f"  {nombre}:")
        lineas.append(f"    peso: {peso}")
        lineas.append("    descripcion: " + json.dumps(descripcion, ensure_ascii=False))
    return "\n".join(lineas) + "\n"


def yaml_compose(datos: dict[str, Any]) -> str:
    """Genera el `docker-compose.yml` del laboratorio."""
    lab = datos.get("laboratorio") or {}
    servicios: dict[str, Any] = {}
    for imagen in lab.get("imagenes") or []:
        servicios[imagen["nombre"]] = {
            "image": imagen["imagen"],
            "container_name": f'{_slug(lab.get("red", "cyberlab"))}-{imagen["nombre"]}',
            "restart": "unless-stopped",
            "ports": [f'{imagen["puerto"]}:{imagen["puerto_contenedor"]}'],
            "networks": [lab.get("red", "cyberlab")],
        }
        if imagen.get("comando"):
            servicios[imagen["nombre"]]["command"] = imagen["comando"]
    documento = {
        "name": lab.get("red", "cyberlab"),
        "services": servicios,
        "networks": {
            lab.get("red", "cyberlab"): {
                "driver": "bridge",
                "ipam": {"config": [{"subnet": lab.get("subred", "172.28.0.0/24")}]},
            }
        },
    }
    cabecera = (
        "# Laboratorio generado desde curso.yaml — no editar a mano.\n"
        "# Solo accesible en localhost; nunca exponer estos servicios a Internet.\n"
    )
    return cabecera + yaml.safe_dump(
        documento, sort_keys=False, allow_unicode=True, default_flow_style=False
    )


def md_laboratorio(datos: dict[str, Any]) -> str:
    """Genera el README del laboratorio."""
    lab = datos.get("laboratorio") or {}
    filas = "\n".join(
        f'| `{i["nombre"]}` | `{i["imagen"]}` | {i["puerto"]} | {i["proposito"]} |'
        for i in lab.get("imagenes") or []
    )
    reglas = "\n".join(f"- {r}" for r in lab.get("reglas") or [])
    caracter = lab.get("caracter") or ""
    if not lab.get("imagenes"):
        return (
            "# Laboratorio del curso\n\n"
            f"{caracter}\n\n"
            f"{lab.get('recursos', '')}\n\n"
            "Este curso no usa contenedores: el laboratorio es físico y el material\n"
            "de análisis se ejecuta en el equipo de cada grupo.\n\n"
            "## Reglas\n\n"
            f"{reglas}\n"
        )
    return (
        "# Laboratorio del curso\n\n"
        f"{caracter}\n\n"
        "Cada grupo trabaja desde su propio equipo y conexión. Este laboratorio no\n"
        "necesita red compartida: los servicios se publican solo en `localhost`.\n\n"
        f"Red Docker: `{lab.get('red', 'cyberlab')}` sobre `{lab.get('subred', '')}`.\n\n"
        "## Servicios\n\n"
        "| Contenedor | Imagen | Puerto local | Propósito |\n"
        "| --- | --- | --- | --- |\n"
        f"{filas}\n\n"
        f"Requisitos: {lab.get('recursos', '')}\n\n"
        "## Puesta en marcha\n\n"
        "```bash\n"
        "docker compose -f laboratorio/docker-compose.yml up -d\n"
        "docker compose -f laboratorio/docker-compose.yml ps\n"
        "```\n\n"
        "## Reinicio a estado inicial\n\n"
        "```bash\n"
        "docker compose -f laboratorio/docker-compose.yml down -v\n"
        "```\n\n"
        "## Reglas\n\n"
        f"{reglas}\n"
    )


def md_readme(datos: dict[str, Any]) -> str:
    """Genera el README del curso."""
    meta = datos["meta"]
    semanas = datos["semanas"]
    return (
        f"# {meta['titulo']}\n\n"
        f"{meta['subtitulo']}\n\n"
        f"- Autor: {meta['autor']}\n"
        f"- Duración: {meta['semanas']} semanas\n"
        f"- Versión: {meta.get('version', 1)} — {meta['fecha']}\n\n"
        "## Fuente de verdad\n\n"
        "`curso.yaml` es el descriptor del curso. Todo el material de este árbol\n"
        "(sílabo, plan semanal, guía, prácticas, evaluaciones y laboratorio) se\n"
        "genera desde él con:\n\n"
        "```bash\n"
        "python3 flujo_disenar_curso.py --curso cursos/"
        f"{meta['codigo']}/curso.yaml\n"
        "```\n\n"
        "Editar a mano un `.tex` generado se pierde en la siguiente ejecución: el\n"
        "cambio va al YAML.\n\n"
        "## Estructura\n\n"
        "```\n"
        "curso.yaml                 descriptor (fuente de verdad)\n"
        "plan_estudios/             silabo.pdf y plan_semanal.pdf\n"
        "docs/                      guia_estudiante.pdf\n"
        "practicas/                 un documento por semana (taller o practica)\n"
        "evaluaciones/              controles de fase y evaluacion_final\n"
        "laboratorio/               docker-compose.yml y README\n"
        "```\n\n"
        "## Calendario\n\n"
        "| Semana | Tema | Documento semanal |\n"
        "| --- | --- | --- |\n"
        + "\n".join(
            f'| {s["numero"]} | {s["titulo"]} | {etiqueta_semana(s)}: {s["practica"]["titulo"]} |'
            for s in semanas
        )
        + "\n\n## "
        + _texto(datos, "titulo_entregas", "Repositorio GitHub y entregas")
        + "\n\n"
        + (
            "\n".join(
                [
                    f"- Plataforma: {entregas.get('plataforma', '')}",
                    f"- Modalidad: {entregas.get('modalidad', '')}",
                    f"- Revisión: {entregas.get('cadencia', '')}",
                    f"- Corte: {entregas.get('corte', '')}",
                    "",
                    "### " + _texto(datos, "titulo_estructura", "Estructura del repositorio"),
                    "",
                ]
                + [f"- {e}" for e in entregas.get("estructura") or []]
                + ["", "### Reglas de entrega", ""]
                + [f"- {r}" for r in entregas.get("reglas") or []]
            )
            if (entregas := datos.get("entregas") or {})
            else "- Sin configuración de entregas en el descriptor."
        )
        + "\n\n## Reglas de uso\n\n"
        + "\n".join(f"- {r}" for r in datos.get("politicas") or [])
        + "\n"
    )


# ── Orquestación de escritura y compilación ───────────────────────────────────


def _epoch(meta: dict[str, Any]) -> int:
    """Devuelve el epoch fijado en `meta.fecha_iso` para PDFs reproducibles."""
    return int(
        datetime.fromisoformat(str(meta["fecha_iso"]))
        .replace(tzinfo=None)
        .timestamp()
    )


def _compilar(contenido: str, job: str, build: Path, destino: Path) -> dict[str, Any]:
    """Compila un documento y copia el PDF junto a su fuente si no hubo errores.

    Args:
        contenido: Documento LaTeX completo.
        job: Nombre del job de compilación (sin extensión).
        build: Directorio de compilación aislado.
        destino: Ruta del `.tex` final dentro del curso.

    Returns:
        Diccionario con `job`, `pdf`, `errores` y `overfull`.
    """
    resultado: dict[str, Any] = {"job": job, "pdf": None, "errores": [], "overfull": 0}
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        salida = compile_latex_code(
            contenido, job_name=job, output_dir=str(build), clean=False
        )
    log_path = build / f"{job}.log"
    if log_path.exists():
        log = log_path.read_text(encoding="utf-8", errors="ignore")
        resultado["errores"] = re.findall(r"^! (.+)$", log, re.M)
        resultado["overfull"] = len(re.findall(r"Overfull \\hbox", log))
    pdf = build / f"{job}.pdf"
    if salida.get("success") and pdf.exists() and not resultado["errores"]:
        shutil_copy(pdf, destino.with_suffix(".pdf"))
        resultado["pdf"] = str(destino.with_suffix(".pdf"))
    elif not resultado["errores"]:
        resultado["errores"] = [salida.get("error", "compilación fallida sin detalle")]
    return resultado


def shutil_copy(origen: Path, destino: Path) -> None:
    """Copia preservando metadatos del fichero."""
    import shutil

    shutil.copy2(origen, destino)


def generar(
    datos: dict[str, Any],
    salida: Path,
    solo: set[str],
    compilar: bool,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Genera y, si se pide, compila todos los artefactos del curso.

    Args:
        datos: Descriptor validado.
        salida: Directorio raíz del curso.
        solo: Subconjunto de artefactos a emitir.
        compilar: Si es False, escribe solo los `.tex` sin invocar pdflatex.

    Returns:
        Tupla `(artefactos, errores)`; los errores de compilación se acumulan.
    """
    meta = datos["meta"]
    codigo = _slug(meta["codigo"])
    build = RAIZ / ".tmp" / "latex_build" / f"curso_{codigo}"
    build.mkdir(parents=True, exist_ok=True)
    os.environ[FUENTE_FECHA] = str(_epoch(meta))

    dirs = {
        "plan_estudios": salida / "plan_estudios",
        "docs": salida / "docs",
        "practicas": salida / "practicas",
        "evaluaciones": salida / "evaluaciones",
        "laboratorio": salida / "laboratorio",
    }
    for ruta in dirs.values():
        ruta.mkdir(parents=True, exist_ok=True)

    pendientes: list[tuple[str, str, str, Path]] = []
    if "silabo" in solo:
        pendientes.append(("silabo", "silabo", tex_silabo(datos), dirs["plan_estudios"] / "silabo.tex"))
    if "plan_semanal" in solo:
        pendientes.append(
            ("plan_semanal", "plan_semanal", tex_plan_semanal(datos), dirs["plan_estudios"] / "plan_semanal.tex")
        )
    if "guia" in solo:
        pendientes.append(
            ("guia", "guia_estudiante", tex_guia(datos), dirs["docs"] / "guia_estudiante.tex")
        )
    if "practicas" in solo:
        for sem in datos["semanas"]:
            prefijo = "taller" if etiqueta_semana(sem) == "Taller" else "practica"
            job = f'{prefijo}_{sem["numero"]:02d}'
            pendientes.append(
                (
                    "practicas",
                    job,
                    tex_practica(datos, sem),
                    dirs["practicas"] / f"{job}.tex",
                )
            )
    if "controles" in solo:
        for control in datos.get("controles") or []:
            job = f'control_fase_{control["fase"]}'
            pendientes.append(
                (
                    "controles",
                    job,
                    tex_control(datos, control),
                    dirs["evaluaciones"] / f"{job}.tex",
                )
            )
    if "final" in solo:
        pendientes.append(
            (
                "final",
                "evaluacion_final",
                tex_evaluacion_final(datos),
                dirs["evaluaciones"] / "evaluacion_final.tex",
            )
        )

    artefactos: list[dict[str, Any]] = []
    errores: list[str] = []

    for artefacto, job, contenido, destino in pendientes:
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(contenido, encoding="utf-8")
        registro: dict[str, Any] = {
            "artefacto": artefacto,
            "job": job,
            "tex": str(destino),
            "pdf": None,
            "errores": [],
            "overfull": 0,
        }
        if compilar:
            resultado = _compilar(contenido, job, build, destino)
            registro.update(
                {
                    "pdf": resultado["pdf"],
                    "errores": resultado["errores"],
                    "overfull": resultado["overfull"],
                }
            )
            for mensaje in resultado["errores"]:
                errores.append(f"{job}: {mensaje}")
        artefactos.append(registro)

    if "rubrica" in solo:
        destino = dirs["evaluaciones"] / "rubrica_practica.yaml"
        destino.write_text(yaml_rubrica(datos), encoding="utf-8")
        artefactos.append({"artefacto": "rubrica", "tex": None, "pdf": None,
                           "ruta": str(destino), "errores": [], "overfull": 0})

    if "laboratorio" in solo:
        compose = dirs["laboratorio"] / "docker-compose.yml"
        compose.write_text(yaml_compose(datos), encoding="utf-8")
        readme_lab = dirs["laboratorio"] / "README.md"
        readme_lab.write_text(md_laboratorio(datos), encoding="utf-8")
        artefactos.append({"artefacto": "laboratorio", "tex": None, "pdf": None,
                           "ruta": str(compose), "errores": [], "overfull": 0})

    if "readme" in solo:
        readme = salida / "README.md"
        readme.write_text(md_readme(datos), encoding="utf-8")
        artefactos.append({"artefacto": "readme", "tex": None, "pdf": None,
                           "ruta": str(readme), "errores": [], "overfull": 0})

    return artefactos, errores


# ── CLI ───────────────────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    """Construye el parser de línea de comandos."""
    p = argparse.ArgumentParser(
        description="Genera el material completo de un curso desde su descriptor YAML."
    )
    p.add_argument("--curso", required=True, help="Ruta al descriptor curso.yaml")
    p.add_argument(
        "--salida",
        default=None,
        help="Directorio del curso (por defecto, el del descriptor)",
    )
    p.add_argument(
        "--solo",
        default="",
        help="Lista de artefactos separados por coma: " + ", ".join(ARTEFACTOS),
    )
    p.add_argument("--sin-compilar", action="store_true", help="Escribe los .tex sin invocar pdflatex")
    p.add_argument("--json", action="store_true", help="Emite un único objeto JSON por stdout")
    return p


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada.

    Args:
        argv: Argumentos de línea de comandos (por defecto, sys.argv[1:]).

    Returns:
        Código de salida según el contrato del módulo.
    """
    args = _parser().parse_args(argv)
    ruta = Path(args.curso).resolve()
    salida = Path(args.salida).resolve() if args.salida else ruta.parent

    try:
        datos = cargar_descriptor(ruta)
    except FileNotFoundError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    problemas = validar(datos)
    if problemas:
        if args.json:
            print(json.dumps({"status": "descriptor_invalido", "problemas": problemas},
                             ensure_ascii=False, indent=2))
        else:
            print("[error] Descriptor inválido:", file=sys.stderr)
            for problema in problemas:
                print(f"  - {problema}", file=sys.stderr)
        return 3

    solo = {s.strip() for s in args.solo.split(",") if s.strip()} or set(ARTEFACTOS)
    desconocidos = solo - set(ARTEFACTOS)
    if desconocidos:
        print(f"[error] artefactos desconocidos: {sorted(desconocidos)}", file=sys.stderr)
        return 1

    try:
        artefactos, errores = generar(datos, salida, solo, not args.sin_compilar)
    except OSError as exc:
        print(f"[error] escritura: {exc}", file=sys.stderr)
        return 5

    compilados = sum(1 for a in artefactos if a.get("pdf"))
    salida_json = {
        "status": "error" if errores else "ok",
        "curso": datos["meta"]["codigo"],
        "salida": str(salida),
        "artefactos": artefactos,
        "tex_escritos": sum(1 for a in artefactos if a.get("tex")),
        "compilados": compilados,
        "errores": errores,
    }

    if args.json:
        print(json.dumps(salida_json, ensure_ascii=False, indent=2))
    else:
        print(f"Curso: {datos['meta']['codigo']} -> {salida}")
        print(f"Documentos LaTeX escritos: {salida_json['tex_escritos']}")
        if not args.sin_compilar:
            print(f"PDF compilados: {compilados}")
        for artefacto in artefactos:
            estado = "ok" if not artefacto["errores"] else "ERROR"
            destino = artefacto.get("pdf") or artefacto.get("tex") or artefacto.get("ruta")
            print(f"  [{estado}] {artefacto['artefacto']:<12} {destino}")
        if errores:
            print("\nErrores de compilación:", file=sys.stderr)
            for mensaje in errores:
                print(f"  - {mensaje}", file=sys.stderr)

    return 4 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
