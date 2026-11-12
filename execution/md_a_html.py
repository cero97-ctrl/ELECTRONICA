#!/usr/bin/env python3
r"""
md_a_html.py — Convierte un cuestionario Markdown a HTML determinista (Layer 3).

Contrato:
  - Entrada: un .md con front matter opcional y preguntas en el formato
    `## Question N` (o `## Pregunta N`) seguidas de opciones `- A. texto`.
  - Clave: o bien `clave:` en el front matter, o bien un archivo de respuestas
    aparte (`--respuestas`, típicamente `<fuente>_respuestas.md`) con líneas
    `**Answer:** X. ...`. Si se dan las dos, deben coincidir exactamente: dos
    fuentes de verdad que divergen en silencio son peores que ninguna.
  - El archivo de respuestas se valida contra la fuente (mismo número de
    preguntas, mismo enunciado y mismas opciones) antes de usar su clave, así
    que una copia desactualizada falla ruidosamente en vez de corregir mal.
  - Salida: HTML autocontenido (CSS inline, sin CDN ni recursos externos),
    en dos variantes: `_alumno.html` (sin clave) y `_docente.html` (con clave).
  - Determinismo: el mismo .md produce exactamente los mismos bytes. No hay
    timestamps, aleatoriedad ni orden dependiente del sistema de ficheros.

Reglas de seguridad:
  - Solo escribe dentro de `cursos/<CURSO>/evaluaciones/web/` (nunca en
    `fuentes/`), y exige que git ignore la ruta de salida. Un examen es
    material privado en un repo público.

Uso:
    python3 execution/md_a_html.py --fuente <cuestionario.md> --check
    python3 execution/md_a_html.py --fuente <cuestionario.md> --variantes alumno
    python3 execution/md_a_html.py --fuente <cuestionario.md> --variantes alumno,docente
    python3 execution/md_a_html.py --fuente <cuestionario.md> \\
        --respuestas <cuestionario_respuestas.md> --variantes alumno,docente
    python3 execution/md_a_html.py --fuente <cuestionario.md> --dry-run --json

Códigos de salida:
    0 -> ok
    1 -> error de E/S
    3 -> fuente inválida (formato, numeración, opciones, clave mal formada) o
         respuestas que no coinciden con la fuente
    4 -> se pidió la variante docente y no hay clave (ni `clave:` ni --respuestas)
    5 -> salida rechazada por la barrera de rutas o por git
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from string import Template

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from estilo_infografia import PALETA  # noqa: E402

FRONT_MATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
PREGUNTA = re.compile(r"^##\s+(?:Question|Pregunta)\s+(\d+)\s*$", re.IGNORECASE)
OPCION = re.compile(r"^\s*[-*]\s+([A-Za-z])[.)]\s+(.+?)\s*$")
SEPARADOR = re.compile(r"^\s*---\s*$")
RESPUESTA = re.compile(r"^\*\*Answer:\*\*\s*([A-Za-z])\b")
PISTA = re.compile(r"^\*\*Hint:\*\*\s*(.*)$")
EXPLICACION = re.compile(r"^\*\*Explanation:\*\*\s*$")
MARCA_RESPUESTAS = re.compile(r"^\*\*Answer:\*\*", re.MULTILINE)
VARIANTES = ("alumno", "docente")
MAX_OPCIONES = 6
MIN_OPCIONES = 2

CSS = Template(
    """
:root {
  --fondo: #$fondoOscuro;
  --marca: #$verdeTurquesa;
  --azul: #$azulNoche;
  --azul-medio: #$azulMedio;
  --cyan: #$cyanNeon;
  --verde: #$verdeSignal;
  --naranja: #$naranjaVivo;
  --rojo: #$rojoAlerta;
  --papel: #$grisPapel;
  --linea: #$grisLinea;
  --texto-suave: #$grisTexto;
  --nota: #$amarilloNota;
  --codigo: #$codigoFondo;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  background: var(--papel);
  color: #1d2733;
  font-family: "Source Sans Pro", "Segoe UI", system-ui, sans-serif;
  line-height: 1.55;
}
.banda {
  background: linear-gradient(135deg, var(--fondo) 0%, var(--azul) 70%, var(--marca) 100%);
  color: #f7fbff;
  padding: 2.2rem 1.5rem 1.8rem;
}
.banda .curso {
  margin: 0 0 .3rem;
  letter-spacing: .18em;
  text-transform: uppercase;
  font-size: .78rem;
  color: var(--cyan);
}
.banda h1 { margin: 0; font-size: clamp(1.5rem, 4vw, 2.3rem); font-weight: 600; }
.banda .meta { margin: .7rem 0 0; color: #d7e6f5; font-size: .92rem; }
main { max-width: 900px; margin: 0 auto; padding: 1.6rem 1.1rem 4rem; }
.aviso {
  border-left: 5px solid var(--nota);
  background: #fff8e1;
  padding: .8rem 1rem;
  border-radius: 6px;
  margin: 0 0 1.4rem;
  font-size: .92rem;
}
.pregunta {
  background: #fff;
  border: 1px solid var(--linea);
  border-radius: 12px;
  padding: 1.1rem 1.2rem 1.2rem;
  margin: 0 0 1.2rem;
  box-shadow: 0 1px 3px rgba(13, 27, 42, .06);
}
.pregunta h2 {
  margin: 0 0 .6rem;
  font-size: 1.05rem;
  color: var(--azul);
  display: flex;
  gap: .55rem;
  align-items: baseline;
  flex-wrap: wrap;
}
.pregunta h2 .num {
  display: inline-grid;
  place-items: center;
  min-width: 1.9rem;
  height: 1.9rem;
  border-radius: 50%;
  background: var(--azul);
  color: #fff;
  font-size: .85rem;
}
.pregunta h2 .puntos { color: var(--texto-suave); font-weight: 400; font-size: .85rem; }
.enunciado { margin: 0 0 .9rem; }
fieldset { border: 0; margin: 0; padding: 0; }
.sr-only {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
  overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
}
.opcion {
  display: flex;
  gap: .6rem;
  align-items: flex-start;
  border: 1px solid var(--linea);
  border-radius: 8px;
  padding: .65rem .75rem;
  margin: 0 0 .5rem;
  cursor: pointer;
  transition: border-color .15s, background .15s;
}
.opcion:hover { border-color: var(--azul-medio); background: #f8fbff; }
.opcion input { margin: .28rem 0 0; accent-color: var(--azul); }
.opcion .letra { font-weight: 700; color: var(--azul); min-width: 1.2rem; }
.opcion.correcta { border-color: var(--verde); background: #e9f9f3; }
.opcion.incorrecta { border-color: var(--rojo); background: #fdecea; }
.opcion.revelada { border-color: var(--verde); border-style: dashed; }
.pregunta.bloqueada .opcion { cursor: default; opacity: .85; }
.pregunta.bloqueada .opcion:hover { border-color: var(--linea); background: transparent; }
.pregunta.bloqueada .opcion input { cursor: default; }
.fijada { margin: .6rem 0 0; font-size: .85rem; color: var(--texto-suave); }
.progreso, .resultado {
  background: #fff;
  border: 1px solid var(--linea);
  border-radius: 10px;
  padding: .8rem 1rem;
  margin: 0 0 1.2rem;
}
.datos {
  background: #fff;
  border: 1px solid var(--linea);
  border-radius: 12px;
  padding: 1.1rem 1.2rem;
  margin: 0 0 1.2rem;
  box-shadow: 0 1px 3px rgba(13, 27, 42, .06);
}
.datos h2 { margin: 0 0 .7rem; font-size: 1.05rem; color: var(--azul); }
.datos .campos {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: .8rem 1rem;
}
.datos .campo { display: flex; flex-direction: column; gap: .3rem; }
.datos label { font-size: .85rem; font-weight: 600; color: var(--texto-suave); }
.datos input, .datos select {
  font: inherit;
  padding: .55rem .65rem;
  border: 1px solid var(--linea);
  border-radius: 8px;
  background: #fff;
  color: #1d2733;
}
.datos input:focus, .datos select:focus {
  outline: 2px solid var(--azul-medio);
  outline-offset: 1px;
}
.datos input.falta, .datos select.falta { border-color: #c2410c; background: #fffaf5; }
.datos .aviso-datos {
  margin: .7rem 0 0;
  padding: .5rem .65rem;
  border-radius: 8px;
  background: #fff4e5;
  color: #8a4b00;
  font-size: .88rem;
  font-weight: 600;
}
.progreso strong, .resultado strong { color: var(--azul); }
.entrega {
  margin: 1.6rem 0 0;
  padding: 1rem 1.1rem;
  background: var(--papel);
  border: 1px solid var(--linea);
  border-radius: 10px;
}
.entrega h2 { margin: 0 0 .4rem; font-size: 1.05rem; color: var(--azul); }
.entrega p { margin: 0 0 .8rem; font-size: .9rem; color: var(--texto-suave); }
.entrega button:disabled { opacity: .55; cursor: not-allowed; }
.estado-entrega { margin: .8rem 0 0; font-size: .92rem; font-weight: 600; }
.estado-entrega.ok { color: var(--verde); }
.estado-entrega.error { color: var(--rojo); }
.acciones { display: flex; gap: .6rem; flex-wrap: wrap; margin: 0 0 1.2rem; }
button {
  font: inherit;
  border: 0;
  border-radius: 8px;
  padding: .6rem 1rem;
  cursor: pointer;
  background: var(--azul);
  color: #fff;
}
button.secundario { background: var(--marca); }
button.terciario { background: #e6ecf5; color: var(--azul); }
.retro {
  margin: .8rem 0 0;
  padding: .7rem .85rem;
  border-left: 4px solid var(--cyan);
  background: #eef8fc;
  border-radius: 6px;
  font-size: .92rem;
}
code {
  background: var(--codigo);
  color: #eaf6ff;
  padding: .08rem .35rem;
  border-radius: 4px;
  font-size: .9em;
}
footer {
  max-width: 900px;
  margin: 0 auto;
  padding: 0 1.1rem 2rem;
  color: var(--texto-suave);
  font-size: .82rem;
}
@media print {
  body { background: #fff; }
  .banda { background: #fff; color: #000; border-bottom: 2px solid #000; }
  .banda .curso, .banda .meta { color: #333; }
  .acciones, .progreso, .resultado, .aviso { display: none; }
  .pregunta { box-shadow: none; break-inside: avoid; }
  .datos { box-shadow: none; }
  .datos input, .datos select {
    border: 0;
    border-bottom: 1px solid #000;
    border-radius: 0;
    padding: .2rem 0;
    appearance: none;
  }
  .datos .aviso-datos, .entrega { display: none; }
  button { display: none; }
}
"""
)


def _paleta() -> dict[str, str]:
    return {nombre: hexval for nombre, (hexval, _) in PALETA.items()}


def _slug(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto)
    ascii_texto = "".join(c for c in normalizado if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", ascii_texto.lower()).strip("_") or "cuestionario"


def _inline(texto: str) -> str:
    """Markdown inline mínimo y determinista: código, negrita y cursiva."""
    seguro = html.escape(texto, quote=False)
    seguro = re.sub(r"`([^`]+)`", r"<code>\1</code>", seguro)
    seguro = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", seguro)
    seguro = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", seguro)
    return seguro


def _leer_front_matter(texto: str) -> tuple[dict, str]:
    match = FRONT_MATTER.match(texto)
    if not match:
        return {}, texto
    try:
        datos = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise ValueError(f"front matter YAML inválido: {exc}") from exc
    if datos is None:
        datos = {}
    if not isinstance(datos, dict):
        raise ValueError("el front matter debe ser un mapa YAML")
    return datos, texto[match.end():]


def _parsear_cuestionario(texto: str) -> list[dict]:
    preguntas: list[dict] = []
    actual: dict | None = None
    for linea in texto.splitlines():
        match = PREGUNTA.match(linea)
        if match:
            if actual is not None:
                preguntas.append(actual)
            actual = {"numero": int(match.group(1)), "enunciado": [], "opciones": []}
            continue
        if actual is None:
            continue
        if SEPARADOR.match(linea) or not linea.strip():
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
    if actual is not None:
        preguntas.append(actual)

    for pregunta in preguntas:
        pregunta["enunciado"] = " ".join(pregunta["enunciado"]).strip()
    return preguntas


def _normalizar_texto(texto: str) -> str:
    """Colapsa espacios para comparar la misma frase escrita en dos archivos."""
    return " ".join(texto.split())


def _parsear_respuestas(texto: str) -> list[dict]:
    """Lee un archivo de respuestas: preguntas + `**Answer:** X.` por bloque.

    Devuelve la misma forma que `_parsear_cuestionario` más la letra de la
    respuesta. `**Hint:**` y `**Explanation:**` se reconocen para no confundir
    sus líneas con opciones, pero no se usan aquí.
    """
    preguntas: list[dict] = []
    actual: dict | None = None
    estado = "pregunta"
    for linea in texto.splitlines():
        match = PREGUNTA.match(linea)
        if match:
            if actual is not None:
                preguntas.append(actual)
            actual = {
                "numero": int(match.group(1)),
                "enunciado": [],
                "opciones": [],
                "respuesta": None,
            }
            estado = "pregunta"
            continue
        if actual is None:
            continue
        if SEPARADOR.match(linea) or not linea.strip():
            continue
        if estado == "pregunta":
            respuesta = RESPUESTA.match(linea)
            if respuesta:
                actual["respuesta"] = respuesta.group(1).upper()
                estado = "meta"
                continue
            if PISTA.match(linea):
                estado = "meta"
                continue
            if EXPLICACION.match(linea):
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
        if estado == "meta":
            respuesta = RESPUESTA.match(linea)
            if respuesta:
                actual["respuesta"] = respuesta.group(1).upper()
                continue
            if PISTA.match(linea):
                continue
            if EXPLICACION.match(linea):
                estado = "explicacion"
            continue
    if actual is not None:
        preguntas.append(actual)

    for pregunta in preguntas:
        pregunta["enunciado"] = " ".join(pregunta["enunciado"]).strip()
    return preguntas


def _cruzar(preguntas: list[dict], respuestas: list[dict]) -> tuple[list[str], dict[int, str]]:
    """Comprueba que el archivo de respuestas describe el mismo examen.

    Es la barrera contra la copia desactualizada: si los enunciados u opciones
    difieren, la clave podría estar corrigiendo otro examen y hay que fallar.
    """
    problemas: list[str] = []
    clave: dict[int, str] = {}
    if not respuestas:
        return ["el archivo de respuestas no contiene ninguna pregunta"], clave

    numeros_fuente = [p["numero"] for p in preguntas]
    numeros_resp = [r["numero"] for r in respuestas]
    if numeros_fuente != numeros_resp:
        problemas.append(
            f"las preguntas del archivo de respuestas no coinciden: "
            f"fuente {numeros_fuente}, respuestas {numeros_resp}"
        )
        return problemas, clave

    for fuente, resp in zip(preguntas, respuestas):
        numero = fuente["numero"]
        if _normalizar_texto(fuente["enunciado"]) != _normalizar_texto(resp["enunciado"]):
            problemas.append(f"pregunta {numero}: el enunciado difiere entre los dos archivos")
        opciones_fuente = [(o["letra"], _normalizar_texto(o["texto"])) for o in fuente["opciones"]]
        opciones_resp = [(o["letra"], _normalizar_texto(o["texto"])) for o in resp["opciones"]]
        if opciones_fuente != opciones_resp:
            problemas.append(f"pregunta {numero}: las opciones difieren entre los dos archivos")
        letra = resp.get("respuesta")
        if not letra:
            problemas.append(f"pregunta {numero}: el archivo de respuestas no trae `**Answer:**`")
            continue
        if letra not in {o["letra"] for o in resp["opciones"]}:
            problemas.append(f"pregunta {numero}: la respuesta {letra} no es una de sus opciones")
            continue
        clave[numero] = letra
    return problemas, clave


def _normalizar_clave(cruda: object) -> tuple[dict[int, str], list[str]]:
    problemas: list[str] = []
    if cruda is None:
        return {}, problemas
    if not isinstance(cruda, dict):
        return {}, ["`clave:` debe ser un mapa pregunta -> letra"]
    normalizada: dict[int, str] = {}
    for clave, valor in cruda.items():
        try:
            numero = int(clave)
        except (TypeError, ValueError):
            problemas.append(f"clave con pregunta no numérica: {clave!r}")
            continue
        if not isinstance(valor, str) or len(valor.strip()) != 1:
            problemas.append(f"clave[{numero}] debe ser una letra (A-F), no {valor!r}")
            continue
        normalizada[numero] = valor.strip().upper()
    return normalizada, problemas


def _normalizar_puntos(cruda: object, total: float, numeros: list[int]) -> tuple[dict[int, float], list[str]]:
    problemas: list[str] = []
    if cruda is None:
        if not numeros:
            return {}, problemas
        return {n: total / len(numeros) for n in numeros}, problemas
    if not isinstance(cruda, dict):
        return {}, ["`puntos:` debe ser un mapa pregunta -> número"]
    puntos: dict[int, float] = {}
    for clave, valor in cruda.items():
        try:
            numero = int(clave)
        except (TypeError, ValueError):
            problemas.append(f"puntos con pregunta no numérica: {clave!r}")
            continue
        try:
            puntos[numero] = float(valor)
        except (TypeError, ValueError):
            problemas.append(f"puntos[{numero}] no es numérico: {valor!r}")
    suma = sum(puntos.values())
    if abs(suma - total) > 0.01:
        problemas.append(
            f"la suma de `puntos:` es {suma:g} y `puntaje_total` es {total:g}"
        )
    return puntos, problemas


def validar(preguntas: list[dict], meta: dict) -> tuple[list[str], dict[int, str], dict[int, float], float]:
    problemas: list[str] = []
    if not preguntas:
        problemas.append("no se encontró ninguna pregunta (`## Question N` / `## Pregunta N`)")

    numeros = [p["numero"] for p in preguntas]
    if len(set(numeros)) != len(numeros):
        problemas.append(f"numeración de preguntas duplicada: {numeros}")
    if numeros and sorted(numeros) != list(range(1, len(numeros) + 1)):
        problemas.append(f"la numeración debe ser 1..{len(numeros)} sin huecos: {numeros}")

    for pregunta in preguntas:
        numero = pregunta["numero"]
        if not pregunta["enunciado"]:
            problemas.append(f"pregunta {numero}: enunciado vacío")
        opciones = pregunta["opciones"]
        if not (MIN_OPCIONES <= len(opciones) <= MAX_OPCIONES):
            problemas.append(
                f"pregunta {numero}: {len(opciones)} opción(es); se esperan entre "
                f"{MIN_OPCIONES} y {MAX_OPCIONES}"
            )
        letras = [o["letra"] for o in opciones]
        if len(set(letras)) != len(letras):
            problemas.append(f"pregunta {numero}: letras de opción duplicadas {letras}")
        for opcion in opciones:
            if not opcion["texto"]:
                problemas.append(f"pregunta {numero}: la opción {opcion['letra']} está vacía")

    clave, problemas_clave = _normalizar_clave(meta.get("clave"))
    problemas.extend(problemas_clave)
    if clave:
        letras_validas = {
            p["numero"]: {o["letra"] for o in p["opciones"]} for p in preguntas
        }
        for numero in numeros:
            if numero not in clave:
                problemas.append(f"falta la respuesta de la pregunta {numero} en `clave:`")
            elif clave[numero] not in letras_validas.get(numero, set()):
                problemas.append(
                    f"clave[{numero}]={clave[numero]} no es una opción de esa pregunta"
                )
        sobrantes = sorted(set(clave) - set(numeros))
        if sobrantes:
            problemas.append(f"`clave:` referencia preguntas inexistentes: {sobrantes}")

    total = meta.get("puntaje_total", len(preguntas))
    try:
        total = float(total)
    except (TypeError, ValueError):
        problemas.append(f"`puntaje_total` no es numérico: {meta.get('puntaje_total')!r}")
        total = float(len(preguntas))
    if total <= 0:
        problemas.append(f"`puntaje_total` debe ser > 0, no {total:g}")

    grupos = meta.get("grupos")
    if grupos is not None:
        try:
            grupos_int = int(grupos)
        except (TypeError, ValueError):
            problemas.append(f"`grupos` no es un entero: {grupos!r}")
        else:
            if not (1 <= grupos_int <= 20):
                problemas.append(f"`grupos` debe estar entre 1 y 20, no {grupos_int}")

    entrega_url = meta.get("entrega_url")
    if entrega_url is not None:
        if not isinstance(entrega_url, str) or not re.match(
            r"^https://[^\s]+$", entrega_url
        ):
            problemas.append(
                f"`entrega_url` debe ser una URL https:// sin espacios: {entrega_url!r}"
            )

    puntos, problemas_puntos = _normalizar_puntos(meta.get("puntos"), total, numeros)
    problemas.extend(problemas_puntos)
    return problemas, clave, puntos, total


def cargar_clave(fuente: Path | str, respuestas: Path | str | None = None) -> dict:
    """Lee una fuente y su clave: única definición del formato para los flujos.

    Devuelve `meta`, `preguntas`, `clave` (número -> letra), `puntos`,
    `puntaje_total`, `n_preguntas` y `grupos`. Lanza `ValueError` si la fuente o
    la clave no son válidas (o si el front matter y el archivo de respuestas
    discrepan) y `FileNotFoundError` si falta alguno de los dos archivos.

    Lo usan `flujo_desplegar_worker_cuestionarios.py` (para subir la clave como
    secreto del Worker) y `execution/descargar_resultados.py` (para recalcular la
    nota archivada). Dos copias de esta lectura divergirían en silencio y
    terminarían calificando distinto: la clave se lee una sola vez, aquí.
    """
    ruta_fuente = Path(fuente)
    if not ruta_fuente.is_file():
        raise FileNotFoundError(f"no existe la fuente: {ruta_fuente}")
    meta, cuerpo = _leer_front_matter(ruta_fuente.read_text(encoding="utf-8"))
    preguntas = _parsear_cuestionario(cuerpo)
    problemas, clave_fm, puntos, total = validar(preguntas, meta)
    if problemas:
        raise ValueError("; ".join(problemas))

    clave = dict(clave_fm)
    if respuestas is not None:
        ruta_resp = Path(respuestas)
        if not ruta_resp.is_file():
            raise FileNotFoundError(f"no existe el archivo de respuestas: {ruta_resp}")
        _, cuerpo_resp = _leer_front_matter(ruta_resp.read_text(encoding="utf-8"))
        parseadas = _parsear_respuestas(cuerpo_resp)
        problemas_cruce, clave_resp = _cruzar(preguntas, parseadas)
        if problemas_cruce:
            raise ValueError(
                "el archivo de respuestas no coincide con la fuente: "
                + "; ".join(problemas_cruce)
            )
        if clave_fm and clave_fm != clave_resp:
            discrepan = sorted(
                n
                for n in set(clave_fm) | set(clave_resp)
                if clave_fm.get(n) != clave_resp.get(n)
            )
            raise ValueError(
                "`clave:` del front matter y el archivo de respuestas no dicen lo "
                f"mismo; hay dos fuentes de verdad (preguntas: {discrepan})"
            )
        clave = dict(clave_resp)
        meta["clave"] = dict(clave_resp)
    elif MARCA_RESPUESTAS.search(cuerpo):
        raise ValueError(
            "la fuente contiene `**Answer:**`: parece un archivo de respuestas, "
            "no un cuestionario"
        )

    return {
        "meta": meta,
        "preguntas": preguntas,
        "clave": clave,
        "puntos": puntos,
        "puntaje_total": total,
        "n_preguntas": len(preguntas),
        "grupos": _grupos_declarados(meta),
    }


def _formato_punto(valor: float) -> str:
    texto = f"{valor:.2f}".rstrip("0").rstrip(".")
    return texto.replace(".", ",")


def _meta_linea(meta: dict) -> str:
    partes = []
    if meta.get("tipo"):
        partes.append(str(meta["tipo"]).capitalize())
    if meta.get("semana") is not None:
        partes.append(f"Semana {meta['semana']}")
    if meta.get("grupo") is not None:
        partes.append(f"Grupo {meta['grupo']}")
    if meta.get("variante") is not None:
        partes.append(f"Variante {meta['variante']}")
    return " · ".join(partes)


def _cabecera(meta: dict, titulo: str) -> str:
    curso = html.escape(str(meta.get("curso", "")), quote=True)
    titulo_html = html.escape(titulo, quote=True)
    linea = _meta_linea(meta)
    meta_html = f'<p class="meta">{html.escape(linea, quote=True)}</p>' if linea else ""
    curso_html = f'<p class="curso">{curso}</p>' if curso else ""
    return (
        '<header class="banda">'
        f"{curso_html}"
        f"<h1>{titulo_html}</h1>"
        f"{meta_html}"
        "</header>"
    )


def _opciones_html(pregunta: dict) -> str:
    filas = []
    for opcion in pregunta["opciones"]:
        letra = html.escape(opcion["letra"], quote=True)
        filas.append(
            f'<label class="opcion" data-letra="{letra}">'
            f'<input type="radio" name="q{pregunta["numero"]}" value="{letra}">'
            f'<span class="letra">{letra}.</span>'
            f'<span class="texto">{_inline(opcion["texto"])}</span>'
            "</label>"
        )
    return "\n".join(filas)


def _preguntas_html(
    preguntas: list[dict],
    puntos: dict[int, float],
    retro: dict[int, str] | None,
    fijable: bool = False,
) -> str:
    bloques = []
    for pregunta in preguntas:
        numero = pregunta["numero"]
        valor = puntos.get(numero, 0.0)
        retro_html = ""
        if retro and numero in retro:
            retro_html = (
                f'<p class="retro" hidden>{_inline(str(retro[numero]))}</p>'
            )
        fijada_html = (
            '<p class="fijada" hidden>Respuesta fijada: no se puede cambiar.</p>'
            if fijable
            else ""
        )
        bloques.append(
            f'<section class="pregunta" id="p{numero}" data-numero="{numero}">'
            f'<h2><span class="num">{numero}</span> Pregunta {numero}'
            f'<span class="puntos">({_formato_punto(valor)} pto)</span></h2>'
            f'<p class="enunciado">{_inline(pregunta["enunciado"])}</p>'
            "<fieldset>"
            f'<legend class="sr-only">Opciones de la pregunta {numero}</legend>'
            f"{_opciones_html(pregunta)}"
            "</fieldset>"
            f"{fijada_html}"
            f"{retro_html}"
            "</section>"
        )
    return "\n".join(bloques)


def _js_alumno(
    total: int,
    entrega_url: str | None = None,
    cuestionario_id: str = "",
) -> str:
    base = (
        "const total = " + str(total) + ";\n"
        "const contador = document.getElementById('contador');\n"
        "const form = document.getElementById('cuestionario');\n"
        "const avisoDatos = document.getElementById('aviso-datos');\n"
        "const camposDatos = ['estudiante-nombre', 'estudiante-cedula', "
        "'estudiante-grupo'].map(id => document.getElementById(id)).filter(Boolean);\n"
        "function datosCompletos(){\n"
        "  return camposDatos.length > 0"
        " && camposDatos.every(c => c.value.trim() !== '');\n"
        "}\n"
        "function marcarFaltantes(){\n"
        "  camposDatos.forEach(c => {\n"
        "    c.classList.toggle('falta', c.value.trim() === '');\n"
        "  });\n"
        "}\n"
        "function fijar(sec){\n"
        "  if (!sec || !sec.querySelector('input:checked')) return;\n"
        "  sec.querySelectorAll('input').forEach(i => { i.disabled = true; });\n"
        "  sec.classList.add('bloqueada');\n"
        "  const aviso = sec.querySelector('.fijada');\n"
        "  if (aviso) aviso.hidden = false;\n"
        "}\n"
        "function actualizar(){\n"
        "  const hechas = new Set(Array.from(form.querySelectorAll('input:checked'))"
        ".map(i => i.name)).size;\n"
        "  if (contador) contador.textContent = String(hechas);\n"
        "  refrescarBoton();\n"
        "}\n"
        "if (form) form.addEventListener('change', (evento) => {\n"
        "  if (evento.target.type === 'radio' && !datosCompletos()) {\n"
        "    evento.target.checked = false;\n"
        "    if (avisoDatos) avisoDatos.hidden = false;\n"
        "    marcarFaltantes();\n"
        "    const vacio = camposDatos.find(c => c.value.trim() === '');\n"
        "    if (vacio) vacio.focus();\n"
        "    return;\n"
        "  }\n"
        "  if (datosCompletos()) {\n"
        "    if (avisoDatos) avisoDatos.hidden = true;\n"
        "    marcarFaltantes();\n"
        "  }\n"
        "  const sec = evento.target.closest ? evento.target.closest('.pregunta') : null;\n"
        "  fijar(sec);\n"
        "  actualizar();\n"
        "});\n"
        "camposDatos.forEach(c => c.addEventListener('input', refrescarBoton));\n"
    )
    if not entrega_url:
        return base + "function refrescarBoton(){}\nactualizar();\n"
    return (
        base
        + "const ENTREGA_URL = " + json.dumps(entrega_url) + ";\n"
        + "const CUESTIONARIO = " + json.dumps(cuestionario_id) + ";\n"
        "const botonEnviar = document.getElementById('enviar');\n"
        "const estadoEntrega = document.getElementById('estado-entrega');\n"
        "let enviando = false;\n"
        "let enviado = false;\n"
        "function respuestas(){\n"
        "  const r = {};\n"
        "  form.querySelectorAll('input:checked').forEach(i => {\n"
        "    r[i.name.slice(1)] = i.value;\n"
        "  });\n"
        "  return r;\n"
        "}\n"
        "function puedeEnviar(){\n"
        "  return !!botonEnviar && !enviando && !enviado && datosCompletos()\n"
        "    && Object.keys(respuestas()).length === total;\n"
        "}\n"
        "function refrescarBoton(){\n"
        "  if (botonEnviar) botonEnviar.disabled = !puedeEnviar();\n"
        "}\n"
        "async function enviar(){\n"
        "  if (!puedeEnviar()) return;\n"
        "  enviando = true;\n"
        "  refrescarBoton();\n"
        "  if (estadoEntrega) {\n"
        "    estadoEntrega.className = 'estado-entrega';\n"
        "    estadoEntrega.textContent = 'Enviando…';\n"
        "  }\n"
        "  const cuerpo = {\n"
        "    cuestionario: CUESTIONARIO,\n"
        "    nombre: document.getElementById('estudiante-nombre').value.trim(),\n"
        "    cedula: document.getElementById('estudiante-cedula').value.trim(),\n"
        "    grupo: Number(document.getElementById('estudiante-grupo').value),\n"
        "    respuestas: respuestas()\n"
        "  };\n"
        "  try {\n"
        "    const res = await fetch(ENTREGA_URL, {\n"
        "      method: 'POST',\n"
        "      headers: {'Content-Type': 'application/json'},\n"
        "      body: JSON.stringify(cuerpo)\n"
        "    });\n"
        "    let datos = {};\n"
        "    try { datos = await res.json(); } catch (e) {}\n"
        "    if (!res.ok) throw new Error(datos.error || ('error ' + res.status));\n"
        "    enviado = true;\n"
        "    if (estadoEntrega) {\n"
        "      estadoEntrega.className = 'estado-entrega ok';\n"
        "      estadoEntrega.textContent = 'Entrega registrada. Nota: '\n"
        "        + Number(datos.nota).toFixed(2).replace('.', ',') + ' / 10 · '\n"
        "        + datos.aciertos + ' de ' + datos.total + ' correctas.';\n"
        "    }\n"
        "  } catch (e) {\n"
        "    if (estadoEntrega) {\n"
        "      estadoEntrega.className = 'estado-entrega error';\n"
        "      estadoEntrega.textContent = 'No se pudo enviar: ' + e.message\n"
        "        + '. Revisa la conexión y vuelve a intentar.';\n"
        "    }\n"
        "  } finally {\n"
        "    enviando = false;\n"
        "    refrescarBoton();\n"
        "  }\n"
        "}\n"
        "if (botonEnviar) botonEnviar.addEventListener('click', enviar);\n"
        "actualizar();\n"
    )


def _js_docente(clave: dict[int, str], puntos: dict[int, float], total: float) -> str:
    clave_js = "{" + ",".join(
        f'"{n}":"{letra}"' for n, letra in sorted(clave.items())
    ) + "}"
    puntos_js = "{" + ",".join(
        f'"{n}":{puntos.get(n, 0.0):g}' for n in sorted(clave)
    ) + "}"
    return (
        "const CLAVE = " + clave_js + ";\n"
        "const PUNTOS = " + puntos_js + ";\n"
        "const TOTAL = " + f"{total:g}" + ";\n"
        "const form = document.getElementById('cuestionario');\n"
        "const salida = document.getElementById('resultado');\n"
        "function marcar(clase, limpiar){\n"
        "  document.querySelectorAll('.opcion').forEach(o => {\n"
        "    o.classList.remove('correcta', 'incorrecta', 'revelada');\n"
        "  });\n"
        "  if (limpiar) return;\n"
        "  Object.keys(CLAVE).forEach(n => {\n"
        "    const seccion = document.getElementById('p' + n);\n"
        "    if (!seccion) return;\n"
        "    const elegida = seccion.querySelector('input:checked');\n"
        "    const correcta = seccion.querySelector("
        "'.opcion[data-letra=\"' + CLAVE[n] + '\"]');\n"
        "    if (correcta) correcta.classList.add(clase === 'revelar' "
        "? 'revelada' : 'correcta');\n"
        "    if (elegida && elegida.value !== CLAVE[n]) {\n"
        "      const mala = elegida.closest('.opcion');\n"
        "      if (mala) mala.classList.add('incorrecta');\n"
        "    }\n"
        "  });\n"
        "}\n"
        "function corregir(){\n"
        "  marcar('corregir', false);\n"
        "  let nota = 0;\n"
        "  let acertadas = 0;\n"
        "  Object.keys(CLAVE).forEach(n => {\n"
        "    const seccion = document.getElementById('p' + n);\n"
        "    const elegida = seccion ? seccion.querySelector('input:checked') : null;\n"
        "    if (elegida && elegida.value === CLAVE[n]) {\n"
        "      nota += PUNTOS[n] || 0;\n"
        "      acertadas += 1;\n"
        "    }\n"
        "  });\n"
        "  document.querySelectorAll('.retro').forEach(p => { p.hidden = false; });\n"
        "  if (salida) salida.innerHTML = '<strong>Resultado:</strong> ' + acertadas + "
        "' de ' + Object.keys(CLAVE).length + ' correctas · nota ' + "
        "nota.toFixed(2).replace('.', ',') + ' / ' + TOTAL.toFixed(2).replace('.', ',');\n"
        "}\n"
        "function revelar(){\n"
        "  marcar('revelar', false);\n"
        "  document.querySelectorAll('.retro').forEach(p => { p.hidden = false; });\n"
        "  if (salida) salida.textContent = 'Respuestas correctas reveladas.';\n"
        "}\n"
        "function limpiar(){\n"
        "  if (form) form.reset();\n"
        "  marcar('limpiar', true);\n"
        "  document.querySelectorAll('.retro').forEach(p => { p.hidden = true; });\n"
        "  if (salida) salida.textContent = '';\n"
        "}\n"
        "document.getElementById('corregir').addEventListener('click', corregir);\n"
        "document.getElementById('revelar').addEventListener('click', revelar);\n"
        "document.getElementById('limpiar').addEventListener('click', limpiar);\n"
    )


def _documento(titulo: str, meta: dict, cuerpo: str, script: str) -> str:
    return (
        "<!DOCTYPE html>\n"
        '<html lang="es">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(titulo, quote=True)}</title>\n"
        "<style>\n"
        + CSS.safe_substitute(_paleta())
        + "</style>\n"
        "</head>\n"
        "<body>\n"
        + _cabecera(meta, titulo)
        + "\n<main>\n"
        + cuerpo
        + "\n</main>\n"
        '<footer>Material privado del curso. No publicar ni compartir fuera del aula.</footer>\n'
        + (f"<script>\n{script}</script>\n" if script else "")
        + "</body>\n"
        "</html>\n"
    )


def _grupos_declarados(meta: dict) -> int | None:
    valor = meta.get("grupos")
    if valor is None:
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _campo_grupo(grupos: int | None) -> str:
    if grupos:
        opciones = "".join(
            f'<option value="{n}">Grupo {n}</option>' for n in range(1, grupos + 1)
        )
        control = (
            '<select id="estudiante-grupo" name="estudiante_grupo" required>'
            '<option value="">Selecciona tu grupo</option>'
            f"{opciones}"
            "</select>"
        )
    else:
        control = (
            '<input type="number" id="estudiante-grupo" name="estudiante_grupo" '
            'min="1" step="1" inputmode="numeric" required>'
        )
    return (
        '<div class="campo">'
        '<label for="estudiante-grupo">Grupo</label>'
        f"{control}"
        "</div>"
    )


def _datos_alumno(grupos: int | None) -> str:
    return (
        '<section class="datos" id="datos-estudiante" aria-labelledby="datos-titulo">'
        '<h2 id="datos-titulo">Datos del estudiante</h2>'
        '<div class="campos">'
        '<div class="campo">'
        '<label for="estudiante-nombre">Nombre y apellidos</label>'
        '<input type="text" id="estudiante-nombre" name="estudiante_nombre" '
        'autocomplete="name" spellcheck="false" required>'
        "</div>"
        '<div class="campo">'
        '<label for="estudiante-cedula">Cédula de identidad</label>'
        '<input type="text" id="estudiante-cedula" name="estudiante_cedula" '
        'inputmode="numeric" autocomplete="off" placeholder="Ej.: 12345678" required>'
        "</div>"
        f"{_campo_grupo(grupos)}"
        "</div>"
        '<p class="aviso-datos" id="aviso-datos" role="alert" hidden>'
        "Completa tu nombre, cédula y grupo antes de responder."
        "</p>"
        "</section>\n"
    )


def _entrega_alumno(total: int) -> str:
    return (
        '<section class="entrega" id="entrega" aria-labelledby="entrega-titulo">'
        '<h2 id="entrega-titulo">Enviar mis respuestas</h2>'
        f"<p>Cuando hayas respondido las {total} preguntas podrás enviar. "
        "La entrega es definitiva: las respuestas quedan fijadas.</p>"
        '<button type="button" id="enviar" disabled>Enviar mis respuestas</button>'
        '<div class="estado-entrega" id="estado-entrega" role="status" '
        'aria-live="polite"></div>'
        "</section>\n"
    )


def _render_alumno(
    titulo: str,
    meta: dict,
    preguntas: list[dict],
    puntos: dict[int, float],
    entrega_url: str | None = None,
    cuestionario_id: str = "",
) -> str:
    cuerpo = (
        '<div class="progreso">Respondidas: <strong><span id="contador">0</span></strong>'
        f" de {len(preguntas)}.</div>\n"
        '<form id="cuestionario">\n'
        + _datos_alumno(_grupos_declarados(meta))
        + _preguntas_html(preguntas, puntos, None, fijable=True)
        + "\n</form>"
    )
    if entrega_url:
        cuerpo += "\n" + _entrega_alumno(len(preguntas))
    return _documento(
        titulo, meta, cuerpo, _js_alumno(len(preguntas), entrega_url, cuestionario_id)
    )


def _render_docente(
    titulo: str,
    meta: dict,
    preguntas: list[dict],
    puntos: dict[int, float],
    total: float,
    clave: dict[int, str],
    retro: dict[int, str] | None,
) -> str:
    acciones = (
        '<div class="acciones">'
        '<button type="button" id="corregir">Corregir</button>'
        '<button type="button" id="revelar" class="secundario">Mostrar respuestas</button>'
        '<button type="button" id="limpiar" class="terciario">Limpiar</button>'
        "</div>\n"
        '<div class="resultado" id="resultado" aria-live="polite"></div>\n'
    )
    aviso = (
        '<div class="aviso"><strong>Modo docente.</strong> Esta página contiene la '
        "clave de respuestas en el código fuente. No compartir el archivo con los "
        "estudiantes.</div>\n"
    )
    cuerpo = (
        aviso
        + acciones
        + '<form id="cuestionario">\n'
        + _preguntas_html(preguntas, puntos, retro)
        + "\n</form>"
    )
    return _documento(titulo, meta, cuerpo, _js_docente(clave, puntos, total))


def _validar_salida(salida_dir: Path) -> None:
    raiz_cursos = (PROJECT_ROOT / "cursos").resolve()
    destino = salida_dir.resolve()
    try:
        relativo = destino.relative_to(raiz_cursos)
    except ValueError as exc:
        raise PermissionError(
            f"la salida debe estar dentro de cursos/: {destino}"
        ) from exc
    partes = relativo.parts
    if len(partes) < 3 or partes[1] != "evaluaciones" or partes[2] != "web":
        raise PermissionError(
            "la salida debe ser cursos/<CURSO>/evaluaciones/web/ "
            f"(recibido: {relativo})"
        )
    if len(partes) > 3 and partes[3] == "fuentes":
        raise PermissionError("la salida no puede escribirse dentro de fuentes/")
    prueba = destino / ".md_a_html_guard"
    resultado = subprocess.run(
        ["git", "check-ignore", "-q", str(prueba)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if resultado.returncode != 0:
        raise PermissionError(
            "git no ignora la salida; un examen podría publicarse en el repo. "
            f"Revisar .gitignore para {prueba}"
        )


def _escribir(ruta: Path, contenido: str) -> None:
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    temporal.write_text(contenido, encoding="utf-8")
    os.replace(temporal, ruta)


def _generar_indice(salida_dir: Path) -> Path:
    fuentes_dir = salida_dir / "fuentes"
    entradas = []
    if fuentes_dir.is_dir():
        for fuente in sorted(fuentes_dir.glob("*.md")):
            try:
                meta, resto = _leer_front_matter(fuente.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            titulo = meta.get("titulo")
            if not titulo:
                primera = re.search(r"^#\s+(.+)$", resto, re.MULTILINE)
                titulo = primera.group(1).strip() if primera else fuente.stem
            slug = _slug(fuente.stem)
            enlaces = []
            for variante in VARIANTES:
                archivo = salida_dir / f"{slug}_{variante}.html"
                if archivo.is_file():
                    enlaces.append(
                        f'<a class="boton" href="{archivo.name}">{variante.capitalize()}</a>'
                    )
            if enlaces:
                entradas.append(
                    "<li>"
                    f'<span class="titulo">{html.escape(str(titulo), quote=False)}</span>'
                    f'<span class="enlaces">{" ".join(enlaces)}</span>'
                    "</li>"
                )
    cuerpo = (
        '<div class="aviso"><strong>Material privado.</strong> Estos cuestionarios '
        "son de uso interno del curso; no publicar ni compartir fuera del aula.</div>\n"
        "<h2>Cuestionarios disponibles</h2>\n"
        + ("<ul class=\"indice\">" + "\n".join(entradas) + "</ul>" if entradas else "<p>No hay cuestionarios generados.</p>")
    )
    meta = {"curso": "", "tipo": ""}
    html_doc = _documento("Cuestionarios del curso", meta, cuerpo, "")
    html_doc = html_doc.replace(
        "</style>\n",
        "</style>\n<style>\n"
        ".indice { list-style: none; padding: 0; margin: 0; }\n"
        ".indice li { display: flex; justify-content: space-between; gap: 1rem; "
        "align-items: center; background: #fff; border: 1px solid var(--linea); "
        "border-radius: 10px; padding: .8rem 1rem; margin: 0 0 .6rem; flex-wrap: wrap; }\n"
        ".indice .titulo { font-weight: 600; color: var(--azul); }\n"
        ".boton { display: inline-block; background: var(--azul); color: #fff; "
        "padding: .35rem .7rem; border-radius: 6px; text-decoration: none; "
        "font-size: .85rem; }\n"
        "</style>\n",
        1,
    )
    destino = salida_dir / "index.html"
    _escribir(destino, html_doc)
    return destino


def _resultado(status: str, code: int, **extra) -> dict:
    return {"status": status, "code": code, **extra}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convierte un cuestionario Markdown a HTML determinista."
    )
    parser.add_argument("--fuente", required=True, help="Ruta al .md de origen.")
    parser.add_argument(
        "--salida-dir",
        default=None,
        help="Directorio de salida (por defecto, el padre de fuentes/).",
    )
    parser.add_argument(
        "--variantes",
        default="alumno,docente",
        help="Variantes a generar, separadas por coma: alumno,docente.",
    )
    parser.add_argument("--check", action="store_true", help="Valida sin escribir.")
    parser.add_argument("--dry-run", action="store_true", help="Muestra rutas sin escribir.")
    parser.add_argument("--json", action="store_true", help="Salida JSON.")
    parser.add_argument("--titulo", default=None, help="Sobrescribe el título.")
    parser.add_argument("--curso", default=None, help="Sobrescribe el curso.")
    parser.add_argument(
        "--respuestas",
        default=None,
        help=(
            "Archivo .md con las respuestas (`**Answer:** X.`). Se valida contra "
            "la fuente y de ahí sale la clave de la variante docente."
        ),
    )
    args = parser.parse_args()

    fuente = Path(args.fuente).resolve()
    if not fuente.is_file():
        print(json.dumps(_resultado("error", 1, message=f"no existe {fuente}")))
        return 1

    variantes = [v.strip().lower() for v in args.variantes.split(",") if v.strip()]
    invalidas = [v for v in variantes if v not in VARIANTES]
    if invalidas:
        print(json.dumps(_resultado("error", 3, message=f"variantes inválidas: {invalidas}")))
        return 3
    if not variantes:
        print(json.dumps(_resultado("error", 3, message="no se pidió ninguna variante")))
        return 3

    try:
        texto = fuente.read_text(encoding="utf-8")
    except OSError as exc:
        print(json.dumps(_resultado("error", 1, message=f"no se pudo leer: {exc}")))
        return 1

    try:
        meta, cuerpo = _leer_front_matter(texto)
        preguntas = _parsear_cuestionario(cuerpo)
    except ValueError as exc:
        print(json.dumps(_resultado("error", 3, message=str(exc))))
        return 3

    if args.curso:
        meta["curso"] = args.curso
    if args.titulo:
        meta["titulo"] = args.titulo

    ruta_respuestas: Path | None = None
    if args.respuestas:
        ruta_respuestas = Path(args.respuestas).resolve()
        if not ruta_respuestas.is_file():
            print(json.dumps(_resultado("error", 1, message=f"no existe {ruta_respuestas}")))
            return 1
        try:
            texto_resp = ruta_respuestas.read_text(encoding="utf-8")
            _, cuerpo_resp = _leer_front_matter(texto_resp)
            respuestas = _parsear_respuestas(cuerpo_resp)
        except (OSError, ValueError) as exc:
            print(json.dumps(_resultado("error", 3, message=f"respuestas ilegibles: {exc}")))
            return 3
        problemas_cruce, clave_resp = _cruzar(preguntas, respuestas)
        if problemas_cruce:
            print(
                json.dumps(
                    _resultado(
                        "error",
                        3,
                        message="el archivo de respuestas no coincide con la fuente",
                        problemas=problemas_cruce,
                    ),
                    ensure_ascii=False,
                )
            )
            return 3
        clave_meta, problemas_clave_meta = _normalizar_clave(meta.get("clave"))
        if problemas_clave_meta:
            print(
                json.dumps(
                    _resultado(
                        "error", 3, message="`clave:` mal formada", problemas=problemas_clave_meta
                    ),
                    ensure_ascii=False,
                )
            )
            return 3
        if clave_meta and clave_meta != clave_resp:
            discrepan = sorted(
                n for n in set(clave_meta) | set(clave_resp)
                if clave_meta.get(n) != clave_resp.get(n)
            )
            print(
                json.dumps(
                    _resultado(
                        "error",
                        3,
                        message=(
                            "`clave:` del front matter y el archivo de respuestas "
                            "no dicen lo mismo; hay dos fuentes de verdad"
                        ),
                        problemas=[f"preguntas en desacuerdo: {discrepan}"],
                    ),
                    ensure_ascii=False,
                )
            )
            return 3
        meta["clave"] = dict(clave_resp)
    elif MARCA_RESPUESTAS.search(cuerpo):
        print(
            json.dumps(
                _resultado(
                    "error",
                    3,
                    message=(
                        "la fuente contiene `**Answer:**`: parece un archivo de "
                        "respuestas, no un cuestionario. Pasarlo con --respuestas "
                        "y apuntar --fuente al cuestionario"
                    ),
                ),
                ensure_ascii=False,
            )
        )
        return 3

    problemas, clave, puntos, total = validar(preguntas, meta)
    if problemas:
        print(
            json.dumps(
                _resultado(
                    "error",
                    3,
                    message="la fuente no cumple el contrato",
                    problemas=problemas,
                ),
                ensure_ascii=False,
            )
        )
        return 3

    titulo = meta.get("titulo")
    if not titulo:
        primera = re.search(r"^#\s+(.+)$", cuerpo, re.MULTILINE)
        titulo = primera.group(1).strip() if primera else fuente.stem
    meta.setdefault("curso", "")
    if not meta["curso"]:
        partes = fuente.parts
        if "cursos" in partes:
            indice = partes.index("cursos")
            if indice + 1 < len(partes):
                meta["curso"] = partes[indice + 1]

    retro_crudo = meta.get("retroalimentacion")
    retro: dict[int, str] = {}
    if isinstance(retro_crudo, dict):
        for k, v in retro_crudo.items():
            try:
                retro[int(k)] = str(v)
            except (TypeError, ValueError):
                continue

    salida_dir = (
        Path(args.salida_dir).resolve()
        if args.salida_dir
        else (fuente.parent.parent if fuente.parent.name == "fuentes" else fuente.parent)
    )
    slug = _slug(fuente.stem)
    plan = {v: salida_dir / f"{slug}_{v}.html" for v in variantes}

    resumen = {
        "fuente": str(fuente),
        "titulo": titulo,
        "curso": meta.get("curso", ""),
        "preguntas": len(preguntas),
        "puntaje_total": total,
        "tiene_clave": bool(clave),
        "respuestas": str(ruta_respuestas) if ruta_respuestas else None,
        "entrega_url": meta.get("entrega_url"),
        "variantes": variantes,
        "salidas": {k: str(v) for k, v in plan.items()},
    }

    if args.check:
        print(json.dumps(_resultado("ok", 0, **resumen), ensure_ascii=False))
        return 0

    if args.dry_run:
        print(json.dumps(_resultado("dry-run", 0, **resumen), ensure_ascii=False))
        return 0

    if "docente" in variantes and not clave:
        print(
            json.dumps(
                _resultado(
                    "error",
                    4,
                    message=(
                        "se pidió la variante docente pero el front matter no tiene "
                        "`clave:`; añadir el mapa pregunta -> letra"
                    ),
                    **resumen,
                ),
                ensure_ascii=False,
            )
        )
        return 4

    try:
        _validar_salida(salida_dir)
    except PermissionError as exc:
        print(json.dumps(_resultado("error", 5, message=str(exc))))
        return 5

    salida_dir.mkdir(parents=True, exist_ok=True)
    generados: dict[str, str] = {}
    try:
        if "alumno" in variantes:
            ruta = plan["alumno"]
            _escribir(
                ruta,
                _render_alumno(
                    titulo,
                    meta,
                    preguntas,
                    puntos,
                    meta.get("entrega_url"),
                    slug,
                ),
            )
            generados["alumno"] = str(ruta)
        if "docente" in variantes:
            ruta = plan["docente"]
            _escribir(
                ruta,
                _render_docente(titulo, meta, preguntas, puntos, total, clave, retro),
            )
            generados["docente"] = str(ruta)
        indice = _generar_indice(salida_dir)
        generados["indice"] = str(indice)
    except OSError as exc:
        print(json.dumps(_resultado("error", 1, message=f"no se pudo escribir: {exc}")))
        return 1

    print(
        json.dumps(
            _resultado("ok", 0, **resumen, generados=generados),
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
