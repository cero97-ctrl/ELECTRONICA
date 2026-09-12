#!/usr/bin/env python3
"""
regenerar_faq_flujo.py — Sincroniza el documento de diagramas de flujo LaTeX con su FAQ Markdown
fuente (Layer 3: Execution).

El .tex de diagramas (`faq_higiene_estado_sesion_flujo.tex`) es una traducción SEMÁNTICA
(no 1:1 mecánica) del FAQ (`faq_higiene_estado_sesion.md`). Este script aplica la estrategia
híbrida:

1. DOBLE determinista  : campos conocidos (FECHA_PLANTILLA, modelo obsoleto, nº de bitácoras
                         antiguas) se inyectan por sustitución directa cuando cambian en el .md.
2. Clasificación       : difiere el .md contra el snapshot previo; si los cambios solo tocan
                         campos conocidos -> nada más que hacer. Si hay cambios estructurales
                         (texto nuevo, secciones, semántica) -> se requiere re-traducción LLM.
3. Re-traducción LLM   : para cada sección del FAQ afectada, se invoca el LLM (enrutador
                         determinista) con el bloque .tex actual como plantilla; devuelve un
                         JSON de edits quirúrgicos {"edits":[{"old":...,"new":...}]} que el
                         script valida (substring único, geometría intacta, LaTeX prohibido
                         de estructura) antes de aplicar.

Uso:
    python3 execution/regenerar_faq_flujo.py                      # sincroniza el .tex
    python3 execution/regenerar_faq_flujo.py --plan               # solo clasifica, sin tocar nada
    python3 execution/regenerar_faq_flujo.py --dry-run            # aplica en memoria, sin escribir
    python3 execution/regenerar_faq_flujo.py --no-llm             # aborta si hay cambio semántico
    python3 execution/regenerar_faq_flujo.py --critico            # escala el LLM a opus (enrutador)

Salida (stdout, JSON):
    { "status": "ok", "tex_cambiado": bool, "via": "determinista|llm|sin_cambios",
      "cambios": [...], "known_fields": {...}, ... }

Códigos de salida:
    0 — OK (tex sincronizado o sin cambios)
    2 — errores de entrada (md/tex/snapshot inexistentes)
    3 — cambio estructural pero --no-llm activo (no se tocó el tex)
    4 — no hay plantilla .tex (el flujo no crea diagramas desde cero)
    5 — fallo del LLM o edits inválidos tras agotar el retry budget (máx 3)
"""

import argparse
import difflib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from execution.enrutador import decide, append_log  # noqa: E402
from execution.llm_client import openrouter_chat, get_max_tokens, load_api_key  # noqa: E402

# ── Marcadores estructurales del .tex ──────────────────────────────────────────
_MARKER = "% \u2550\u2550 Secci\u00f3n"          # "% ══ Sección"
_MARKERS = {n: f"{_MARKER} {n}:" for n in (1, 2, 3, 4)}
_END_DOC = "\\end{document}"

# Secciones del FAQ Markdown que se ignoran (no alimentan diagramas)
_IGNORED_MD_SECTIONS = {"front", "refs"}

# Mapas sección md -> bloque tex
_BLOCK_FOR_MD_SECTION = {"1": 1, "2": 2, "3": 3, "4": 4}

# Tokens prohibidos en el texto nuevo de un edit (protegen la estructura del .tex)
_FORBIDDEN_IN_NEW = ("\\begin{tikzpicture}", "\\end{tikzpicture}", "\\section",
                     "\\begin{document}", "\\end{document}", "\\documentclass")

MAX_EDITS_PER_BLOCK = 25
RETRY_BUDGET = 3

# ── Campos conocidos (deterministas) ───────────────────────────────────────────
_RE_FECHA = r"\d{4}-\d{2}-\d{2}"
_RE_MODELO = r"deepseek-[\w.-]+"
_RE_ANTIGUAS = r"\d+\s+antiguas"


def _find_sections(md_lines: list[str], snap_lines: list[str]) -> dict:
    """Indexa las cabeceras '## N. ...' de ambos documentos."""
    def index(lines):
        out = []
        for i, ln in enumerate(lines):
            m = re.match(r"^##\s+(\d+)\.", ln)
            if m:
                out.append((i, m.group(1)))
            elif re.match(r"^##\s+Referencias", ln):
                out.append((i, "refs"))
        return out

    return {"md": index(md_lines), "snap": index(snap_lines)}


def _seccion_de_linea(idx: int, headings: list[tuple[int, str]]) -> str:
    sec = "front"
    for i, name in headings:
        if i <= idx:
            sec = name
        else:
            break
    return sec


def _scrub_line(line: str) -> str:
    """Normaliza una línea eliminando los campos conocidos (para clasificar el cambio)."""
    line = re.sub(_RE_FECHA, "<FECHA>", line)
    line = re.sub(_RE_MODELO, "<MODELO>", line)
    line = re.sub(_RE_ANTIGUAS, "<N> antiguas", line)
    return line


def clasificar_cambios(md_text: str, snap_text: str):
    """Devuelve {seccion_md: {"semantico": bool, "hunks": [(old_lines, new_lines)]}}."""
    md_lines = md_text.splitlines()
    snap_lines = snap_text.splitlines()
    head = _find_sections(md_lines, snap_lines)

    por_seccion: dict[str, dict] = {}
    sm = difflib.SequenceMatcher(None, snap_lines, md_lines)

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        old_lines = snap_lines[i1:i2]
        new_lines = md_lines[j1:j2]
        if new_lines:
            sec = _seccion_de_linea(j1, head["md"])
        else:
            sec = _seccion_de_linea(i1, head["snap"])
        entry = por_seccion.setdefault(sec, {"semantico": False, "hunks": []})
        entry["hunks"].append((old_lines, new_lines))

        # ¿Cambio solo de campos conocidos? (normalizado igual en ambos lados)
        for o, n in zip(old_lines, new_lines):
            if _scrub_line(o) != _scrub_line(n):
                entry["semantico"] = True
        if len(old_lines) != len(new_lines):
            entry["semantico"] = True

    return por_seccion


def extraer_campos_conocidos(md_text: str) -> dict:
    """Extrae del .md los campos deterministas que se inyectan en el .tex."""
    campos = {}
    m = re.search(r"FECHA_PLANTILLA\s*\((\d{4}-\d{2}-\d{2})\)", md_text)
    if m:
        y, mo, d = m.group(1).split("-")
        campos["fecha_plantilla"] = {
            "iso": m.group(1),
            "header": f"{d}/{mo}/{y}",
        }
    m = re.search(_RE_MODELO, md_text)
    if m:
        campos["modelo"] = m.group(0)
    m = re.search(_RE_ANTIGUAS, md_text)
    if m:
        campos["n_antiguas"] = re.match(r"(\d+)", m.group(0)).group(0)
    return campos


def _blocks_tex(tex: str) -> dict:
    """Devuelve {n: (start, end)} de los 4 bloques de sección del .tex."""
    pos = {}
    for n, marker in _MARKERS.items():
        i = tex.find(marker)
        if i == -1:
            raise ValueError(f"No se encontró el marcador '{marker}' en el .tex.")
        pos[n] = i
    end = tex.find(_END_DOC)
    if end == -1:
        raise ValueError("No se encontró \\end{document} en el .tex.")
    return {
        1: (pos[1], pos[2]),
        2: (pos[2], pos[3]),
        3: (pos[3], pos[4]),
        4: (pos[4], end),
    }


def aplicar_campos_conocidos(tex: str, campos: dict) -> tuple[str, dict]:
    """Aplica las sustituciones deterministas al .tex. Devuelve (tex, aplicados)."""
    aplicados = {}
    fecha = campos.get("fecha_plantilla")
    if fecha:
        iso, header = fecha["iso"], fecha["header"]
        antes = tex
        tex = re.sub(_RE_FECHA, iso, tex)
        if tex != antes:
            aplicados["fecha"] = iso
        antes = tex
        tex = re.sub(r"\d{2}/\d{2}/\d{4}", header, tex)
        if tex != antes:
            aplicados["header"] = header
    modelo = campos.get("modelo")
    if modelo:
        antes = tex
        tex = re.sub(_RE_MODELO, modelo, tex)
        if tex != antes:
            aplicados["modelo"] = modelo
    antiguas = campos.get("n_antiguas")
    if antiguas:
        antes = tex
        tex = re.sub(_RE_ANTIGUAS, f"{antiguas} antiguas", tex)
        if tex != antes:
            aplicados["n_antiguas"] = antiguas
    return tex, aplicados


# ── Parsing robusto de la respuesta JSON del LLM ───────────────────────────────
def _find_balanced_json(text: str) -> str | None:
    """Primer objeto JSON balanceado, respetando strings y escapes."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            if in_string:
                escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _parse_edits(raw: str) -> list[dict]:
    bloque = _find_balanced_json(raw)
    if not bloque:
        raise ValueError("No se encontró un JSON balanceado en la respuesta del LLM.")
    bloque = re.sub(r",\s*([}\]])", r"\1", bloque)
    data = json.loads(bloque)
    edits = data.get("edits") if isinstance(data, dict) else None
    if not isinstance(edits, list):
        raise ValueError("La respuesta del LLM no contiene una lista 'edits'.")
    return edits


# ── Invocación LLM con retry budget (fallback cost-aware del enrutador) ────────
def _llm_edits(model: str, fallback: list[str], tokens: int, critico: bool,
               block_tex: str, md_seccion: str, hunks: list) -> list[dict]:
    task = "conversion"
    decision = decide(task, tokens, critico, False, None)
    if decision["tier"] == "desconocido":
        raise RuntimeError(decision["reason"])
    append_log({"tipo": "sync_faq", **decision})

    candidates = list(dict.fromkeys([decision["model"]] + (decision.get("fallback") or [])[:2]))
    if model:  # override explícito (--modelo-explicito implícito vía --critico no aplica aquí)
        candidates = [model] + [c for c in candidates if c != model]

    cambios_txt = []
    for old, new in hunks:
        cambios_txt.append("ANTES:\n" + "\n".join(old) + "\nAHORA:\n" + "\n".join(new))

    system = (
        "Eres un editor quir\u00fargico de c\u00f3digo LaTeX en el proyecto ELECTRONICA. "
        "Debes sincronizar el diagrama de flujo LaTeX (TikZ + tablas tcolorbox 'Leyenda de etiquetas') "
        "con cambios del documento Markdown fuente de un FAQ.\n\n"
        "REGLAS INVARIABLES (cumplirlas siempre):\n"
        "1. NO modifiques la geometr\u00eda: ni coordenadas, ni estilos \\node[...], ni el n\u00famero de "
        "nodos, ni los nombres de nodo, ni las etiquetas internas de los s\u00edmbolos (T1, P1, D1, E1, A1, N1...).\n"
        "2. Solo edita textos: las filas de la tabla 'Leyenda de etiquetas', los \u00faltimos p\u00e1rrafos "
        "explicativos de la secci\u00f3n y, si el texto del nodo no es la etiqueta, ese texto.\n"
        "3. El cambio puede exigir a\u00f1adir filas a la tabla 'Leyenda de etiquetas' (m\u00ednimas) o reescribir "
        "el significado de filas existentes. PROHIBIDO a\u00f1adir nodos, coordenadas o secciones nuevas.\n"
        "4. Mant\u00e9n el LaTeX v\u00e1lido: dentro de tablas escapa & como \\& y _ como \\_ si est\u00e1 dentro de "
        "\\texttt. Respeta \\toprule / \\midrule / \\bottomrule y el formato exacto de la tabla.\n"
        "5. Devuelve SOLO JSON sin markdown: {\"edits\":[{\"old\":\"<subcadena \u00fanica del bloque>\","
        "\"new\":\"<texto nuevo>\"}]}. 'old' debe existir EXACTO y aparecer UNA sola vez dentro del bloque dado; "
        "si no es \u00fanico, ampl\u00eda contexto en 'old'. Si no hay nada que cambiar, devuelve {\"edits\":[]}.\n"
        "6. No escribas nada fuera del JSON."
    )

    user = (
        f"CONTEXTO: sincroniza los diagramas con los cambios de la SECCI\u00d3N {md_seccion} del FAQ.\n\n"
        + "CAMBIO DETECTADO EN LA SECCI\u00d3N (fragmentos viejos -> nuevos):\n"
        + "\n".join(cambios_txt)
        + "\n\nBLOQUE LaTeX ACTUAL a editar:\n```\n" + block_tex + "\n```\n"
    )

    last_error = None
    for n_attempt, model_candidate in enumerate(candidates[:RETRY_BUDGET]):
        try:
            raw, _tokens = openrouter_chat(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                model=model_candidate,
                api_key=load_api_key(),
                temperature=0.1,
                max_tokens=get_max_tokens(),
                title="ELECTRONICA - Sync FAQ->Flujo",
            )
            edits = _parse_edits(raw)
            if not isinstance(edits, list) or len(edits) > MAX_EDITS_PER_BLOCK:
                raise ValueError(f"Lista de edits no v\u00e1lida (got {len(edits) if isinstance(edits, list) else '?'})")
            return edits
        except Exception as e:  # noqa: BLE001 — agotar el retry budget del framework
            last_error = f"[modelo {model_candidate}, intento {n_attempt + 1}/{RETRY_BUDGET}] {e}"
    raise RuntimeError(f"Fall\u00f3 la re-traducci\u00f3n LLM tras {RETRY_BUDGET} intentos. \u00daltimo error: {last_error}")


def _edits_validos(edits: list[dict], block: str) -> list[dict]:
    """Valida y filtra edits peligrosos antes de aplicarlos al bloque."""
    validos = []
    for e in edits:
        if not isinstance(e, dict):
            continue
        old, new = e.get("old"), e.get("new")
        if not isinstance(old, str) or not isinstance(new, str) or not old or old == new:
            continue
        if block.count(old) != 1:
            raise ValueError(f"'old' debe aparecer UNA vez en el bloque (aparece {block.count(old)}): {old!r}")
        for tok in _FORBIDDEN_IN_NEW:
            if tok in new:
                raise ValueError(f"Edit rechazado: contiene token estructural '{tok}'.")
        validos.append({"old": old, "new": new})
    return validos


def _aplicar_edits(block: str, edits: list[dict]) -> str:
    for e in edits:
        if block.count(e["old"]) != 1:
            raise ValueError(f"'old' ya no es \u00fanico al aplicar: {e['old']!r}")
        block = block.replace(e["old"], e["new"])
    return block


def main() -> int:
    parser = argparse.ArgumentParser(description="Sincroniza el .tex de diagramas con su FAQ markdown.")
    parser.add_argument("--md", default=str(PROJECT_ROOT / "docs" / "AGENTE_IA" / "faq_higiene_estado_sesion.md"))
    parser.add_argument("--tex", default=str(PROJECT_ROOT / "docs" / "AGENTE_IA" / "faq_higiene_estado_sesion_flujo.tex"))
    parser.add_argument("--snapshot", default=str(PROJECT_ROOT / ".tmp" / "faq_flujo_md_snapshot.md"))
    parser.add_argument("--plan", action="store_true", help="Solo clasificar/campos, sin llamar al LLM ni escribir.")
    parser.add_argument("--dry-run", action="store_true", help="Aplicar en memoria; no escribir nada.")
    parser.add_argument("--no-llm", action="store_true", help="Abortar (código 3) si hay cambio estructural.")
    parser.add_argument("--critico", action="store_true", help="Escala la re-traducción LLM a opus (enrutador).")
    parser.add_argument("--modelo", default=None, help="Modelo explícito (override, opcional).")
    args = parser.parse_args()

    md_path, tex_path = Path(args.md), Path(args.tex)
    snap_path = Path(args.snapshot)
    if not md_path.is_file():
        print(json.dumps({"status": "error", "code": 2, "message": f"Falta el .md: {md_path}"}, ensure_ascii=False))
        return 2
    if not tex_path.is_file():
        print(json.dumps({"status": "error", "code": 4,
                          "message": f"No hay plantilla .tex ({tex_path}). Este flujo no crea diagramas desde cero."},
                         ensure_ascii=False))
        return 4

    md_text = md_path.read_text(encoding="utf-8")
    tex = tex_path.read_text(encoding="utf-8")
    snap_text = snap_path.read_text(encoding="utf-8") if snap_path.is_file() else None

    # 1) Campos conocidos
    campos = extraer_campos_conocidos(md_text)
    tex, aplicados = aplicar_campos_conocidos(tex, campos)

    # 2) Clasificación (si hay snapshot)
    cambios_por_seccion = clasificar_cambios(md_text, snap_text) if snap_text else {}

    mapa = []
    llm_necesario = False
    for sec in sorted(cambios_por_seccion):
        info = cambios_por_seccion[sec]
        if sec in _IGNORED_MD_SECTIONS:
            mapa.append({"seccion": sec, "via": "ignorada", "hunks": len(info["hunks"])})
            continue
        if not info["semantico"]:
            mapa.append({"seccion": sec, "via": "determinista", "hunks": len(info["hunks"])})
            continue
        mapa.append({"seccion": sec, "via": "llm", "hunks": len(info["hunks"])})
        llm_necesario = True

    resultado = {
        "status": "ok",
        "tex_cambiado": bool(aplicados),
        "via": "sin_cambios",
        "known_fields": aplicados,
        "cambios": mapa,
        "llm_necesario": llm_necesario,
    }

    # ── Modo --plan: clasificar y salir ─────────────────────────────────────────
    if args.plan:
        resultado["via"] = "plan"
        if llm_necesario and not args.no_llm:
            resultado["nota"] = "La sincronización real invocará el LLM vía OpenRouter (consume créditos)."
        print(json.dumps(resultado, ensure_ascii=False))
        return 0

    if llm_necesario and args.no_llm:
        # Cambio estructural sin permiso LLM: conserva el .tex intacto.
        resultado["status"] = "error"
        resultado["code"] = 3
        resultado["message"] = "Cambios estructurales detectados pero --no-llm está activo. " \
                               "No se tocó el .tex. Revisa manualmente o relanza sin --no-llm."
        print(json.dumps(resultado, ensure_ascii=False))
        return 3

    # 3) Re-traducción LLM por bloque afectado
    blocks = _blocks_tex(tex)
    edits_aplicados = 0
    for item in mapa:
        if item["via"] != "llm":
            continue
        sec_n = int(item["seccion"])
        blk_name = _BLOCK_FOR_MD_SECTION.get(item["seccion"])
        if blk_name is None:
            continue
        start, end = blocks[blk_name]
        block = tex[start:end]
        corpus = md_text + block + str(cambios_por_seccion[item["seccion"]])
        tokens = len(corpus) // 4

        edits = _llm_edits(args.modelo, [], tokens, args.critico, block,
                           item["seccion"], cambios_por_seccion[item["seccion"]]["hunks"])
        edits = _edits_validos(edits, block)
        nuevo_block = _aplicar_edits(block, edits)

        # Invariante de geometría: mismo número de nodos en el bloque
        n_antes = block.count("\\node[")
        n_despues = nuevo_block.count("\\node[")
        if n_antes != n_despues:
            raise RuntimeError(
                f"El LLM alteró la geometría del bloque de la sección {item['seccion']} "
                f"(nodos {n_antes} -> {n_despues}). Abortando sin escribir."
            )

        tex = tex[:start] + nuevo_block + tex[end:]
        edits_aplicados += len(edits)
        item["edits"] = len(edits)

    if edits_aplicados > 0:
        resultado["tex_cambiado"] = True

    resultado["edits_total"] = edits_aplicados
    resultado["via"] = "llm" if edits_aplicados > 0 or llm_necesario else (
        "determinista" if aplicados else "sin_cambios"
    )

    # 4) Escritura atómica
    if args.dry_run or not resultado["tex_cambiado"]:
        resultado["escrito"] = False
    else:
        fd, tmp = tempfile.mkstemp(dir=str(tex_path.parent), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(tex)
        os.replace(tmp, tex_path)
        resultado["escrito"] = True

    print(json.dumps(resultado, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())