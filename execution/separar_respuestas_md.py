#!/usr/bin/env python3
"""Separa un markdown con respuestas en español en fuente + solucionario.

El conversor `md_a_html.py` entiende `**Answer:**`, `**Hint:**` y
`**Explanation:**`. Un cuestionario redactado con `**Respuesta:**`,
`**Pista:**` y `**Explicación:**` no se reconoce: esas líneas se concatenan a la
última opción y la clave se filtraría en la variante alumno. Este script
transforma ese markdown en los dos archivos que el conversor sí acepta:

* `<stem>.md` — solo enunciado y opciones (se sobrescribe en sitio).
* `<stem>_respuestas.md` — mismo examen más `**Answer:**`, `**Hint:**` y
  `**Explanation:**` con sus viñetas.
* `<stem>_original_con_respuestas.md` — copia íntegra del original, para que
  nada se pierda. Solo se escribe si no existe.

La validación ocurre **antes** de escribir en destino: ambos textos se prueban
en un directorio temporal con `md_a_html.cargar_clave()`. Si el conversor no
acepta la pareja, no se toca ningún archivo del curso.

Uso:
    python3 execution/separar_respuestas_md.py --fuente ROL_ROJO_CUESTIONARIO.md
    python3 execution/separar_respuestas_md.py --fuente ROL_ROJO_CUESTIONARIO.md --json --forzar

Códigos de salida: 0 ok · 1 E/S · 3 validación fallida ·
4 no es separable (ya está separado o formato imprevisto) ·
5 el solucionario ya existe y no se pasó --forzar.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import md_a_html as M  # noqa: E402  (capa 3: contrato único del formato)

PREGUNTA = re.compile(r"^##\s+(?:Pregunta|Question)\s+(\d+)\s*$", re.IGNORECASE)
OPCION = re.compile(r"^\s*[-*]\s+([A-Fa-f])[.)]\s+(.+?)\s*$")
RESPUESTA_ES = re.compile(r"^\*\*Respuesta:\*\*\s*([A-Za-z])(?:\.\s*|\s+)(.*)$")
RESPUESTA_SOLO = re.compile(r"^\*\*Respuesta:\*\*\s*([A-Za-z])\b\s*$")
PISTA_ES = re.compile(r"^\*\*Pista:\*\*\s*(.*)$")
EXPLICACION_ES = re.compile(r"^\*\*Explicaci[oó]n:\*\*\s*$")
VIETA_EXP = re.compile(r"^\s*[-*]\s+[A-Fa-f]\s*[✓✗]\s*(.*)$")
SEPARADOR = re.compile(r"^\s*---\s*$")
MARCA_INGLES = re.compile(r"^\*\*(?:Answer|Hint|Explanation):\*\*", re.MULTILINE)
MAX_OPCIONES = 6
MIN_OPCIONES = 2


class SeparacionError(Exception):
    """Fallo categorizado; `codigo` es el código de salida del script."""

    def __init__(self, mensaje: str, codigo: int):
        super().__init__(mensaje)
        self.codigo = codigo


def es_separable(texto: str) -> bool:
    """True si hay marcas en español y ninguna en inglés."""
    return (
        "**Respuesta:**" in texto
        and "**Pista:**" in texto
        and not MARCA_INGLES.search(texto)
    )


def parsear(texto: str) -> tuple[list[str], list[dict]]:
    """Lee el markdown en español y devuelve (cabecera, preguntas)."""
    lineas = texto.splitlines()
    indice = next((i for i, l in enumerate(lineas) if PREGUNTA.match(l)), len(lineas))
    cabecera = [l for l in lineas[:indice] if l.strip()]
    if cabecera and SEPARADOR.match(cabecera[-1]):
        cabecera.pop()

    preguntas: list[dict] = []
    actual: dict | None = None
    estado = "enunciado"

    def cerrar() -> None:
        nonlocal actual
        if actual is not None:
            actual["enunciado"] = " ".join(actual["enunciado"]).strip()
            actual["texto_respuesta"] = " ".join(actual["texto_respuesta"]).strip()
            actual["pista"] = " ".join(actual["pista"]).strip()
            preguntas.append(actual)
            actual = None

    for linea in lineas:
        inicio = PREGUNTA.match(linea)
        if inicio:
            cerrar()
            actual = {
                "numero": int(inicio.group(1)),
                "enunciado": [],
                "opciones": [],
                "respuesta": None,
                "texto_respuesta": [],
                "pista": [],
                "explicacion": [],
            }
            estado = "enunciado"
            continue
        if actual is None or SEPARADOR.match(linea) or not linea.strip():
            continue

        if estado == "enunciado":
            opcion = OPCION.match(linea)
            if opcion:
                actual["opciones"].append(
                    {"letra": opcion.group(1).upper(), "texto": opcion.group(2).strip()}
                )
                estado = "opciones"
            else:
                respuesta = RESPUESTA_ES.match(linea) or RESPUESTA_SOLO.match(linea)
                if respuesta:
                    actual["respuesta"] = respuesta.group(1).upper()
                    if respuesta.lastindex and respuesta.lastindex >= 2 and respuesta.group(2):
                        actual["texto_respuesta"].append(respuesta.group(2).strip())
                    estado = "respuesta"
                else:
                    actual["enunciado"].append(linea.strip())
            continue

        if estado == "opciones":
            respuesta = RESPUESTA_ES.match(linea) or RESPUESTA_SOLO.match(linea)
            if respuesta:
                actual["respuesta"] = respuesta.group(1).upper()
                if respuesta.lastindex and respuesta.lastindex >= 2 and respuesta.group(2):
                    actual["texto_respuesta"].append(respuesta.group(2).strip())
                estado = "respuesta"
                continue
            pista = PISTA_ES.match(linea)
            if pista:
                actual["pista"].append(pista.group(1).strip())
                estado = "pista"
                continue
            if EXPLICACION_ES.match(linea):
                estado = "explicacion"
                continue
            opcion = OPCION.match(linea)
            if opcion:
                actual["opciones"].append(
                    {"letra": opcion.group(1).upper(), "texto": opcion.group(2).strip()}
                )
            elif actual["opciones"]:
                actual["opciones"][-1]["texto"] += " " + linea.strip()
            else:
                actual["enunciado"].append(linea.strip())
            continue

        if estado in {"respuesta", "pista"}:
            pista = PISTA_ES.match(linea)
            if pista:
                actual["pista"].append(pista.group(1).strip())
                estado = "pista"
                continue
            if EXPLICACION_ES.match(linea):
                estado = "explicacion"
                continue
            if estado == "respuesta":
                actual["texto_respuesta"].append(linea.strip())
            else:
                actual["pista"].append(linea.strip())
            continue

        # estado == "explicacion": las viñetas se preservan, no se reinterpretan
        # como opciones.
        actual["explicacion"].append(linea.strip())

    cerrar()
    return cabecera, preguntas


def validar(preguntas: list[dict]) -> list[str]:
    """Problemas que impiden separar con seguridad."""
    problemas: list[str] = []
    if not preguntas:
        return ["no se encontró ninguna pregunta"]
    numeros = [p["numero"] for p in preguntas]
    if numeros != list(range(1, len(preguntas) + 1)):
        problemas.append(f"numeración no consecutiva: {numeros}")
    for p in preguntas:
        n = p["numero"]
        letras = [o["letra"] for o in p["opciones"]]
        if not MIN_OPCIONES <= len(letras) <= MAX_OPCIONES:
            problemas.append(f"pregunta {n}: {len(letras)} opciones (se requieren 2..6)")
        if len(set(letras)) != len(letras):
            problemas.append(f"pregunta {n}: letras de opción repetidas {letras}")
        if not p["enunciado"]:
            problemas.append(f"pregunta {n}: enunciado vacío")
        if not p["respuesta"]:
            problemas.append(f"pregunta {n}: falta **Respuesta:**")
        elif p["respuesta"] not in letras:
            problemas.append(
                f"pregunta {n}: la respuesta {p['respuesta']} no está entre las opciones {letras}"
            )
        if not p["explicacion"]:
            problemas.append(f"pregunta {n}: falta **Explicación:**")
        elif not any(VIETA_EXP.match(l) for l in p["explicacion"]):
            problemas.append(f"pregunta {n}: la explicación no trae viñetas A ✓/✗")
    return problemas


def titulo_de(cabecera: list[str], por_defecto: str = "Cuestionario") -> str:
    for linea in cabecera:
        if linea.startswith("# "):
            return linea[2:].strip()
    return por_defecto


def armar_fuente(cabecera: list[str], preguntas: list[dict]) -> str:
    """Examen limpio: enunciado y opciones, sin clave ni explicación."""
    partes = list(cabecera)
    for p in preguntas:
        partes.extend(["", f"## Pregunta {p['numero']}", "", p["enunciado"], ""])
        partes.extend(f"- {o['letra']}. {o['texto']}" for o in p["opciones"])
        partes.append("")
    return "\n".join(partes).rstrip() + "\n"


def armar_respuestas(cabecera: list[str], preguntas: list[dict]) -> str:
    """Solucionario en el formato que `md_a_html.py` ya entiende."""
    titulo = titulo_de(cabecera)
    partes = [f"# {titulo} — respuestas", "", f"> {len(preguntas)} preguntas", ""]
    for p in preguntas:
        partes.extend(["", f"## Pregunta {p['numero']}", "", p["enunciado"], ""])
        partes.extend(f"- {o['letra']}. {o['texto']}" for o in p["opciones"])
        partes.append("")
        texto = p["texto_respuesta"]
        respuesta = f"**Answer:** {p['respuesta']}" + (f". {texto}" if texto else "")
        partes.append(respuesta)
        if p["pista"]:
            partes.append(f"**Hint:** {' '.join(p['pista'])}")
        if p["explicacion"]:
            partes.append("**Explanation:**")
            partes.extend(p["explicacion"])
        partes.append("")
    return "\n".join(partes).rstrip() + "\n"


def _escribir_atomico(ruta: Path, contenido: str) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fd, temporal = tempfile.mkstemp(dir=ruta.parent, prefix=f".{ruta.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as manejador:
            manejador.write(contenido)
        os.replace(temporal, ruta)
    except BaseException:
        if os.path.exists(temporal):
            os.unlink(temporal)
        raise


def _sha256(ruta: Path) -> str:
    import hashlib

    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def separar(fuente: Path, forzar: bool = False) -> dict:
    """Transforma el archivo y devuelve un informe sin exponer la clave."""
    fuente = fuente.resolve()
    if not fuente.is_file():
        raise SeparacionError(f"no existe la fuente: {fuente}", 4)
    original = fuente.read_text(encoding="utf-8")
    if not es_separable(original):
        raise SeparacionError(
            "la fuente ya está separada o no usa **Respuesta:**/**Pista:**/**Explicación:**", 4
        )

    cabecera, preguntas = parsear(original)
    problemas = validar(preguntas)
    if problemas:
        raise SeparacionError("; ".join(problemas), 3)

    limpia = armar_fuente(cabecera, preguntas)
    solucionario = armar_respuestas(cabecera, preguntas)

    # Validación con el contrato real, en temporal: si falla, no se escribe nada.
    with tempfile.TemporaryDirectory(dir=RAIZ / ".tmp") as temporal:
        tmp = Path(temporal)
        f_limpia, f_resp = tmp / "fuente.md", tmp / "respuestas.md"
        f_limpia.write_text(limpia, encoding="utf-8")
        f_resp.write_text(solucionario, encoding="utf-8")
        try:
            datos = M.cargar_clave(f_limpia, f_resp)
        except (ValueError, FileNotFoundError) as exc:
            raise SeparacionError(f"el conversor rechazó la separación: {exc}", 3) from exc
        if datos["n_preguntas"] != len(preguntas) or len(datos["clave"]) != len(preguntas):
            raise SeparacionError("el conversor no recuperó la clave de todas las preguntas", 3)

    respuestas = fuente.with_name(f"{fuente.stem}_respuestas.md")
    backup = fuente.with_name(f"{fuente.stem}_original_con_respuestas.md")
    if respuestas.exists() and not forzar:
        raise SeparacionError(f"ya existe {respuestas.name}; usa --forzar para sobrescribirla", 5)

    if not backup.exists():
        _escribir_atomico(backup, original)
    _escribir_atomico(respuestas, solucionario)
    _escribir_atomico(fuente, limpia)

    return {
        "status": "ok",
        "code": 0,
        "fuente": str(fuente.relative_to(RAIZ)),
        "respuestas": str(respuestas.relative_to(RAIZ)),
        "respaldo": str(backup.relative_to(RAIZ)),
        "preguntas": len(preguntas),
        "sha256": {
            "fuente": _sha256(fuente),
            "respuestas": _sha256(respuestas),
            "respaldo": _sha256(backup),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fuente", required=True, help="Markdown con respuestas en español.")
    parser.add_argument("--forzar", action="store_true", help="Sobrescribe un solucionario previo.")
    parser.add_argument("--json", action="store_true", help="Salida JSON.")
    args = parser.parse_args()
    try:
        resultado = separar(Path(args.fuente), forzar=args.forzar)
    except SeparacionError as exc:
        resultado = {"status": "error", "code": exc.codigo, "message": str(exc)}
    except OSError as exc:
        resultado = {"status": "error", "code": 1, "message": str(exc)}
    if args.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
    else:
        if resultado["code"] == 0:
            print(f"Separado: {resultado['fuente']} ({resultado['preguntas']} preguntas)")
            print(f"  solucionario: {resultado['respuestas']}")
            print(f"  respaldo:     {resultado['respaldo']}")
        else:
            print(f"FALLA ({resultado['code']}): {resultado['message']}", file=sys.stderr)
    return int(resultado["code"])


if __name__ == "__main__":
    sys.exit(main())
