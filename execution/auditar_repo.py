#!/usr/bin/env python3
"""Capa 3: comprobaciones estructurales del repo que NINGUN verificador cubre.

Este script no agrega nada: mide dimension por dimension y devuelve evidencia
contable. El veredicto global lo compone el orquestador
(`flujo_auditar_repo.py`) con la funcion pura `clasificar_salud`, porque decidir
que significa la conjunto es logica de orquestacion, no de medicion.

Por que existe: en el repo hay 13 verificadores independientes, cada uno con su
propio dialecto de exit code, y ninguno los consolida. Ademas hay defectos
reales que nadie mide (referencias muertas en directivas, peso historico de
git, secretos) y que se acumulan en silencio al crecer el proyecto.

Determinismo: mismos ficheros y mismo estado de git -> misma salida. Sin red,
sin LLM, sin coste, sin borrados. Solo lectura.

Uso:
    python3 execution/auditar_repo.py                    # informe legible
    python3 execution/auditar_repo.py --json             # JSON
    python3 execution/auditar_repo.py --dimension claves  # solo esas
Salida: 0 si ninguna dimension esta en fallo, 1 si alguna, 2 si uso incorrecto.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Umbrales. Son politica del repo, no medidas: se ajustan con evidencia
# registrada en la directiva, nunca "a ojo" en el chat.
# ---------------------------------------------------------------------------
MB = 1024 * 1024
PESO_AVISO_MB = 5.0          # a partir de aqui un fichero trackeado es ruido
PESO_FALLO_MB = 50.0         # GitHub AVISA a partir de 50 MB
PESO_BLOQUEO_MB = 100.0      # GitHub BLOQUEA el push a partir de 100 MB
UNTRACKED_AVISO = 20         # mas de esto suele ser deriva, no trabajo en curso
CARPETAS_NUNCA_TRACKEAR = ("node_modules", ".pio", "__pycache__", ".venv", "venv")

# Codigo de terceros vendorizado o artefactos de build. NO se escanean buscando
# secretos: no es codigo de este repo, no lo podemos arreglar, y escanearlo
# produce falsos positivos que entrenan a ignorar la alerta. Medido: el escaneo
# de node_modules marco una clave PEM de plantilla de miniflare como secreto.
RUTAS_VENDIDAS = (
    "node_modules", ".pio", "vendor", "third_party", ".git", ".tmp",
    "chroma_db", "__pycache__", ".venv", "venv", ".tox", "site-packages",
)

# Extensiones que se inspeccionan buscando secretos. Se excluyen a proposito
# los binarios: un matcher de patrones sobre un .pdf solo produce ruido.
EXTENSIONES_TEXTO = {
    ".py", ".md", ".txt", ".yaml", ".yml", ".json", ".toml", ".cfg", ".ini",
    ".env", ".sh", ".bash", ".tex", ".js", ".ts", ".html", ".sql", ".csv",
}

# Ficheros cuyo contenido es SECRETOS POR DISENO (los .env locales, gitignored).
# No se escanean nunca, ni tracked ni untracked, para no imprimirlos.
NUNCA_ESCANEAR_SECRETOS = {".env", ".groq_api_key", "secrets.json", "credentials.json"}

# ---------------------------------------------------------------------------
# Deteccion de secretos. De ALTA PRECISION a proposito.
#
# Un detector de secretos que marca la prosa sana es peor que no tener ninguno:
# entrena a ignorar sus propias alertas. Cada patron anadido tiene que medirse
# contra el repo real antes de quedarse (ver `medir_preciston_secretos`).
# Se priorizan los formatos con prefijo de proveedor, que casi no colisionan.
# ---------------------------------------------------------------------------
PATRONES_SECRETO: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("openrouter", re.compile(r"sk-or-v1-[A-Za-z0-9]{32,}"), "API key de OpenRouter"),
    ("openai", re.compile(r"\bsk-(?!or-v1)[A-Za-z0-9]{32,}\b"), "API key estilo OpenAI"),
    ("github_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{50,}"), "fine-grained PAT de GitHub"),
    ("github_classic", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}"), "token clasico de GitHub"),
    ("aws", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "access key de AWS"),
    ("google", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), "API key de Google"),
    ("huggingface", re.compile(r"\bhf_[A-Za-z0-9]{34,}\b"), "token de HuggingFace"),
    ("slack", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"), "token de Slack"),
    ("telegram", re.compile(r"\b\d{9,11}:[A-Za-z0-9_-]{35}\b"), "token de bot de Telegram"),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
     "clave privada PEM"),
)

# Asignacion generica: solo con valor de alta entropia y comillas, para no
# marcar prosa como "token = el_fin_del_semestre".
PATRON_ASIGNACION = re.compile(
    r"""(?ix)
    \b (?: api[_-]?key | secret | token | password | passwd | clave )
    \s* [:=] \s*
    ['"] (?P<valor> [A-Za-z0-9+/_\-]{24,} ) ['"]
    """
)


def entropia_shannon(texto: str) -> float:
    """Bits por caracter. Una clave real ronda 4.5-6.0; una palabraenglish ~3.0."""
    if not texto:
        return 0.0
    counts: dict[str, int] = {}
    for ch in texto:
        counts[ch] = counts.get(ch, 0) + 1
    total = len(texto)
    ent = 0.0
    for n in counts.values():
        prob = n / total
        ent -= prob * math.log2(prob)
    return ent


# ---------------------------------------------------------------------------
# Dimensiones nuevas
# ---------------------------------------------------------------------------

def comprobar_secretos(raiz: Path) -> dict[str, Any]:
    """Secretos en ficheros que git PUEDE publicar.

    Solo se inspeccionan ficheros trackeados o no ignorados: un `.env` local no
    se escanea nunca (esta en NUNCA_ESCANEAR_SECRETOS) y no se imprime su
    contenido bajo ningun supuesto.
    """
    try:
        tr = subprocess.run(["git", "ls-files", "-z", "--cached"],
                            cwd=raiz, capture_output=True, text=True, timeout=120)
        un = subprocess.run(["git", "ls-files", "-z", "--others", "--exclude-standard"],
                            cwd=raiz, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        return _no_verificado("secretos", f"no se pudo listar ficheros de git: {exc}")

    trackeados = {r for r in tr.stdout.split("\0") if r}
    no_trackeados = {r for r in un.stdout.split("\0") if r} - trackeados
    candidatos = sorted(trackeados | no_trackeados)
    rutas = [r for r in candidatos if not _es_vendida(r)]
    descartados_vendidas = len(candidatos) - len(rutas)

    inspeccionados = 0
    hallazgos: list[dict[str, str]] = []
    saltados_por_tamano = 0

    for rel in rutas:
        p = raiz / rel
        if p.name in NUNCA_ESCANEAR_SECRETOS or p.suffix in NUNCA_ESCANEAR_SECRETOS:
            continue
        if p.suffix.lower() not in EXTENSIONES_TEXTO and p.suffix != "":
            continue
        if ".env" in p.name:            # .env.local, .env.production, ...
            continue
        try:
            if p.stat().st_size > 2 * MB:
                saltados_por_tamano += 1
                continue
            texto = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        inspeccionados += 1
        for linea_n, linea in enumerate(texto.splitlines(), 1):
            for nombre, patron, desc in PATRONES_SECRETO:
                m = patron.search(linea)
                if m:
                    hallazgos.append({
                        "fichero": rel, "linea": str(linea_n), "tipo": nombre,
                        "descripcion": desc,
                        "trackeado": rel in trackeados,
                        "evidencia": _ofuscar(m.group(0)),
                    })
                    break
            else:
                m = PATRON_ASIGNACION.search(linea)
                if m and entropia_shannon(m.group("valor")) >= 4.0:
                    hallazgos.append({
                        "fichero": rel, "linea": str(linea_n), "tipo": "asignacion",
                        "descripcion": "asignacion de secreto con valor de alta entropia",
                        "trackeado": rel in trackeados,
                        "evidencia": _ofuscar(m.group("valor")),
                    })

    publicados = [h for h in hallazgos if h["trackeado"]]
    latentes = [h for h in hallazgos if not h["trackeado"]]
    if publicados:
        estado = "fallo"
    elif latentes:
        estado = "aviso"
    else:
        estado = "ok"
    if not inspeccionados:
        return _no_verificado(
            "secretos",
            f"ningun fichero de texto inspeccionable (de {len(rutas)} candidatos); "
            "un 0 aqui no es evidencia de nada",
            extra={"candidatos": len(rutas)},
        )
    return {
        "dimension": "secretos",
        "estado": estado,
        "resumen": (
            f"{len(publicados)} secreto(s) en ficheros YA TRACKEADOS, "
            f"{len(latentes)} latente(s) sin trackear, en {inspeccionados} ficheros"
            if hallazgos else
            f"sin secretos en {inspeccionados} ficheros inspeccionados"
        ),
        "evidencia": {
            "ficheros_inspeccionados": inspeccionados,
            "candidatos_considerados": len(candidatos),
            "descartados_por_codigo_vendizado": descartados_vendidas,
            "saltados_por_tamano": saltados_por_tamano,
            "excluidos_por_diseno": sorted(NUNCA_ESCANEAR_SECRETOS),
            "rutas_vendidas_excluidas": list(RUTAS_VENDIDAS),
            "secretos_publicados": publicados,
            "secretos_latentes": latentes,
        },
        "accion": (
            "Un secreto en fichero trackeado esta PUBLICADO: revocar y rotar la "
            "credencial primero, despues sacarlo. Borrar el fichero NO basta, "
            "sigue en el historico de git."
            if publicados else
            "No hay secretos publicados. Los latentes se filtrarian con un 'git add .'."
            if latentes else
            "Nada que hacer. Cobertura: ficheros de texto propios del repo, trackeados "
            "y no ignorados. El codigo de terceros vendorizado queda fuera a proposito."
        ),
    }


def comprobar_directivas(raiz: Path) -> dict[str, Any]:
    """Directivas que invocan scripts de execution/ que no existen.

    Una directiva muerta no falla: simplemente nunca se ejecuto. Es la forma mas
    silenciosa de perder la arquitectura de 3 capas, porque el flujo sigue
    "funcionando" mientras su SOP ya no describe lo que hace.
    """
    directivas = sorted((raiz / "directives").glob("*.yaml"))
    if not directivas:
        return _no_verificado("directivas", "no hay directorio directives/")

    rotas: list[dict[str, Any]] = []
    total_refs = 0
    patron = re.compile(r"\bexecution/([A-Za-z0-9_.\-]+\.py)\b")

    for y in directivas:
        try:
            texto = y.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            rotas.append({"directiva": y.name, "script": "?", "motivo": f"ilegible: {exc}"})
            continue
        vistas: set[str] = set()
        for m in patron.finditer(texto):
            nombre = m.group(1)
            vistas.add(nombre)
            total_refs += 1
            if not (raiz / "execution" / nombre).is_file():
                rotas.append({
                    "directiva": y.name,
                    "script": nombre,
                    "motivo": "execution/ no existe",
                })

    estado = "fallo" if rotas else "ok"
    if total_refs == 0:
        return _no_verificado(
            "directivas",
            "ninguna directiva referencia execution/*.py: no se puede afirmar nada",
        )
    return {
        "dimension": "directivas",
        "estado": estado,
        "resumen": (
            f"{len(rotas)} referencia(s) a scripts inexistentes en {len(directivas)} directivas"
            if rotas else
            f"las {total_refs} referencias de {len(directivas)} directivas resuelven"
        ),
        "evidencia": {
            "directivas_revisadas": len(directivas),
            "referencias_totales": total_refs,
            "referencias_rotas": len(rotas),
            "rotas": rotas,
        },
        "accion": (
            "Una directiva que apunta a un script inexistente es una directiva "
            "muerta: no avisa, simplemente nunca se ejecuta. Corregir la "
            "referencia o retirar la directiva."
            if rotas else
            "Toda referencia execution/*.py de las directivas resuelve a un fichero real."
        ),
    }


# Procesos de servicio permanentes. No son orquestadores por lotes: no terminan,
# asi que no tienen un "script de ejecucion" al que delegar una tarea discreta.
# Exentos de la comprobacion de capa 3 por diseno, no por Convenience.
FLUJOS_DAEMON: dict[str, str] = {
    "flujo_ruview_rescue.py": "listener UDP :5005, servicio permanente",
    "flujo_telegram.py": "gateway de polling de Telegram, servicio permanente",
}


def comprobar_capas(raiz: Path) -> dict[str, Any]:
    """Cobertura de la capa 3 (el flujo delega en execution/) por flujo.

    La pregunta es de EXISTENCIA, no de forma: se busca cualquier basename .py
    que el flujo nombre y que exista de verdad en execution/. No se busca el
    literal "execution/x.py" porque los orquestadores reales construyen la ruta
    con Path (`SCRIPT_DIR / "execution" / "disco_medir.py"`); un matcher de
    texto dio 13 falsos positivos sobre 20 flujos.

    La capa 1 (directiva) NO se verifica aqui, y no por pereza: el mapeo
    flujo -> directiva no es 1:1 (flujo_disco.py -> mantenimiento_disco.yaml) y
    solo 4 de 20 directivas declaran la clave `orchestrator:`. Cualquier
    afirmacion sobre la capa 1 seria inventada, y afirmar lo que no se ha
    comprobado es el error que este mismo flujo existe para evitar. Se reporta
    como contexto, fuera del veredicto, y queda como decision pendiente.
    """
    flujos = sorted(p for p in raiz.glob("flujo_*.py") if p.is_file())
    if not flujos:
        return _no_verificado("capas", "no hay flujos en la raiz")

    existentes = {q.name for q in (raiz / "execution").glob("*.py")}
    nombres_directivas = [d.name for d in (raiz / "directives").glob("*.yaml")]

    sin_capa3: list[dict[str, Any]] = []
    ilegibles: list[str] = []
    con_capa3: list[str] = []
    daemons = []

    for f in flujos:
        if f.name in FLUJOS_DAEMON:
            daemons.append({"flujo": f.name, "motivo": FLUJOS_DAEMON[f.name]})
            continue
        try:
            fuente = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            ilegibles.append(f.name)
            continue
        nombrados = set(re.findall(r"\b([A-Za-z0-9_]+\.py)\b", fuente))
        delega = sorted(nombrados & existentes)
        if delega:
            con_capa3.append(f.name)
        else:
            sin_capa3.append({
                "flujo": f.name,
                "motivo": "no nombra ningun .py que exista en execution/",
            })

    if ilegibles:
        estado = "no_verificado"
    elif sin_capa3:
        estado = "fallo"
    else:
        estado = "ok"

    return {
        "dimension": "capas",
        "estado": estado,
        "resumen": (
            f"{len(con_capa3)}/{len(flujos) - len(daemons)} flujos de proceso delegan en "
            f"execution/; {len(sin_capa3)} sin capa 3; {len(daemons)} daemons exentos; "
            f"capa 1 no verificable (informativo)"
        ),
        "evidencia": {
            "flujos_totales": len(flujos),
            "flujos_auditados_capa3": len(flujos) - len(daemons),
            "con_capa_3": con_capa3,
            "sin_capa_3": sin_capa3,
            "daemons_exentos": daemons,
            "ilegibles": ilegibles,
            "capa_1_no_verificada": {
                "motivo": (
                    "el mapeo flujo->directiva no es 1:1 y solo 4 de "
                    f"{len(nombres_directivas)} directivas declaran 'orchestrator:'. "
                    "Sin una tabla canonica no hay forma honesta de derivarlo."
                ),
                "directivas_existentes": len(nombres_directivas),
                "flujos_con_directiva_de_nombre_evidente": sum(
                    1 for f in flujos
                    if any(f.stem in d or f.stem.replace("flujo_", "") in d
                           for d in nombres_directivas)
                ),
            },
        },
        "accion": (
            "Un flujo que no nombra ningun script de execution/ tiene la logica de negocio "
            "en la capa de orquestacion, que es lo que AGENTS.md prohibe. Extraer a "
            "execution/ y dejar el flujo como pura coordinacion."
            if sin_capa3 else
            "Todo flujo de proceso delega su trabajo en execution/."
        ),
    }


def comprobar_peso_git(raiz: Path) -> dict[str, Any]:
    """Peso historico de git: lo que ya no se puede deshacer con un rm.

    Un repo puede estar limpio en el working tree y seguir con 800 MB de
    node_modules en el historial. Eso no se arregla borrando ficheros: exige
    reescribir historia, y mientras tanto, un fichero sobre 100 MB bloquea
    todos los pushes.
    """
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-z"], cwd=raiz,
            capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return _no_verificado("peso_git", f"no se pudo ejecutar git ls-files: {exc}")
    if proc.returncode != 0:
        return _no_verificado("peso_git", f"git ls-files devolvio {proc.returncode}")

    rutas = [r for r in proc.stdout.split("\0") if r]
    if not rutas:
        return _no_verificado("peso_git", "git no devolvio ficheros trackeados")

    grandes: list[dict[str, Any]] = []
    carpetas_mal: dict[str, int] = {}
    total = 0

    for rel in rutas:
        try:
            b = (raiz / rel).stat().st_size
        except OSError:
            continue
        total += b
        if b >= PESO_AVISO_MB * MB:
            grandes.append({"fichero": rel, "mb": round(b / MB, 1)})
        partes = rel.split("/")
        for i, p in enumerate(partes[:-1]):
            if p in CARPETAS_NUNCA_TRACKEAR:
                raiz_carpeta = "/".join(partes[: i + 1])
                carpetas_mal[raiz_carpeta] = carpetas_mal.get(raiz_carpeta, 0) + b
                break

    grandes.sort(key=lambda d: -d["mb"])
    # `bloquea_push` es un umbral duro de GitHub, no una opinion.
    bloquean = [g for g in grandes if g["mb"] >= PESO_BLOQUEO_MB]

    if bloquean:
        estado = "fallo"
    elif carpetas_mal or grandes:
        estado = "aviso"
    else:
        estado = "ok"

    return {
        "dimension": "peso_git",
        "estado": estado,
        "resumen": (
            f"{total / MB:.0f} MB trackeados; {len(grandes)} fichero(s) >= {PESO_AVISO_MB:.0f} MB; "
            f"{len(carpetas_mal)} carpeta(s) que nunca deberian trackearse"
        ),
        "evidencia": {
            "ficheros_trackeados": len(rutas),
            "total_mb": round(total / MB, 1),
            "ficheros_sobre_50mb": grandes,
            "ficheros_sobre_100mb_bloquean_push": bloquean,
            "carpetas_que_no_deben_trackearse": {
                k: round(v / MB, 1) for k, v in sorted(carpetas_mal.items())
            },
            "umbrales_mb": {
                "aviso": PESO_AVISO_MB, "fallo": PESO_FALLO_MB, "bloqueo_push": PESO_BLOQUEO_MB,
            },
        },
        "accion": (
            "Sacarlos del indice con 'git rm -r --cached' + regla .gitignore. El peso ya "
            "esta en .git: dejar de trackearlos AHORRA espacio futuro pero NO reduce el "
            "historico. Reducir el historico exige reescribirlo (filter-repo/filter-branch), "
            "que es una operacion con consecuencias y hay que decidir con cuidado."
            if estado != "ok" else
            "Ningun fichero trackeado pasa los umbrales."
        ),
    }


def comprobar_untracked(raiz: Path) -> dict[str, Any]:
    """Deriva de ficheros sin trackear. Aviso, nunca fallo.

    Un untracked no es un defecto: puede ser trabajo en curso legitimo. Solo se
    señala la magnitud, porque un numero alto sostenido significa que el
    working tree ya no es representativo del proyecto.
    """
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-o", "--exclude-standard", "-z"],
            cwd=raiz, capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return _no_verificado("untracked", f"no se pudo ejecutar git ls-files: {exc}")

    rutas = [r for r in proc.stdout.split("\0") if r]
    estado = "aviso" if len(rutas) > UNTRACKED_AVISO else "ok"
    return {
        "dimension": "untracked",
        "estado": estado,
        "resumen": f"{len(rutas)} fichero(s) sin trackear (umbral de aviso: {UNTRACKED_AVISO})",
        "evidencia": {
            "ficheros_untracked": len(rutas),
            "umbral_aviso": UNTRACKED_AVISO,
            "muestra": rutas[:25],
            "nota": "muestra truncada a 25; no se puede commitear en bloque a ciegas",
        },
        "accion": (
            "Revisar uno a uno. Un 'git add .' aqui se llevaria trabajo de otras sesiones."
            if estado == "aviso" else
            "Dentro de lo razonable."
        ),
    }


def comprobar_logs_append_only(raiz: Path) -> dict[str, Any]:
    """Cadena de hashes de cada .tmp/session_log_*.jsonl.

    El log append-only es la fuente de verdad del proyecto: si alguien edita o
    borra una linea, la cadena se rompe. Se verifica TODOS los logs presentes,
    no solo el de la ultima corrida, porque un log antiguo tambien es evidencia.

    Sin logs no se afirma nada: `no_verificado`, nunca `ok`.
    """
    tmp = raiz / ".tmp"
    sesion_log = raiz / "execution" / "sesion_log.py"
    if not sesion_log.is_file():
        return _no_verificado("no encuentro execution/sesion_log.py", "logs")

    logs = sorted(p.name[len("session_log_"):-len(".jsonl")]
                  for p in tmp.glob("session_log_*.jsonl"))
    if not logs:
        return _no_verificado("no hay ningun log append-only en .tmp/", "logs")

    rotos: list[dict[str, Any]] = []
    ilegibles: list[str] = []
    total_eventos = 0
    for run_id in logs:
        try:
            proc = subprocess.run(
                [sys.executable, str(sesion_log), "integrity", "--run", run_id],
                capture_output=True, text=True, timeout=60, cwd=raiz,
            )
            datos = json.loads(proc.stdout) if proc.stdout.strip() else {}
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
            ilegibles.append(run_id)
            continue
        if datos.get("ok") is True:
            total_eventos += int(datos.get("eventos") or 0)
        else:
            rotos.append({"run_id": run_id, "salida": datos})

    if ilegibles:
        return _no_verificado(
            f"{len(ilegibles)} log(s) no se pudieron verificar (timeout o salida ilegible)", "logs")

    if rotos:
        return {
            "dimension": "logs",
            "estado": "fallo",
            "resumen": f"cadena de hashes rota en {len(rotos)} de {len(logs)} log(s)",
            "accion": (
                "Un log append-only editado o truncado rompe la cadena de hashes y "
                "anula la trazabilidad de esa corrida. No se corrige a mano: la "
                "evidencia esta comprometida y hay que decidir si se acepta la "
                "corrida como no fiable o se restaura desde otra copia."
            ),
            "evidencia": {"logs": len(logs), "rotos": rotos},
        }

    return {
        "dimension": "logs",
        "estado": "ok",
        "resumen": f"cadena de hashes intacta en {len(logs)} log(s), {total_eventos} evento(s)",
        "evidencia": {"logs": len(logs), "eventos": total_eventos, "rotos": []},
    }


def comprobar_pdf_stale(raiz: Path) -> dict[str, Any]:
    """PDF cuyo .tex es mas reciente: el entregable esta desactualizado.

    Es la deriva mas comun de un repo con LaTeX: se corrige el fuente, se
    regenera un lado, y el PDF que se entrega sigue siendo el viejo.
    """
    desfasados: list[dict[str, Any]] = []
    revisados = 0
    for tex in raiz.rglob("*.tex"):
        if ".tmp" in tex.parts or ".git" in tex.parts:
            continue
        pdf = tex.with_suffix(".pdf")
        if not pdf.is_file():
            continue
        revisados += 1
        try:
            dt_tex = tex.stat().st_mtime
            dt_pdf = pdf.stat().st_mtime
        except OSError:
            continue
        if dt_tex > dt_pdf + 1.0:
            desfasados.append({
                "tex": str(tex.relative_to(raiz)),
                "retraso_s": int(dt_tex - dt_pdf),
            })

    desfasados.sort(key=lambda d: -d["retraso_s"])
    if not revisados:
        return _no_verificado("pdf_stale", "ningun par .tex/.pdf comparable")
    estado = "aviso" if desfasados else "ok"
    return {
        "dimension": "pdf_stale",
        "estado": estado,
        "resumen": (
            f"{len(desfasados)} de {revisados} par(es) .tex/.pdf con el fuente mas nuevo"
            if desfasados else
            f"los {revisados} pares .tex/.pdf estan al dia"
        ),
        "evidencia": {
            "pares_revisados": revisados,
            "desfasados": desfasados[:25],
            "nota": f"muestra truncada a 25 de {len(desfasados)}",
        },
        "accion": (
            "Recompilar antes de entregar. El PDF es lo que lee el usuario final; "
            "un .tex bonito con un PDF viejo no comunica nada."
            if desfasados else
            "Todos los PDF reflejan su fuente."
        ),
    }


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _es_vendida(rel: str) -> bool:
    """True si la ruta cae en codigo de terceros o artefactos de build."""
    partes = set(Path(rel).parts)
    return bool(partes & set(RUTAS_VENDIDAS))


def _no_verificado(dimension: str, motivo: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    ev = {"motivo": motivo}
    if extra:
        ev.update(extra)
    return {
        "dimension": dimension,
        "estado": "no_verificado",
        "resumen": f"NO SE PUDO COMPROBAR: {motivo}",
        "evidencia": ev,
        "accion": "No tomes este 'OK' como evidencia. Arregla la comprobacion y vuelve a medir.",
    }


def _ofuscar(secreto: str) -> str:
    """Muestra solo lo necesario para identificarlo sin propagarlo."""
    s = secreto.strip()
    if len(s) <= 12:
        return f"{s[:4]}***"
    return f"{s[:6]}***{s[-2:]}({len(s)} chars)"


DIMENSIONES_NUEVAS: dict[str, Callable[[Path], dict[str, Any]]] = {
    "secretos": comprobar_secretos,
    "logs": comprobar_logs_append_only,
    "directivas": comprobar_directivas,
    "capas": comprobar_capas,
    "peso_git": comprobar_peso_git,
    "untracked": comprobar_untracked,
    "pdf_stale": comprobar_pdf_stale,
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Comprobaciones estructurales del repo que ningun verificador cubre.",
    )
    ap.add_argument("--json", action="store_true", help="salida en JSON")
    ap.add_argument("--dimension", action="append", default=[],
                    choices=sorted(DIMENSIONES_NUEVAS),
                    help="restringir a estas dimensiones (repetible)")
    ap.add_argument("--raiz", default=str(PROJECT_ROOT), help="raiz del repo")
    args = ap.parse_args(argv)

    raiz = Path(args.raiz).resolve()
    if not (raiz / "directives").is_dir():
        print(f"error: {raiz} no parece la raiz del repo (falta directives/)", file=sys.stderr)
        return 2

    elegidas = args.dimension or list(DIMENSIONES_NUEVAS)
    informe = {"dimensiones": [DIMENSIONES_NUEVAS[n](raiz) for n in elegidas]}

    if args.json:
        print(json.dumps(informe, ensure_ascii=False, indent=2))
    else:
        print("== Comprobaciones estructurales del repo ==")
        for d in informe["dimensiones"]:
            marca = {"ok": "ok    ", "aviso": "AVISO ", "fallo": "FALLO ",
                     "no_verificado": "SIN VERIF"}[d["estado"]]
            print(f"  [{marca}] {d['dimension']}: {d['resumen']}")
            if d["estado"] in ("fallo", "aviso", "no_verificado"):
                print(f"            -> {d['accion']}")

    return 1 if any(d["estado"] == "fallo" for d in informe["dimensiones"]) else 0


if __name__ == "__main__":
    sys.exit(main())
