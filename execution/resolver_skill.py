#!/usr/bin/env python
"""resolver_skill.py — Resuelve un problema usando un skill estructurado (Fase 2).

Determinista en la capa de decisión: el retrieval, el sandbox y el juicio de
éxito viven EN ESTE SCRIPT. El LLM solo formula (análisis + bloque SymPy).

Etapas (patrón neuro-simbólico del doc de diseño, §4):
  1. Retrieval por embeddings (0 créditos): selecciona las secciones de
     references/ más afines al problema.
  2. Formulador LLM (créditos): análisis paso a paso + bloque SymPy
     autocontenido siguiendo las metodologías/límites/prerrequisitos del skill.
  3. Oráculo (0 créditos): ejecuta el bloque en sandbox aislado.
  4. Reflexión (créditos): ante error del oráculo o JSON inválido, re-formula
     con el error real. Máximo --max-reflexion rondas.

Salida JSON a stdout. Exit codes: 0 ok / 1 args / 2 skill inválido /
3 no resuelto tras agotar reflexión, formulación fallida, o con
--abortar-debil y retrieval de confianza baja.
"""
import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

from llm_client import openrouter_chat  # noqa: E402
from validar_skill_formulas import _escaneo_seguridad  # noqa: E402

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

MAX_SECCION_CHARS = 6000
CACHE_DIR = PROJECT_ROOT / ".tmp" / "resolver_skill"
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
# Calibrado con evidencia (2026-09-03): con MiniLM los problemas dentro de alcance
# dan >= ~0.45 y los fuera de alcance ~0.25. Umbral de 'alta' en 0.55 y alerta de
# confianza débil en 0.35 para separar ambos conjuntos.
CONFIANZA_ALTA = 0.55
ALERTA_SCORE_DEFAULT = 0.35

_PROMPT_SISTEMA = """Eres un formulador formal dentro de un sistema neuro-simbólico.
Debes resolver un problema de ingeniería/electrónica SIGUIENDO ESTRICTAMENTE el
skill que se te adjunta (metodologías paso a paso, límites de aplicabilidad,
prerrequisitos y fórmulas del libro).

REGLAS:
1. RAZONA paso a paso en "analisis", citando qué metodología del skill aplicas y
   verificando los prerrequisitos/límites ANTES de usar cada fórmula. No calcules
   el resultado aún: describe el procedimiento.
2. Al final escribe un bloque de código Python/SymPy en "codigo_sympy" que:
   - sea AUTOCONTENIDO: importe 'from sympy import *' y defina TODAS las variables;
   - calcule el resultado numérico con sympy (evalf, simplify, solve, etc.);
   - termine con un único print() del resultado final legible.
3. El JSON DEBE tener exactamente estas claves:
   {"analisis": "razonamiento paso a paso",
    "codigo_sympy": "código SymPy autocontenido",
    "resultado_esperado": "valor que el código DEBE imprimir (tu predicción)"}

NO uses os, subprocess, eval, exec ni import de módulos no estándar del bloque.
Devuelve SOLO el JSON, sin explicaciones fuera de él."""

_FENCE_RE = re.compile(r"```(?:json|python|py)?\s*(.*?)\s*```", re.DOTALL)


def _arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--skill", required=True, help="Directorio del skill (SKILL.md + references/).")
    p.add_argument("--problema", required=True, help="Enunciado del problema a resolver.")
    p.add_argument("--modelo", default="google/gemini-3.7-flash", help="ID de modelo OpenRouter.")
    p.add_argument("--max-reflexion", type=int, default=3, help="Rondas máx de reflexión (≤3).")
    p.add_argument("--top-k", type=int, default=6, help="Secciones a recuperar por embeddings.")
    p.add_argument("--min-score", type=float, default=0.05, help="Score mínimo de similitud.")
    p.add_argument("--alerta-score", type=float, default=ALERTA_SCORE_DEFAULT,
                   help="Umbral de confianza débil: si el mejor score es < este valor, "
                        "se marca/avisa fundamento bajo (no bloquea, salvo --abortar-debil).")
    p.add_argument("--abortar-debil", action="store_true",
                   help="Convertir la confianza baja en aborto (exit 3) en lugar de solo avisar.")
    p.add_argument("--timeout-s", type=int, default=30, help="Timeout del sandbox SymPy (s).")
    p.add_argument("--max-tokens", type=int, default=None, help="Override de max_tokens de salida.")
    p.add_argument("--temperatura", type=float, default=0.2)
    p.add_argument("--solo-retrieval", action="store_true",
                   help="Solo imprimir las secciones seleccionadas (0 créditos).")
    return p


# ── Etapa 1: retrieval determinista por embeddings (0 créditos) ─────────────

def _secciones(dir_skill: Path) -> list[dict]:
    """Divide las references/ del skill en secciones con cabecera markdown."""
    skill_md = dir_skill / "SKILL.md"
    if not skill_md.is_file():
        return []
    archivos = [skill_md]
    refs = dir_skill / "references"
    if refs.is_dir():
        archivos += sorted(refs.glob("*.md"))
    secciones: list[dict] = []
    for archivo in archivos:
        try:
            texto = archivo.read_text(encoding="utf-8")
        except OSError:
            continue
        if texto.startswith("---"):
            fin = texto.find("\n---", 3)
            if fin != -1:
                texto = texto[fin + 4:]
        partes = re.split(r"(?m)^(#{1,3}\s+.+)$", texto)
        if not partes:
            continue
        encabezado_actual = "(inicio)"
        for chunk in partes:
            m = re.match(r"^#{1,3}\s+(.+)$", chunk)
            if m:
                encabezado_actual = m.group(1).strip()
                continue
            if not chunk.strip():
                continue
            secciones.append({
                "archivo": "SKILL.md" if archivo.name == "SKILL.md" else f"references/{archivo.name}",
                "titulo": encabezado_actual.strip(),
                "texto": chunk.strip()[:MAX_SECCION_CHARS],
            })
    return secciones


_EMB: object | None = None


def _embeddings_model():
    global _EMB
    if _EMB is None:
        from langchain_huggingface import HuggingFaceEmbeddings
        _EMB = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    return _EMB


def _cache_sk(dir_skill: Path) -> Path:
    nombre = dir_skill.name or "skill"
    sub = CACHE_DIR / nombre
    sub.mkdir(parents=True, exist_ok=True)
    return sub


def _indexar(dir_skill: Path, secciones: list[dict]) -> dict:
    cache = _cache_sk(dir_skill)
    hash_txt = hashlib.sha256("\n".join(s["texto"] for s in secciones).encode("utf-8")).hexdigest()
    idx_json = cache / "secciones.json"
    if idx_json.is_file():
        try:
            prev = json.loads(idx_json.read_text(encoding="utf-8"))
            if prev.get("hash") == hash_txt:
                return prev
        except (json.JSONDecodeError, OSError):
            pass
    idx = {"hash": hash_txt, "secciones": secciones}
    idx_json.write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
    return idx


def _retrieval(dir_skill: Path, problema: str, top_k: int, min_score: float) -> list[dict]:
    import numpy as np

    secciones = _secciones(dir_skill)
    if not secciones:
        print(json.dumps(
            {"status": "error", "code": 2,
             "message": f"El skill en {dir_skill} no tiene SKILL.md ni references/."},
            ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
    idx = _indexar(dir_skill, secciones)
    texts = [s["texto"] for s in idx["secciones"]]
    npz = _cache_sk(dir_skill) / "embeddings.npz"
    hash_emb = hashlib.sha256("\u0001".join(texts).encode("utf-8")).hexdigest()
    matriz = None
    if npz.is_file():
        try:
            arch = np.load(npz)
            if arch.get("hash") == hash_emb:
                matriz = arch["matriz"]
            arch.close()
        except (OSError, ValueError):
            matriz = None
    if matriz is None:
        enc = _embeddings_model()
        matriz = np.asarray(enc.embed_documents(texts), dtype=np.float32)
        np.savez(npz, hash=hash_emb, matriz=matriz)
    q = np.asarray(_embeddings_model().embed_query(problema), dtype=np.float32)
    if matriz.ndim == 1 or matriz.size == 0:
        return []
    norm = np.linalg.norm(matriz, axis=1, keepdims=True)
    norm[norm == 0] = 1.0
    scores = (matriz @ q) / (norm[:, 0] * (np.linalg.norm(q) or 1.0))
    order = np.argsort(-scores)
    out = []
    for i in order:
        score = float(scores[i])
        if score < min_score:
            break
        out.append({**idx["secciones"][i], "score": round(score, 4)})
        if len(out) >= top_k:
            break
    return out


def _nivel_confianza(secciones: list[dict], alerta_score: float) -> dict:
    """Clasifica la confianza del retrieval según el mejor score coseno.

    - 'alta':  mejor_score >= CONFIANZA_ALTA (0.55); fundamento sólido
    - 'media': mejor_score >= alerta_score (0.35): aceptable
    - 'baja':  mejor_score < alerta_score: fundamento débil → aviso/aborto
    Umbrales calibrados con evidencia (ver CONFIANZA_ALTA / ALERTA_SCORE_DEFAULT).
    Determinista: solo depende de los scores ya calculados.
    """
    mejor = max((s.get("score") or 0.0) for s in secciones) if secciones else 0.0
    if not secciones:
        nivel, alerta = "baja", "No hay secciones recuperadas."
    elif mejor >= CONFIANZA_ALTA:
        nivel, alerta = "alta", ""
    elif mejor >= alerta_score:
        nivel, alerta = "media", ""
    else:
        nivel, alerta = "baja", (
            f"El mejor score de retrieval ({mejor:.3f}) es inferior al umbral de "
            f"confianza ({alerta_score:.2f}); la respuesta puede apoyarse en "
            f"conocimiento débil o fuera de alcance del skill.")
    return {
        "nivel": nivel,
        "mejor_score": round(mejor, 4),
        "alerta": alerta,
        "alerta_score": alerta_score,
    }


# ── Etapa 3: oráculo determinista (0 créditos) ──────────────────────────────

def _oraculo(src: str, timeout_s: int) -> dict:
    motivo = _escaneo_seguridad(src)
    if motivo:
        return {"exit_code": -1, "stdout": "", "stderr": motivo, "timeout": False, "inseguro": True}
    try:
        ast.parse(src)
    except SyntaxError as exc:
        return {"exit_code": -2, "stdout": "", "stderr": f"sintaxis: línea {exc.lineno}: {exc.msg}",
                "timeout": False, "inseguro": False}
    try:
        proc = subprocess.run([sys.executable, "-c", src], capture_output=True, text=True,
                              timeout=timeout_s, encoding="utf-8")
    except subprocess.TimeoutExpired:
        return {"exit_code": -3, "stdout": "", "stderr": f"tiempo excedido ({timeout_s}s)",
                "timeout": True, "inseguro": False}
    except OSError as exc:
        return {"exit_code": -4, "stdout": "", "stderr": f"no se pudo lanzar sandbox: {exc}",
                "timeout": False, "inseguro": False}
    return {
        "exit_code": proc.returncode,
        "stdout": (proc.stdout or "").strip()[-400:],
        "stderr": ((proc.stderr or "").strip().splitlines()[-1][:400]) if proc.returncode != 0 else "",
        "timeout": False,
        "inseguro": False,
    }


# ── Etapa 2/4: formulador LLM + reflexión (créditos) ────────────────────────

def _extraer_json_respuesta(texto: str) -> dict:
    m = _FENCE_RE.search(texto)
    candidato = m.group(1).strip() if m else texto.strip()
    if not (candidato.startswith("{") and candidato.endswith("}")):
        start = candidato.find("{")
        end = candidato.rfind("}")
        if start == -1 or end <= start:
            return {}
        candidato = candidato[start:end + 1]
    candidato = re.sub(r",\s*([}\]])", r"\1", candidato)
    try:
        return json.loads(candidato)
    except json.JSONDecodeError:
        return _find_balanced_json(candidato)


def _find_balanced_json(text: str) -> dict:
    """Escaneo por llaves balanceadas respetando strings (ver .agent/python.md)."""
    start = text.find("{")
    if start == -1:
        return {}
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
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return {}
    return {}


def _formular(messages: list[dict], modelo: str, max_tokens: int | None,
              temperatura: float) -> tuple[str, dict]:
    kwargs: dict = {"messages": messages, "model": modelo, "api_key": OPENROUTER_API_KEY,
                    "temperature": temperatura, "max_tokens": max_tokens or 8192,
                    "title": "resolver_skill"}
    if "deepseek" in modelo or "kimi" in modelo:
        kwargs["reasoning"] = {"enabled": False}
    return openrouter_chat(**kwargs)


def _bloques_contexto(secciones: list[dict]) -> str:
    partes = []
    for s in secciones:
        partes.append(f"## {s['archivo']} — {s['titulo']}\n{s['texto']}")
    return "\n\n".join(partes)


def _mensaje_usuario(problema: str, secciones: list[dict], confianza: dict | None = None,
                     feedback: str | None = None) -> str:
    bloque = _bloques_contexto(secciones)
    aviso = ""
    if confianza and confianza.get("nivel") == "baja":
        aviso = ("AVISO DE FUNDAMENTO DÉBIL: las secciones recuperadas tienen baja "
                 "similitud con el problema. Si el problema cae FUERA del alcance del "
                 "skill, indícalo en 'analisis' (p. ej. 'no cubierto por el libro') en "
                 "lugar de forzar una fórmula o inventar datos.\n\n")
    if feedback:
        return (f"El intento anterior fracasó. Corrige solo el error sin cambiar la estrategia.\n"
                f"ERROR DETECTADO:\n{feedback}\n\n"
                f"PROBLEMA (el mismo):\n{problema}\n\n{aviso}SKILL (secciones recuperadas):\n{bloque}")
    return f"PROBLEMA:\n{problema}\n\n{aviso}SKILL (secciones recuperadas):\n{bloque}"


def main() -> int:
    args = _arg_parser().parse_args()
    if not OPENROUTER_API_KEY:
        print(json.dumps({"status": "error", "code": 2,
                          "message": "Falta OPENROUTER_API_KEY en .env."}, ensure_ascii=False), file=sys.stderr)
        return 2
    dir_skill = Path(args.skill).expanduser()
    if not (dir_skill / "SKILL.md").is_file():
        print(json.dumps({"status": "error", "code": 2,
                          "message": f"No es un skill válido (falta SKILL.md): {dir_skill}"},
                         ensure_ascii=False), file=sys.stderr)
        return 2
    max_reflexion = max(0, min(args.max_reflexion, 3))

    secciones = _retrieval(dir_skill, args.problema, args.top_k, args.min_score)
    confianza = _nivel_confianza(secciones, args.alerta_score)
    if args.solo_retrieval:
        print(json.dumps({"status": "ok", "confianza_retrieval": confianza, "secciones_usadas": [
            {k: s[k] for k in ("archivo", "titulo", "score")} for s in secciones
        ]}, ensure_ascii=False))
        return 0
    if not secciones:
        print(json.dumps({"status": "error", "code": 3,
                          "message": "El retrieval no encontró secciones afines al problema (baja el umbral).",
                          "confianza_retrieval": confianza},
                         ensure_ascii=False), file=sys.stderr)
        return 3
    if args.abortar_debil and confianza["nivel"] == "baja":
        print(json.dumps({"status": "error", "code": 3,
                          "message": confianza["alerta"],
                          "confianza_retrieval": confianza,
                          "sugerencia": "Usa --abortar-debil solo para repos rígidos; "
                                        "o baja --alerta-score / amplía el skill."},
                         ensure_ascii=False), file=sys.stderr)
        return 3

    sistema = {"role": "system", "content": _PROMPT_SISTEMA}
    messages = [sistema]
    tokens_llm = {"prompt": 0, "respuesta": 0, "total": 0}
    ultimo_intento: dict = {}
    feedback: str | None = None
    reflexiones = 0
    oraculo: dict | None = None

    for intento in range(max_reflexion + 1):
        if intento > 0:
            reflexiones += 1
        messages = [sistema, {"role": "user", "content": _mensaje_usuario(
            args.problema, secciones, confianza, feedback)}]
        try:
            raw, tok = _formular(messages, args.modelo, args.max_tokens, args.temperatura)
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"status": "error", "code": 5,
                              "message": f"Fallo llamando al LLM: {exc}"}, ensure_ascii=False), file=sys.stderr)
            return 5
        for k, v in tok.items():
            tokens_llm[k] = tokens_llm.get(k, 0) + v
        tarde = _extraer_json_respuesta(raw)
        if not tarde:
            feedback = "No se pudo extraer un JSON válido de la respuesta. Devuelve SOLO el JSON pedido."
            continue
        codigo = str(tarde.get("codigo_sympy") or "").strip()
        if not codigo:
            feedback = "Falta la clave 'codigo_sympy'. Debe contener el bloque SymPy."
            continue
        oraculo = _oraculo(codigo, args.timeout_s)
        ultimo_intento = {"analisis": tarde.get("analisis", ""),
                          "codigo_sympy": codigo,
                          "resultado_esperado": tarde.get("resultado_esperado", "")}
        if oraculo["exit_code"] == 0:
            break
        feedback = (oraculo["stderr"] or oraculo["stdout"] or f"exit code {oraculo['exit_code']}").strip()

    resuelto = bool(oraculo) and oraculo["exit_code"] == 0
    salida = {
        "status": "ok" if resuelto else "error",
        "code": 0 if resuelto else 3,
        "problema": args.problema,
        "skill": str(dir_skill),
        "modelo": args.modelo,
        "confianza_retrieval": confianza,
        "secciones_usadas": [{k: s[k] for k in ("archivo", "titulo", "score")} for s in secciones],
        "analisis": ultimo_intento.get("analisis", ""),
        "codigo_sympy": ultimo_intento.get("codigo_sympy", ""),
        "resultado_esperado": ultimo_intento.get("resultado_esperado", ""),
        "resultado_oraculo": oraculo if resuelto or oraculo else {"exit_code": -5, "stdout": "", "stderr": "sin intento"},
        "resultado_final": (oraculo or {}).get("stdout", "") if resuelto else "",
        "reflexiones_usadas": reflexiones,
        "tokens": tokens_llm,
    }
    print(json.dumps(salida, ensure_ascii=False))
    return 0 if resuelto else 3


if __name__ == "__main__":
    sys.exit(main())