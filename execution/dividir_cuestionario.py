#!/usr/bin/env python3
"""Capa 3: divide un cuestionario canónico en fuente (alumno) + respuestas.

El formato canónico (el que sale del banco de preguntas) trae la clave dentro:
`**Answer:**`, `**Hint:**` y `**Explanation:**` después de cada bloque. El
conversor NO acepta eso como fuente —`md_a_html.cargar_clave()` rechaza una
fuente con `**Answer:**` porque «parece un archivo de respuestas»— y además
`_parsear_cuestionario()` pegaría las líneas de `**Hint:**`/`**Explanation:**`
al texto de la última opción, que es exactamente el tipo de fuga silenciosa que
este script existe para evitar.

Por eso el canónico se parte en dos archivos:

  - `<fuente>.md`      → front matter + preguntas y opciones, SIN clave.
  - `<fuente>_respuestas.md` → el canónico tal cual (es ya el formato que lee
    `_parsear_respuestas`, con pistas y explicaciones).

La división es una proyección, no una reescritura: se valida que
fuente+respuestas reconstruyan el canónico (mismo número de preguntas, mismo
enunciado, mismas opciones y misma clave) y que `cargar_clave()` lo acepte.
Si algo no cuadra, no escribe nada.

Única excepción a "tal cual": los signos de ancho completo que el banco deja
a veces (U+FF1B, punto y coma de ancho completo) se normalizan a su equivalente ASCII (`; `). No es
cosmético: `execution/verificar_texto.py` los marca como corrupción de prosa y
la auditoría del repo falla por ellos (pasó con Rojo, Azul y Legal). Se informa
cuántos se sustituyeron.

La segunda excepción son las etiquetas en español (`**Respuesta:**`, `**Pista:**`,
`**Explicación:**`): se traducen a las inglesas que reconoce el parser. Tampoco es
cosmético: una etiqueta desconocida no falla, se pega al texto de la última opción
y la clave acaba en el HTML del alumno. Se cuentan en `normalizaciones` como las
anteriores, y en Lab I esa traducción se hizo a mano (no reproducible).

Uso:
    python3 execution/dividir_cuestionario.py --canonico ROL_AZUL_Cuestionario.md
    python3 execution/dividir_cuestionario.py --canonico X.md --dry-run --json
    python3 execution/dividir_cuestionario.py --canonico X.md --forzar

Códigos de salida: 0 ok · 1 error de E/S · 3 canónico inválido (o ya dividido).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EJECUCION = Path(__file__).resolve().parent
sys.path.insert(0, str(EJECUCION))
import md_a_html  # noqa: E402  (capa 3: el parser es la única definición del formato)

TITULO = re.compile(r"(?m)^#\s+(.+?)\s*$")

ANCHO_COMPLETO = {"\uff1b": "; "}

# El banco de preguntas emite a veces las etiquetas en español (los cursos que se
# redactaron antes de fijar el formato en inglés). El parser solo reconoce las
# inglesas, y una etiqueta desconocida NO falla: `_parsear_cuestionario()` pega la
# respuesta, la pista y toda la explicación al texto de la última opción, así que
# la clave se colaría en el HTML del alumno. Traducirlas aquí, en la única puerta
# de entrada del canónico, evita esa fuga silenciosa.
ETIQUETAS = {
    "**Respuesta:**": "**Answer:**",
    "**Pista:**": "**Hint:**",
    "**Explicación:**": "**Explanation:**",
}


def _normalizar(texto: str) -> tuple[str, int]:
    """Sustituye puntuación de ancho completo y etiquetas ES; devuelve (texto, nº)."""
    total = 0
    for malo, bueno in ANCHO_COMPLETO.items():
        total += texto.count(malo)
        texto = texto.replace(malo, bueno)
    for malo, bueno in ETIQUETAS.items():
        total += texto.count(malo)
        texto = texto.replace(malo, bueno)
    return texto, total


def _titulo(cuerpo: str) -> str:
    """Primer `# ...` del cuerpo; el canónico lo trae antes de la primera pregunta."""
    coincidencia = TITULO.search(cuerpo)
    return coincidencia.group(1).strip() if coincidencia else ""


def validar_preguntas(preguntas: list[dict]) -> list[str]:
    """Reglas del canónico: numeración 1..N, opciones distintas y clave válida."""
    problemas: list[str] = []
    if not preguntas:
        return ["el canónico no tiene ninguna pregunta (`## pregunta N`)"]

    numeros = [p["numero"] for p in preguntas]
    esperados = list(range(1, len(preguntas) + 1))
    if numeros != esperados:
        problemas.append(f"la numeración no es 1..{len(preguntas)}: {numeros}")

    for pregunta in preguntas:
        numero = pregunta["numero"]
        if not pregunta["enunciado"]:
            problemas.append(f"pregunta {numero}: sin enunciado")
        letras = [o["letra"] for o in pregunta["opciones"]]
        if len(letras) < 2:
            problemas.append(f"pregunta {numero}: menos de dos opciones")
        if len(set(letras)) != len(letras):
            problemas.append(f"pregunta {numero}: letras de opción repetidas {letras}")
        for opcion in pregunta["opciones"]:
            if not opcion["texto"]:
                problemas.append(f"pregunta {numero}: opción {opcion['letra']} vacía")
        respuesta = pregunta.get("respuesta")
        if respuesta is None:
            problemas.append(
                f"pregunta {numero}: sin `**Answer:**` (¿es un cuestionario y no un "
                "archivo de respuestas?)"
            )
        elif respuesta not in letras:
            problemas.append(
                f"pregunta {numero}: la respuesta {respuesta} no está entre las "
                f"opciones {letras}"
            )
    return problemas


def _front_matter(
    titulo: str, curso: str, grupos: int, justificar: list[int], evidencia: list[int] = ()
) -> str:
    lineas = [
        "---",
        f"curso: {curso}",
        "tipo: cuestionario",
        f"titulo: {json.dumps(titulo, ensure_ascii=False)}",
        f"grupos: {grupos}",
    ]
    if justificar:
        lineas.append(f"justificacion_items: {json.dumps(sorted(justificar))}")
    if evidencia:
        lineas.append(f"justificacion_evidencia: {json.dumps(sorted(evidencia))}")
    lineas.append("---")
    return "\n".join(lineas) + "\n"


def _evidencia_canonica(meta: dict, justificar: list[int]) -> list[int]:
    """Lee `justificacion_evidencia` del canónico y la valida contra las preguntas.

    Se declara en el canónico para que sobreviva a una nueva división; si nombra
    una pregunta que no exige justificación, el canónico está mal y se falla.
    """
    cruda = meta.get("justificacion_evidencia")
    if cruda is None:
        return []
    if not isinstance(cruda, list):
        raise ValueError(
            f"`justificacion_evidencia` debe ser una lista de números: {cruda!r}"
        )
    items: list[int] = []
    for valor in cruda:
        if isinstance(valor, bool) or not isinstance(valor, int):
            raise ValueError(
                f"`justificacion_evidencia` tiene un valor no entero: {valor!r}"
            )
        items.append(valor)
    if len(set(items)) != len(items):
        raise ValueError(f"`justificacion_evidencia` repite preguntas: {items}")
    sin_justificar = sorted(set(items) - set(justificar))
    if sin_justificar:
        raise ValueError(
            "`justificacion_evidencia` exime de copia preguntas que no exigen "
            f"justificación: {sin_justificar}"
        )
    return sorted(set(items))


def _cuerpo_alumno(titulo: str, preguntas: list[dict]) -> str:
    partes = [f"# {titulo}", "", "---", ""]
    for pregunta in preguntas:
        partes.append(f"## Question {pregunta['numero']}")
        partes.append("")
        partes.append(pregunta["enunciado"])
        partes.append("")
        for opcion in pregunta["opciones"]:
            partes.append(f"- {opcion['letra']}. {opcion['texto']}")
            partes.append("")
        if pregunta.get("justificacion"):
            partes.append(f"**Justificación:** {pregunta['justificacion']}")
            partes.append("")
        partes.append("---")
        partes.append("")
    return "\n".join(partes).rstrip("\n") + "\n"


def dividir(canonico: str, curso: str, grupos: int, titulo_documento: str | None = None) -> dict:
    """Devuelve `{fuente, respuestas, clave, titulo, n_preguntas}` sin tocar disco."""
    canonico, normalizaciones = _normalizar(canonico)
    if not md_a_html.MARCA_RESPUESTAS.search(canonico):
        raise ValueError(
            "el canónico no contiene `**Answer:**` (ni `**Respuesta:**`): ya está "
            "dividido o no es el archivo completo (no se sobrescribe a ciegas)"
        )

    meta, cuerpo = md_a_html._leer_front_matter(canonico)
    titulo = _titulo(cuerpo)
    if not titulo:
        raise ValueError("el canónico no tiene un título `# ...`")
    # El `# ...` del canónico es el nombre interno del banco; el título que ve el
    # alumno puede ser otro (en Lab I se editaba a mano tras dividir). Separarlos
    # aquí hace que esa decisión sea explícita y sobreviva a una nueva división.
    titulo_doc = (titulo_documento or titulo).strip()
    preguntas = md_a_html._parsear_respuestas(cuerpo)
    problemas = validar_preguntas(preguntas)
    if problemas:
        raise ValueError("; ".join(problemas))

    clave = {p["numero"]: p["respuesta"] for p in preguntas}
    justificar = [p["numero"] for p in preguntas if p.get("justificacion")]
    evidencia = _evidencia_canonica(meta, justificar)
    fuente = (
        _front_matter(titulo_doc, curso, grupos, justificar, evidencia)
        + "\n"
        + _cuerpo_alumno(titulo, preguntas)
    )
    return {
        "fuente": fuente,
        "respuestas": canonico if canonico.endswith("\n") else canonico + "\n",
        "clave": clave,
        "titulo": titulo,
        "titulo_documento": titulo_doc,
        "n_preguntas": len(preguntas),
        "justificacion_evidencia": evidencia,
        "normalizaciones": normalizaciones,
    }


def _verificar(
    fuente: str,
    respuestas: str,
    clave: dict[int, str],
    evidencia: list[int] | None = None,
) -> None:
    """El canónico se reconstruye desde lo escrito, no desde lo leído."""
    if md_a_html.MARCA_RESPUESTAS.search(fuente):
        raise ValueError("la fuente generada contiene `**Answer:**` (fuga)")
    meta, cuerpo = md_a_html._leer_front_matter(fuente)
    preguntas = md_a_html._parsear_cuestionario(cuerpo)
    if not preguntas:
        raise ValueError("la fuente generada no se puede volver a parsear")
    _, cuerpo_resp = md_a_html._leer_front_matter(respuestas)
    del_canonico = md_a_html._parsear_respuestas(cuerpo_resp)
    problemas, clave_resp = md_a_html._cruzar(preguntas, del_canonico)
    if problemas:
        raise ValueError("ida y vuelta rota: " + "; ".join(problemas))
    if clave_resp != clave:
        raise ValueError(f"ida y vuelta rota: clave {clave_resp} != {clave}")
    if meta.get("titulo") is None or meta.get("grupos") is None:
        raise ValueError("la fuente generada perdió titulo/grupos del front matter")
    if evidencia is not None:
        leida = meta.get("justificacion_evidencia") or []
        if leida != sorted(evidencia):
            raise ValueError(
                f"ida y vuelta rota: evidencia {leida} != {sorted(evidencia)}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Divide un cuestionario canónico en fuente (alumno) y respuestas."
    )
    parser.add_argument("--canonico", required=True, help="Markdown completo con `**Answer:**`.")
    parser.add_argument("--fuente", default=None, help="Salida de la fuente (por defecto, el canónico).")
    parser.add_argument("--respuestas", default=None, help="Salida de respuestas (por defecto, hermano).")
    parser.add_argument("--curso", default="CYBERSEGURIDAD", help="Valor de `curso` en el front matter.")
    parser.add_argument("--grupos", type=int, default=4, help="Valor de `grupos` (1..20).")
    parser.add_argument(
        "--titulo",
        default=None,
        help="Título que ve el alumno (front matter). Por defecto, el `# ...` del canónico.",
    )
    parser.add_argument("--forzar", action="store_true", help="Sobrescribe archivos existentes.")
    parser.add_argument("--dry-run", action="store_true", help="Valida sin escribir.")
    parser.add_argument("--json", action="store_true", help="Salida JSON.")
    args = parser.parse_args()

    if not (1 <= args.grupos <= 20):
        print("error: --grupos debe estar entre 1 y 20", file=sys.stderr)
        return 3

    canonico_ruta = Path(args.canonico).resolve()
    fuente_ruta = Path(args.fuente).resolve() if args.fuente else canonico_ruta
    respuestas_ruta = (
        Path(args.respuestas).resolve()
        if args.respuestas
        else canonico_ruta.with_name(canonico_ruta.stem + "_respuestas.md")
    )

    try:
        texto = canonico_ruta.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        resultado = dividir(texto, args.curso, args.grupos, args.titulo)
        _verificar(
            resultado["fuente"],
            resultado["respuestas"],
            resultado["clave"],
            resultado["justificacion_evidencia"],
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    if respuestas_ruta == fuente_ruta:
        print("error: --fuente y --respuestas no pueden ser el mismo archivo", file=sys.stderr)
        return 3
    if not args.forzar:
        if respuestas_ruta.exists() and respuestas_ruta.read_text(encoding="utf-8") != resultado["respuestas"]:
            print(
                f"error: {respuestas_ruta} existe con otro contenido; usar --forzar",
                file=sys.stderr,
            )
            return 3
        if fuente_ruta != canonico_ruta and fuente_ruta.exists():
            print(f"error: {fuente_ruta} existe; usar --forzar", file=sys.stderr)
            return 3

    resumen = {
        "canonico": str(canonico_ruta),
        "fuente": str(fuente_ruta),
        "respuestas": str(respuestas_ruta),
        "titulo": resultado["titulo"],
        "titulo_documento": resultado["titulo_documento"],
        "n_preguntas": resultado["n_preguntas"],
        "clave": " ".join(resultado["clave"][n] for n in sorted(resultado["clave"])),
        "justificacion_evidencia": resultado["justificacion_evidencia"],
        "normalizaciones": resultado["normalizaciones"],
        "dry_run": args.dry_run,
    }

    if not args.dry_run:
        try:
            respuestas_ruta.write_text(resultado["respuestas"], encoding="utf-8")
            fuente_ruta.write_text(resultado["fuente"], encoding="utf-8")
            verificado = md_a_html.cargar_clave(fuente_ruta, respuestas_ruta)
        except (OSError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        resumen["cargar_clave"] = {
            "n_preguntas": verificado["n_preguntas"],
            "clave": " ".join(
                verificado["clave"][n] for n in sorted(verificado["clave"])
            ),
        }

    if args.json:
        print(json.dumps(resumen, ensure_ascii=False, indent=2))
    else:
        estado = "validado (dry-run)" if args.dry_run else "escrito"
        print(f"{estado}: {resultado['titulo']} — {resultado['n_preguntas']} preguntas")
        print(f"  fuente:     {fuente_ruta}")
        print(f"  respuestas: {respuestas_ruta}")
        print(f"  clave:      {resumen['clave']}")
        if resumen["normalizaciones"]:
            print(
                f"  normalizado: {resumen['normalizaciones']} sustitución(es): "
                "ancho completo (U+FF1B → '; ') y/o etiquetas ES → EN"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
