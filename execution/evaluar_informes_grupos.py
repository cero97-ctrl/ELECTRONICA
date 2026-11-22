#!/usr/bin/env python3
"""Capa 3: evaluar informes Markdown de los repositorios de los grupos.

No decide nada en el chat. Lee un descriptor privado (grupo -> repo -> commit ->
informe), baja instantáneas inmutables con la sesión `gh` ya autenticada, corre
chequeos deterministas y envía cada informe a Gemini. La nota SIEMPRE la calcula
`calcular_nota()` con los pesos de la rúbrica; el modelo solo puntúa criterios.

Códigos de salida: 0 ok · 1 E/S · 3 descriptor/rúbrica inválida ·
4 red/credenciales · 5 JSON del modelo inválido · 6 cobertura incompleta.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "execution"))

from evaluar_examen import calcular_nota, cargar_rubrica  # noqa: E402
from estilo_infografia import PREAMBULO_INFOGRAFIA, banda_titulo  # noqa: E402

try:
    import yaml
except ImportError:  # pragma: no cover - dependencia declarada del repo
    yaml = None

OK = 0
E_SCRITURA = 1
CONFIG_INVALIDA = 3
RED = 4
MODELO_INVALIDO = 5
COBERTURA_INCOMPLETA = 6

MAX_BYTES_ARCHIVO = 900_000
CAMPOS_PROHIBIDOS = (
    "puntaje_sugerido", "nivel_desempeno", "nota", "nota_total",
    "total", "score", "calificacion",
)

PATRONES_SECRETO = (
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{30,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"),
)
RUTA_RE = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"((?:semana_\d+|evidencia|scripts?|lab)/[A-Za-z0-9_./-]+"
    r"|[A-Za-z0-9_.-]+\.(?:txt|log|csv|json|sha256|ps1|sh|png|jpe?g|pdf|yaml|yml))",
    re.IGNORECASE,
)
CEDULA_RE = re.compile(r"\b[VE]-\d{6,9}\b", re.IGNORECASE)
CORREO_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


# ── Funciones PURAS (testeables sin red) ──────────────────────────────────────

def normalizar(texto: str) -> str:
    """Clave comparable: minúsculas, sin acentos ni separadores."""
    plano = unicodedata.normalize("NFKD", str(texto).lower())
    sin_acentos = "".join(c for c in plano if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", sin_acentos)


def anonimizar(texto: str) -> str:
    """Los informes pueden traer cédulas; ninguna sale del JSON ni del acta."""
    limpio = CEDULA_RE.sub("[IDENTIFICADOR]", str(texto))
    return CORREO_RE.sub("[CORREO]", limpio)


def cargar_descriptor(ruta: str | Path) -> dict:
    """Lee y valida el descriptor. Falla ruidosamente antes de tocar la red."""
    if yaml is None:
        raise RuntimeError("PyYAML no está instalado; no se puede validar el descriptor")
    obj = Path(ruta)
    if not obj.is_file():
        raise FileNotFoundError(f"Descriptor no encontrado: {obj}")
    datos = yaml.safe_load(obj.read_text(encoding="utf-8"))
    if not isinstance(datos, dict):
        raise ValueError("El descriptor debe ser un mapa YAML")

    for clave in ("semana", "rubrica", "grupos"):
        if clave not in datos:
            raise ValueError(f"Descriptor sin la clave obligatoria '{clave}'")
    if not isinstance(datos["semana"], int) or datos["semana"] < 1:
        raise ValueError("'semana' debe ser un entero positivo")
    if "evaluar_corte" in datos and not isinstance(datos["evaluar_corte"], bool):
        raise ValueError("'evaluar_corte' debe ser booleano")
    datos.setdefault("evaluar_corte", True)  # las semanas 2-9 evalúan plazo por defecto

    backend = datos.get("backend", "gemini")
    if backend != "gemini":
        raise ValueError(
            f"backend={backend!r}: este flujo solo usa Gemini free; "
            "cualquier otro backend requiere autorización explícita de gasto"
        )
    datos["backend"] = backend
    if not datos.get("modelo"):
        raise ValueError("Falta 'modelo' (nombre del modelo Gemini)")

    grupos = datos["grupos"]
    if not isinstance(grupos, list) or not grupos:
        raise ValueError("'grupos' debe ser una lista no vacía")
    for g in grupos:
        if not isinstance(g, dict):
            raise ValueError("Cada entrada de 'grupos' debe ser un mapa")
        for clave in ("grupo", "rol", "repo", "commit", "informe"):
            if not g.get(clave):
                raise ValueError(f"Grupo sin '{clave}': {g}")
        if not re.fullmatch(r"[0-9a-f]{40}", str(g["commit"])):
            raise ValueError(f"commit no válido (debe ser SHA-1 de 40 hex): {g['commit']}")
    return datos


def validar_cobertura(datos: dict) -> list[dict]:
    """Exige cobertura exacta; un grupo de más o de menos invalida la corrida."""
    esperados = datos.get("grupos_esperados")
    if not isinstance(esperados, list) or not esperados:
        raise ValueError("Falta 'grupos_esperados' en el descriptor")
    encontrados = [g["grupo"] for g in datos["grupos"]]
    if len(encontrados) != len(set(encontrados)):
        raise ValueError(f"Grupos repetidos en el descriptor: {encontrados}")
    faltan = sorted(set(esperados) - set(encontrados))
    sobran = sorted(set(encontrados) - set(esperados))
    if faltan or sobran:
        raise ValueError(
            f"Cobertura incompleta: faltan {faltan}, sobran {sobran}"
        )
    return sorted(datos["grupos"], key=lambda g: int(g["grupo"]))


def resolver_informe(rutas: list[str], declarado: str) -> str | None:
    """Primero coincide literal; si no, una sola vez sin distinción de mayúsculas."""
    if declarado in rutas:
        return declarado
    candidatos = [r for r in rutas if r.lower() == declarado.lower()]
    return candidatos[0] if len(candidatos) == 1 else None


def extraer_rutas_citadas(texto: str) -> list[str]:
    """Rutas de evidencia citadas en el Markdown, sin duplicados y ordenadas."""
    return sorted({m.group(1) for m in RUTA_RE.finditer(texto)})


def _normalizar_ruta(token: str) -> str:
    """Los informes Windows mezclan '\\' y './'; el repo siempre usa '/'."""
    return str(token).replace("\\", "/").lstrip("./")


def resolver_ruta_citada(token: str, rutas: set[str]) -> str | None:
    """Un nombre suelto se busca en las carpetas habituales del laboratorio."""
    limpio = _normalizar_ruta(token)
    candidatos = [limpio]
    if not limpio.startswith("semana_01/"):
        candidatos += [
            f"semana_01/{limpio}", f"semana_01/evidencia/{limpio}",
            f"semana_01/scripts/{limpio}", f"semana_01/script/{limpio}",
            f"scripts/{limpio}", f"lab/{limpio}",
        ]
    for c in candidatos:
        if c in rutas:
            return c
    return None


def parsear_hashes(texto: str) -> list[tuple[str, str]]:
    """Lee líneas `sha256  ruta` (o `sha256 *ruta`) de los ficheros .sha256."""
    pares: list[tuple[str, str]] = []
    for linea in texto.splitlines():
        m = re.match(r"^\s*([0-9a-fA-F]{64})\s+[* ]?\s*(\S.*?)\s*$", linea)
        if m:
            pares.append((m.group(1).lower(), m.group(2).strip()))
    return pares


def verificar_hashes(archivos: dict[str, bytes]) -> dict:
    """Contrasta cada sha256 declarado contra el archivo descargado."""
    declarados: list[tuple[str, str, str]] = []  # (sha, ruta, fichero_hash)
    for ruta_hash, contenido in sorted(archivos.items()):
        if not ruta_hash.lower().endswith(".sha256"):
            continue
        try:
            texto = contenido.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for sha, ruta in parsear_hashes(texto):
            declarados.append((sha, _normalizar_ruta(ruta), ruta_hash))

    rutas = set(archivos)
    verificados, fallidos, sin_archivo = [], [], []
    for sha, ruta, fichero_hash in declarados:
        base = str(Path(fichero_hash).parent)
        resuelto = resolver_ruta_citada(ruta, rutas)
        if resuelto is None and base:
            for candidato in (f"{base}/{ruta}", ruta, f"semana_01/{ruta}",
                              f"semana_01/evidencia/capturas/{ruta}"):
                if candidato in rutas:
                    resuelto = candidato
                    break
        if resuelto is None:
            # Último recurso: sufijo único. G3 declara capturas con carpetas
            # Windows que no aparecen literalmente en el árbol del repo.
            por_sufijo = [r for r in rutas if r.endswith("/" + ruta)]
            if len(por_sufijo) == 1:
                resuelto = por_sufijo[0]
        if resuelto is None:
            sin_archivo.append(ruta)
            continue
        real = hashlib.sha256(archivos[resuelto]).hexdigest()
        (verificados if real == sha else fallidos).append(resuelto)
    return {
        "declarados": len(declarados),
        "verificados": sorted(set(verificados)),
        "fallidos": sorted(set(fallidos)),
        "sin_archivo": sorted(set(sin_archivo)),
    }


def detectar_secretos(archivos: dict[str, bytes]) -> list[str]:
    """Devuelve solo las rutas sospechosas, nunca el valor del secreto."""
    hallazgos: list[str] = []
    for ruta, contenido in sorted(archivos.items()):
        if Path(ruta).name in (".env", ".env.local", "id_rsa") or ruta.endswith(".pem"):
            hallazgos.append(ruta)
            continue
        try:
            texto = contenido.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if any(p.search(texto) for p in PATRONES_SECRETO):
            hallazgos.append(ruta)
    return hallazgos


def evaluar_puntualidad(fecha_commit: str, corte: str, evaluar_corte: bool) -> dict:
    """El plazo es dato, no nota. Con evaluar_corte=false queda 'no_evaluada'."""
    try:
        # GitHub devuelve UTC con 'Z'; fromisoformat solo lo entiende desde 3.11.
        fecha = datetime.fromisoformat(str(fecha_commit).replace("Z", "+00:00"))
        limite = datetime.fromisoformat(str(corte).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Fecha ISO inválida en el descriptor: {exc}") from exc
    if not evaluar_corte:
        return {
            "estado": "no_evaluada",
            "fecha_commit": fecha_commit,
            "corte": corte,
            "aviso": "Plazo no evaluado por decisión del docente para esta corrida.",
        }
    return {
        "estado": "en_plazo" if fecha <= limite else "tardia",
        "fecha_commit": fecha_commit,
        "corte": corte,
        "aviso": "" if fecha <= limite else "Entregada fuera del plazo declarado.",
    }


def armar_system_instruction(pesos: dict[str, float], rubrica_texto: str) -> str:
    """El modelo solo puntúa criterios: la aritmética la hace el programa."""
    criterios = "\n".join(
        f'- "{nombre}" (peso máximo {peso:g})' for nombre, peso in pesos.items()
    )
    return f"""Eres un corrector de informes técnicos de un curso de ciberseguridad.
Puntúa SOLO los criterios de la rúbrica, uno por cada criterio listado:

{criterios}

{rubrica_texto}

Devuelve UN objeto JSON con esta forma exacta:
{{"items": [
  {{"item": "nombre exacto del criterio", "puntaje_parcial": "2.4/3.0",
    "justificacion": "por qué ese puntaje, con referencia a una sección o evidencia",
    "evidencia": "ruta o cita breve del informe"}}
], "observaciones": "comentario breve para el docente"}}

Reglas estrictas:
- Usa el nombre EXACTO de cada criterio y un denominador igual a su peso.
- No emitas nota total, promedio, nivel ni ningún campo de calificación global.
- Puntúa los CINCO criterios aunque falte evidencia (en ese caso justifica el 0).
- No inventes evidencia: si no aparece en el informe, dilo en la justificación.
- No incluyas nombres, cédulas, correos ni datos personales en tus respuestas.
- El puntaje_parcial debe ser una cadena "obtenido/denominador" con números."""


def validar_items(datos: object, pesos: dict[str, float]) -> tuple[list[dict], list[str], str]:
    """Valida la FORMA del JSON del modelo y descarta cualquier nota que emita."""
    avisos: list[str] = []
    if not isinstance(datos, dict):
        raise ValueError("La respuesta del modelo no es un objeto JSON")
    for clave in CAMPOS_PROHIBIDOS:
        if clave in datos:
            avisos.append(f"Se descartó el campo '{clave}' emitido por el modelo.")
    crudos = datos.get("items")
    if not isinstance(crudos, list) or not crudos:
        raise ValueError("La respuesta del modelo no trae 'items' no vacío")

    permitidos = {normalizar(k): k for k in pesos}
    limpios: list[dict] = []
    vistos: set[str] = set()
    for crudo in crudos:
        if not isinstance(crudo, dict):
            avisos.append("Se descartó un ítem que no es un objeto.")
            continue
        nombre = str(crudo.get("item") or crudo.get("criterio") or "").strip()
        clave = normalizar(nombre)
        if clave not in permitidos:
            avisos.append(f"Se descartó el criterio fuera de rúbrica {nombre!r}.")
            continue
        if clave in vistos:
            avisos.append(f"Se descartó el criterio duplicado {nombre!r}.")
            continue
        vistos.add(clave)
        justificacion = anonimizar(str(crudo.get("justificacion") or "")).strip()
        if len(justificacion) < 15:
            avisos.append(f"Justificación demasiado corta para {nombre!r}; revisar.")
        limpios.append({
            "item": permitidos[clave],
            "puntaje_parcial": crudo.get("puntaje_parcial"),
            "justificacion": justificacion,
            "evidencia": anonimizar(str(crudo.get("evidencia") or "")).strip(),
        })
    if not limpios:
        raise ValueError("Ningún ítem de la respuesta pertenece a la rúbrica")
    observaciones = anonimizar(str(datos.get("observaciones") or "")).strip()
    return limpios, avisos, observaciones


# ── Capa de E/S (red, disco, SDK) ─────────────────────────────────────────────

def _gh(*argumentos: str) -> str:
    """Invoca gh con la sesión ya autenticada; sin credenciales en el código.

    `evaluar_examen.py` carga `.env` al importarse y eso inyecta un GITHUB_TOKEN
    que `gh` prefiere sobre el token del keyring (401 Bad credentials). Este
    flujo usa la sesión interactiva de la cuenta cero97-ctrl: se retiran esas
    variables del entorno del subproceso, sin imprimirlas ni guardarlas.
    """
    entorno = {k: v for k, v in os.environ.items()
               if k not in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN",
                            "GITHUB_ENTERPRISE_TOKEN")}
    try:
        proc = subprocess.run(
            ["gh", "api", *argumentos], capture_output=True, text=True,
            check=True, env=entorno,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("GitHub CLI (gh) no está instalado o no está en PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"gh api falló: {' '.join(argumentos)} :: {exc.stderr.strip()[:300]}"
        ) from exc
    return proc.stdout


def descargar_snapshot(repo: str, sha: str, destino: Path) -> dict[str, bytes]:
    """Baja un árbol fijado por SHA; si ya está en caché, lo reutiliza."""
    destino.mkdir(parents=True, exist_ok=True)
    indice = destino / "_indice.json"
    if indice.is_file():
        datos = json.loads(indice.read_text(encoding="utf-8"))
        if datos.get("sha") == sha:
            return {
                r: (destino / r).read_bytes()
                for r in datos["rutas"]
                if (destino / r).is_file()
            }

    salida = _gh(
        f"repos/{repo}/git/trees/{sha}?recursive=1",
        "--jq", '.tree[] | select(.type=="blob") | [.path,.size] | @tsv',
    )
    rutas: list[str] = []
    for linea in salida.splitlines():
        partes = linea.split("\t")
        if len(partes) != 2:
            continue
        ruta, tamano = partes
        try:
            if int(tamano) > MAX_BYTES_ARCHIVO:
                continue
        except ValueError:
            continue
        if not (ruta.startswith("semana_01/") or ruta in ("README.md", "LICENSE")
                or ruta.startswith(("scripts/", "script/", "lab/"))):
            continue
        rutas.append(ruta)

    archivos: dict[str, bytes] = {}
    for ruta in sorted(rutas):
        contenido = _gh(f"repos/{repo}/contents/{ruta}?ref={sha}", "--jq", ".content")
        try:
            archivos[ruta] = base64.b64decode("".join(contenido.split()))
        except (ValueError, TypeError) as exc:
            raise RuntimeError(f"Contenido base64 inválido en {repo}:{ruta}: {exc}") from exc
        destino_archivo = destino / ruta
        destino_archivo.parent.mkdir(parents=True, exist_ok=True)
        destino_archivo.write_bytes(archivos[ruta])
    indice.write_text(
        json.dumps({"sha": sha, "repo": repo, "rutas": sorted(archivos)},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return archivos


def llamar_gemini(modelo: str, system: str, user_text: str, api_key: str) -> tuple[dict, dict]:
    """Gemini free con JSON forzado y thoughts desactivados. Máx. 3 intentos."""
    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError as exc:  # pragma: no cover - dependencia del entorno
        raise RuntimeError("SDK de Gemini no instalado: pip install google-genai") from exc

    client = genai.Client(api_key=api_key)
    ultimo: Exception | None = None
    for intento in range(1, 4):
        try:
            config = genai_types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.1,
                max_output_tokens=8192,
                response_mime_type="application/json",
                thinking_config=genai_types.ThinkingConfig(
                    thinking_budget=0, include_thoughts=False
                ),
            )
            try:
                respuesta = client.models.generate_content(
                    model=modelo, contents=user_text, config=config
                )
            except Exception as exc:  # modelos sin soporte de thinking_config
                if "thinking" not in str(exc).lower():
                    raise
                config.thinking_config = None
                respuesta = client.models.generate_content(
                    model=modelo, contents=user_text, config=config
                )
            tokens: dict = {}
            try:
                tokens = {
                    "prompt": respuesta.usage_metadata.prompt_token_count,
                    "respuesta": respuesta.usage_metadata.candidates_token_count,
                }
            except (AttributeError, TypeError):
                pass
            return json.loads(respuesta.text), tokens
        except (ValueError, json.JSONDecodeError) as exc:
            ultimo = exc  # JSON roto: se reintenta dentro del budget de 3
        except Exception as exc:
            if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                raise RuntimeError("Cuota free de Gemini agotada (429)") from exc
            ultimo = exc
    raise RuntimeError(f"Gemini no devolvió un JSON válido tras 3 intentos: {ultimo}")


def chequear_grupo(g: dict, archivos: dict[str, bytes], evaluar_corte: bool,
                   corte: str) -> tuple[dict, str]:
    """Chequeos deterministas. Devuelve (informe_check, texto_del_informe)."""
    rutas = list(archivos)
    informe = resolver_informe(rutas, g["informe"])
    if informe is None:
        raise FileNotFoundError(
            f"Informe de G{g['grupo']} no encontrado (¿mayúsculas?): {g['informe']}"
        )
    texto = archivos[informe].decode("utf-8", errors="replace")
    citadas = extraer_rutas_citadas(texto)
    resueltas = {c: resolver_ruta_citada(c, set(rutas)) for c in citadas}
    hashes = verificar_hashes(archivos)
    # "Rojo" no debe recortarse a "roj": se compara la primera palabra del rol.
    clave_rol = "legal" if normalizar(g["rol"]).startswith("legal") else normalizar(g["rol"]).split()[0]
    rol_declarado = clave_rol in normalizar(texto[:4000])
    check = {
        "informe": informe,
        "informe_bytes": len(archivos[informe]),
        "fecha_commit": "",  # la rellena quien consultó el commit
        "puntualidad": evaluar_puntualidad(g.get("fecha_commit", corte), corte,
                                          evaluar_corte),
        "rutas_citadas": {
            "citadas": len(citadas),
            "faltan": sorted(c for c, r in resueltas.items() if r is None),
        },
        "hashes": hashes,
        "secretos": detectar_secretos(archivos),
        "rol_declarado_en_informe": bool(rol_declarado),
    }
    return check, texto


def _tex(texto: str) -> str:
    """Escapa texto libre para LaTeX crudo (tablas y notas)."""
    salida = str(texto)
    for viejo, nuevo in (
        ("\\", r"\textbackslash{}"), ("{", r"\{"), ("}", r"\}"),
        ("%", r"\%"), ("&", r"\&"), ("#", r"\#"), ("_", r"\_"),
        ("$", r"\$"), ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}"),
    ):
        salida = salida.replace(viejo, nuevo)
    return salida


def generar_acta_tex(resultados: list[dict], descriptor: dict, ruta: Path) -> Path:
    """Acta privada separada: 4 grupos, nota del programa y avisos."""
    filas = []
    for r in resultados:
        nota = r["nota"]
        valor = f"{nota['puntaje_numerico']:.2f}" if nota["nota_fiable"] else "No publicable"
        avisos = " ".join(r["avisos"][:3]) or "Sin avisos"
        filas.append(
            f"\\textbf{{G{r['grupo']}}} & {_tex(r['rol'])} & {valor} & "
            f"\\small {_tex(avisos)} \\\\"
        )
    nota_media = ""
    notas = [r["nota"]["puntaje_numerico"] for r in resultados
             if r["nota"]["nota_fiable"]]
    if len(notas) == len(resultados):
        nota_media = f"Promedio de los {len(notas)} grupos: {sum(notas)/len(notas):.2f}/10."

    cuerpo = f"""{PREAMBULO_INFOGRAFIA}

\\begin{{document}}
{banda_titulo(f"Evaluación de informes — semana {descriptor['semana']:02d}",
              "Ciberseguridad Aplicada · acta privada · resultado separado del examen")}

\\begin{{tcolorbox}}[cajaContenido, title={{Criterio y alcance}}]
Rúbrica: \\texttt{{{_tex(descriptor['rubrica'])}}}. La nota la calcula el programa a partir de los
parciales del modelo y los pesos de la rúbrica. El modelo no emite nota total.
Instrumento distinto del cuestionario de la Evaluación 1; no se fusiona con esa acta.
\\end{{tcolorbox}}

\\vspace{{6pt}}
\\begin{{center}}
\\begin{{tabular}}{{@{{}}c c c p{{7.2cm}}@{{}}}}
\\toprule
Grupo & Rol & Nota & Avisos \\\\
\\midrule
{chr(10).join(filas)}
\\bottomrule
\\end{{tabular}}
\\end{{center}}

\\vspace{{6pt}}
{_tex(nota_media)}

\\begin{{tcolorbox}}[cajaContenido, title={{Trazabilidad}}]
Descriptor y JSON con las justificaciones: \\texttt{{.tmp/evaluacion\\_informes\\_grupos/}}.
Los repositorios se fijaron por SHA de commit. La fecha de entrega no se evaluó en esta
corrida por decisión del docente; las semanas siguientes sí la evalúan por defecto.
\\end{{tcolorbox}}

\\end{{document}}
"""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(cuerpo, encoding="utf-8")
    return ruta


def descriptor_desde_resultado(resultado: dict) -> dict:
    """Reconstruye el descriptor mínimo que `generar_acta_tex` necesita.

    Permite regenerar el acta desde el JSON ya evaluado, sin volver a llamar al
    modelo. Es función pura: mismo JSON → mismo descriptor.
    """
    if not isinstance(resultado, dict) or "grupos" not in resultado:
        raise ValueError("El JSON de evaluación no tiene la clave 'grupos'")
    if "semana" not in resultado:
        raise ValueError("El JSON de evaluación no declara 'semana'")
    return {"semana": resultado["semana"], "rubrica": resultado.get("rubrica", "")}


# ── Orquestación de la capa 3 ─────────────────────────────────────────────────

def evaluar(descriptor: dict, rubrica_texto: str, pesos: dict[str, float],
            grupos: list[dict], base: Path, solo_chequeos: bool,
            api_key: str | None) -> dict:
    system = armar_system_instruction(pesos, rubrica_texto)
    salida: list[dict] = []
    for g in grupos:
        destino = base / "snapshots" / f"grupo_{g['grupo']}" / str(g["commit"])[:12]
        archivos = descargar_snapshot(g["repo"], g["commit"], destino)
        check, texto = chequear_grupo(
            g, archivos, descriptor["evaluar_corte"], descriptor.get("corte", "")
        )
        fecha = _gh(
            f"repos/{g['repo']}/commits/{g['commit']}", "--jq", ".commit.author.date"
        ).strip()
        check["fecha_commit"] = fecha
        check["puntualidad"] = evaluar_puntualidad(
            fecha, descriptor.get("corte", ""), descriptor["evaluar_corte"]
        )
        registro: dict = {
            "grupo": g["grupo"],
            "rol": g["rol"],
            "repo": g["repo"],
            "commit": g["commit"],
            "chequeos": check,
            "avisos": [],
        }
        for campo in ("rutas_citadas", "hashes", "secretos", "puntualidad",
                      "rol_declarado_en_informe"):
            valor = check[campo]
            if campo == "rutas_citadas" and valor["faltan"]:
                registro["avisos"].append(
                    f"{len(valor['faltan'])} ruta(s) citada(s) sin archivo en el repo: "
                    + ", ".join(valor["faltan"][:6])
                )
            if campo == "hashes":
                if valor["fallidos"]:
                    registro["avisos"].append(
                        "Hash(es) que no cuadran: " + ", ".join(valor["fallidos"][:6])
                    )
                if valor["sin_archivo"]:
                    registro["avisos"].append(
                        "Hash(es) sin archivo: " + ", ".join(valor["sin_archivo"][:6])
                    )
            if campo == "secretos" and valor:
                registro["avisos"].append(
                    "Posibles secretos en " + ", ".join(valor[:4])
                )
            if campo == "puntualidad" and valor["aviso"]:
                registro["avisos"].append(valor["aviso"])
            if campo == "rol_declarado_en_informe" and not valor:
                registro["avisos"].append(
                    f"El informe no declara explícitamente el rol {g['rol']!r}."
                )

        if solo_chequeos:
            registro["nota"] = {"nota_fiable": False, "puntaje_numerico": None}
            salida.append(registro)
            continue

        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY no encontrada (necesaria para Gemini free)")
        user_text = (
            f"Grupo {g['grupo']} · rol {g['rol']} · semana {descriptor['semana']}.\n"
            "Chequeos deterministas previos (no son nota): "
            + json.dumps(check, ensure_ascii=False)
            + "\n--- INICIO DEL INFORME ---\n" + texto
            + "\n--- FIN DEL INFORME ---"
        )
        crudo, tokens = llamar_gemini(descriptor["modelo"], system, user_text, api_key)
        items, avisos_forma, observaciones = validar_items(crudo, pesos)
        datos_nota, avisos_nota = calcular_nota(items, pesos=pesos)
        registro.update({
            "items": items,
            "observaciones": observaciones,
            "nota": datos_nota,
            "tokens": tokens,
        })
        registro["avisos"].extend(avisos_forma + avisos_nota)
        salida.append(registro)
        print(
            json.dumps({"progreso": f"G{g['grupo']} evaluado",
                        "nota": datos_nota.get("puntaje_sugerido")},
                       ensure_ascii=False),
            flush=True,
        )

    return {
        "estado": "chequeos" if solo_chequeos else "ok",
        "curso": descriptor["curso"],
        "semana": descriptor["semana"],
        "rubrica": descriptor.get("rubrica", ""),
        "modelo": descriptor["modelo"],
        "evaluar_corte": descriptor["evaluar_corte"],
        "grupos": salida,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--descriptor", required=True)
    parser.add_argument("--salida-json", default=".tmp/evaluacion_informes_grupos/evaluacion.json")
    parser.add_argument("--acta-tex", default="")
    parser.add_argument("--check", action="store_true",
                        help="Solo descarga y chequeos deterministas; sin llamadas a Gemini")
    parser.add_argument("--desde-json", action="store_true",
                        help="Regenera el acta desde --salida-json sin llamar al modelo")
    parser.add_argument("--json", action="store_true", help="Resumen final en JSON")
    args = parser.parse_args(argv)

    if args.desde_json:
        try:
            datos = json.loads(Path(args.salida_json).read_text(encoding="utf-8"))
            desc = descriptor_desde_resultado(datos)
            if args.acta_tex:
                generar_acta_tex(datos["grupos"], desc, Path(args.acta_tex))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(json.dumps({"status": "error", "code": CONFIG_INVALIDA,
                              "message": f"Regeneración desde JSON falló: {exc}"},
                             ensure_ascii=False))
            return CONFIG_INVALIDA
        if args.json:
            print(json.dumps({
                "status": "ok", "code": OK, "salida_json": str(args.salida_json),
                "acta_tex": args.acta_tex or None,
                "notas": {f"G{g['grupo']}": g["nota"].get("puntaje_sugerido")
                          for g in datos["grupos"]},
            }, ensure_ascii=False))
        return OK

    try:
        descriptor = cargar_descriptor(args.descriptor)
        grupos = validar_cobertura(descriptor)
        rubrica_texto, pesos = cargar_rubrica(str(RAIZ / descriptor["rubrica"]))
        if not pesos:
            raise ValueError("La rúbrica no declara pesos; la nota no sería reproducible")
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "error", "code": CONFIG_INVALIDA,
                          "message": str(exc)}, ensure_ascii=False))
        return CONFIG_INVALIDA

    base = Path(args.descriptor).resolve().parent
    api_key = os.getenv("GOOGLE_API_KEY") if not args.check else None
    try:
        resultado = evaluar(descriptor, rubrica_texto, pesos, grupos, base,
                            args.check, api_key)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        codigo = RED if "gh " in str(exc) or "Cuota" in str(exc) else CONFIG_INVALIDA
        print(json.dumps({"status": "error", "code": codigo,
                          "message": str(exc)}, ensure_ascii=False))
        return codigo

    destino_json = Path(args.salida_json)
    destino_json.parent.mkdir(parents=True, exist_ok=True)
    destino_json.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if args.acta_tex and not args.check:
        generar_acta_tex(resultado["grupos"], descriptor, Path(args.acta_tex))

    if args.json:
        print(json.dumps({
            "status": "ok", "code": OK, "salida_json": str(destino_json),
            "acta_tex": args.acta_tex or None,
            "notas": {f"G{g['grupo']}": g["nota"].get("puntaje_sugerido")
                      for g in resultado["grupos"]},
        }, ensure_ascii=False))
    return OK


if __name__ == "__main__":
    sys.exit(main())
