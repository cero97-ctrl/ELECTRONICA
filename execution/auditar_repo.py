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
import time
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


# Vocabulario cerrado del marcador de estado de una directiva. Ausencia de
# marcador equivale a 'activo', que es el default mas conservador: una directiva
# sin Status NO puede esconderse tras un hueco declarado.
ESTADO_ACTIVO = "activo"
ESTADO_PLANIFICADO = "planificado"
ESTADOS_DIRECTIVA = {ESTADO_ACTIVO, ESTADO_PLANIFICADO}


def _flags_de_script(raiz: Path, rel: str,
                     cache: dict[str, set[str] | None]) -> set[str] | None:
    """Flags que `<rel>.py` (ruta relativa a la raiz) acepta, o None si no se pudo saber.

    Se relanza con `--help` y se leen sus `usage:`. Es caro (arranca Python),
    asi que se cachea por ruta. Subproceso con timeout corto: un script colgado
    en la importacion no puede tumbar la auditoria.
    """
    if rel in cache:
        return cache[rel]

    ruta = raiz / rel
    if not ruta.is_file():
        cache[rel] = None
        return None

    try:
        proc = subprocess.run(
            [sys.executable, str(ruta), "--help"],
            capture_output=True, text=True, timeout=20,
            cwd=str(raiz),
        )
    except (OSError, subprocess.SubprocessError):
        cache[rel] = None
        return None

    texto = (proc.stdout or "") + (proc.stderr or "")
    if "usage:" not in texto.lower():
        # No es argparse (p. ej. un modulo sin CLI). No se afirma nada en vez
        # de inventar flags.
        cache[rel] = None
        return None

    cache[rel] = set(re.findall(r"(--[A-Za-z][A-Za-z0-9\-]*)", texto))
    return cache[rel]


def comprobar_directivas(raiz: Path) -> dict[str, Any]:
    """Directivas que invocan scripts de execution/ que no existen.

    Una directiva muerta no falla: simplemente nunca se ejecuto. Es la forma mas
    silenciosa de perder la arquitectura de 3 capas, porque el flujo sigue
    "funcionando" mientras su SOP ya no describe lo que hace.

    Un hueco DECLARADO no es una trampa. Si la directiva dice 'Status:
    planificado', el lector ya sabe que la capacidad no existe y la ausencia de
    los scripts es la consecuencia esperada, no una sorpresa. Por eso:

    - referencia rota en directiva 'activa'  -> fallo (trampa silenciosa)
    - referencia rota en directiva 'planificada' -> aviso, y se nombra
    - marcador 'planificado' cuyas referencias SI resuelven -> aviso (mentira
      en sentido contrario: el marcador esta obsoleto)

    Nunca 'ok' si queda alguna referencia rota, solo declarada o no: el hueco
    sigue visible en la evidencia y en la accion, solo baja de gravedad.
    """
    directivas = sorted((raiz / "directives").glob("*.yaml"))
    if not directivas:
        return _no_verificado("directivas", "no hay directorio directives/")

    rotas: list[dict[str, Any]] = []
    obsoletos: list[dict[str, Any]] = []
    marcadores_invalidos: list[dict[str, Any]] = []
    flags_fantasma: list[dict[str, Any]] = []
    total_refs = 0
    patron = re.compile(r"\bexecution/([A-Za-z0-9_.\-]+\.py)\b")
    patron_status = re.compile(r"^Status:\s*([A-Za-z_]+)\s*$", re.MULTILINE)
    # Flags declarados en la directiva: "- name: --algo" (p. ej. `--proteger A,B`).
    patron_flag = re.compile(r"^\s*-\s*name:\s*(--[A-Za-z][A-Za-z0-9\-]*)", re.MULTILINE)
    # El orquestador es quien posee la INTERFAZ del flujo (sus flags), no la capa 3.
    patron_orch = re.compile(r"^\s*orchestrator:\s*([A-Za-z0-9_.\-]+\.py)\s*$", re.MULTILINE)
    # Una dimension reutilizada declara `scripts:` en references: sus flags de
    # input las consume uno de esos scripts, no el compositor.
    patron_scripts = re.compile(r"^\s*scripts:\s*(.+)$", re.MULTILINE)
    # Cache de flags reales por ruta de script (arrancar Python es caro).
    _flags_cache: dict[str, set[str] | None] = {}

    for y in directivas:
        try:
            texto = y.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            rotas.append({
                "directiva": y.name, "script": "?",
                "motivo": f"ilegible: {exc}", "estado_directiva": ESTADO_ACTIVO,
            })
            continue

        m = patron_status.search(texto)
        estado_dir = m.group(1).strip().lower() if m else ESTADO_ACTIVO
        if estado_dir not in ESTADOS_DIRECTIVA:
            marcadores_invalidos.append({
                "directiva": y.name, "valor": estado_dir,
                "motivo": f"fuera del vocabulario {sorted(ESTADOS_DIRECTIVA)}",
            })
            estado_dir = ESTADO_ACTIVO

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
                    "estado_directiva": estado_dir,
                    "declarada": estado_dir == ESTADO_PLANIFICADO,
                })

        # Marcador obsoleto: dice 'no implementado' pero todo lo que referencia
        # existe. Miente en sentido contrario y hay que decirlo.
        if estado_dir == ESTADO_PLANIFICADO and vistas:
            faltan = [
                n for n in sorted(vistas)
                if not (raiz / "execution" / n).is_file()
            ]
            if not faltan:
                obsoletos.append({
                    "directiva": y.name,
                    "motivo": "Status: planificado pero sus "
                              f"{len(vistas)} referencia(s) existen",
                })

        # Flag fantasma: la directiva documenta `--x` que ni su orquestador ni
        # ninguno de sus scripts lo aceptan. Nadie lo detecta al leer: el flujo
        # solo falla cuando alguien teclea el comando. Se valida contra el
        # orquestador (posee la interfaz del flujo) y, si el orquestador es un
        # compositor, tambien contra los `scripts:` de references: (una
        # dimension reutilizada NO tiene CLI propia: sus flags los consume el
        # script que ejecuta). Nunca contra la capa 3 suelta.
        orch = patron_orch.search(texto)
        scripts_ref = patron_scripts.search(texto)
        if orch and (raiz / orch.group(1)).is_file():
            # El orquestador es la voz del flujo. Si no habla argparse, no puede
            # serializar sus flags y no se afirma nada: mirar los scripts de
            # capa 3 daria falsos positivos (sus flags internos no son la
            # interfaz del flujo).
            orch_flags = _flags_de_script(raiz, orch.group(1), _flags_cache)
            if orch_flags is not None:
                # Dimension reutilizada: el compositor no expone los flags de
                # input, los consume uno de los scripts de references/scripts.
                candidatos = [orch.group(1)]
                if scripts_ref:
                    candidatos += re.findall(
                        r"(execution/[A-Za-z0-9_.\-]+\.py)", scripts_ref.group(1))
                flags_reales = set(orch_flags)
                for rel in dict.fromkeys(candidatos[1:]):
                    extra = _flags_de_script(raiz, rel, _flags_cache)
                    if extra is not None:
                        flags_reales |= extra
                for flag in dict.fromkeys(patron_flag.findall(texto)):
                    if flag not in flags_reales:
                        flags_fantasma.append({
                            "directiva": y.name,
                            "flag": flag,
                            "orquestador": orch.group(1),
                            "motivo": f"documenta {flag} pero ni {orch.group(1)} "
                                      "ni sus scripts lo aceptan",
                            # El estado de la DIRECTIVA decide la gravedad: un
                            # flag fantasma en un 'planificado' es aviso (el
                            # hueco esta declarado); en uno activo, fallo.
                            "declarada": estado_dir == ESTADO_PLANIFICADO,
                            "estado_directiva": estado_dir,
                        })

    if total_refs == 0:
        return _no_verificado(
            "directivas",
            "ninguna directiva referencia execution/*.py: no se puede afirmar nada",
        )

    silenciosas = [r for r in rotas if not r.get("declarada")]
    declaradas = [r for r in rotas if r.get("declarada")]
    fantasma_fallos = [r for r in flags_fantasma if not r.get("declarada")]
    fantasma_avisos = [r for r in flags_fantasma if r.get("declarada")]
    if silenciosas or fantasma_fallos:
        estado = "fallo"
    elif declaradas or obsoletos or marcadores_invalidos or fantasma_avisos:
        estado = "aviso"
    else:
        estado = "ok"

    partes = []
    if silenciosas:
        partes.append(f"{len(silenciosas)} referencia(s) rota(s) SIN declarar")
    if fantasma_fallos:
        partes.append(
            f"{len(fantasma_fallos)} flag(s) documentado(s) que el orquestador no acepta"
        )
    if fantasma_avisos:
        partes.append(
            f"{len(fantasma_avisos)} flag(s) fantasma(s) en directiva(s) planificada(s)"
        )
    if declaradas:
        nombres = sorted({r['directiva'] for r in declaradas})
        partes.append(
            f"{len(declaradas)} referencia(s) declarada(s) no implementada(s) "
            f"en {len(nombres)} directiva(s) con Status: planificado"
        )
    if obsoletos:
        partes.append(f"{len(obsoletos)} marcador(es) obsoleto(s)")
    if marcadores_invalidos:
        partes.append(f"{len(marcadores_invalidos)} marcador(es) fuera de vocabulario")

    if partes:
        resumen = (
            f"{len(directivas)} directivas, {total_refs} referencias: "
            + "; ".join(partes)
        )
    else:
        resumen = (
            f"las {total_refs} referencias de {len(directivas)} directivas "
            "resuelven y ningun marcador esta obsoleto"
        )

    if silenciosas or fantasma_fallos:
        accion = ""
        if silenciosas:
            accion += (
                "Una directiva que apunta a un script inexistente SIN declarar que "
                "la capacidad no esta implementada es una trampa: no avisa, "
                "simplemente nunca se ejecuta. Corregir la referencia, marcar la "
                "directiva como 'Status: planificado' si es un roadmap, o retirarla. "
            )
        if fantasma_fallos:
            accion += (
                f"{len(fantasma_fallos)} flag(s) documentado(s) no lo acepta(n) su "
                "orquestador: una instruccion imposible de seguir, que solo falla "
                "cuando alguien teclea el comando. Corregir la directiva para que use "
                "el flag real (el codigo es la fuente de verdad)."
            )
        accion = accion.strip()
    elif declaradas or obsoletos or marcadores_invalidos or fantasma_avisos:
        capas = []
        if declaradas:
            capas.append(
                f"Hay {len(declaradas)} capacidad(es) declarada(s) no implementada(s) "
                f"en {len({r['directiva'] for r in declaradas})} directiva(s) "
                "(Status: planificado). No es un fallo: el hueco esta declarado y "
                "contado. Se implementan cuando hagan falta, no antes."
            )
        if obsoletos:
            capas.append(
                f"{len(obsoletos)} directiva(s) dicen 'planificado' pero todo lo que "
                "referencia existe: el marcador esta obsoleto y hay que quitarlo o "
                "implementar lo que prometen."
            )
        if marcadores_invalidos:
            capas.append(
                f"{len(marcadores_invalidos)} marcador(es) de Status fuera del "
                f"vocabulario {sorted(ESTADOS_DIRECTIVA)}."
            )
        if fantasma_avisos:
            capas.append(
                f"{len(fantasma_avisos)} flag(s) fantasma(s) en directiva(s) "
                "'Status: planificado': el nombre documentado no sera valido cuando "
                "se implemente, asi que hay que corregirlo ANTES de que exista el script."
            )
        accion = " ".join(capas)
    else:
        accion = (
            "Toda referencia execution/*.py de las directivas resuelve a un "
            "fichero real, ningun marcador de estado esta obsoleto y todo flag "
            "documentado existe en el orquestador que lo expone."
        )

    return {
        "dimension": "directivas",
        "estado": estado,
        "resumen": resumen,
        "evidencia": {
            "directivas_revisadas": len(directivas),
            "referencias_totales": total_refs,
            "referencias_rotas": len(rotas),
            "referencias_rotas_silenciosas": len(silenciosas),
            "referencias_declaradas_no_implementadas": len(declaradas),
            "marcadores_obsoletos": obsoletos,
            "marcadores_invalidos": marcadores_invalidos,
            "flags_fantasma": flags_fantasma,
            "rotas": rotas,
        },
        "accion": accion,
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


def _cronometrar(fn: Callable[[Path], dict[str, Any]]) -> Callable[[Path], dict[str, Any]]:
    """Anade la duracion de la comprobacion a su resultado.

    Se envuelve aqui y no en cada comprobar_* para que el dato lo tengan tanto
    la capa 3 en solitario como el orquestador, sin duplicar instrumentacion.
    Sin el, no hay forma de decidir si --rapido ahorra algo: solo se conocia el
    total, y el total no dice que parte es prescindible.
    """

    def envoltura(raiz: Path) -> dict[str, Any]:
        t0 = time.perf_counter()
        resultado = fn(raiz)
        resultado["duracion_s"] = round(time.perf_counter() - t0, 2)
        return resultado

    envoltura.__name__ = getattr(fn, "__name__", "comprobar")
    envoltura.__doc__ = fn.__doc__
    return envoltura


DIMENSIONES_NUEVAS: dict[str, Callable[[Path], dict[str, Any]]] = {
    nombre: _cronometrar(fn)
    for nombre, fn in {
        "secretos": comprobar_secretos,
        "logs": comprobar_logs_append_only,
        "directivas": comprobar_directivas,
        "capas": comprobar_capas,
        "peso_git": comprobar_peso_git,
        "untracked": comprobar_untracked,
        "pdf_stale": comprobar_pdf_stale,
    }.items()
}


class _Parser(argparse.ArgumentParser):
    """Codigo 3 para uso incorrecto, igual que en el orquestador.

    argparse usa 2 y en este flujo 2 significaria 'no verificado'. Un flag mal
    escrito no es una dimension que no se pudo comprobar, asi que se remapea.
    """

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(3)


def construir_parser() -> argparse.ArgumentParser:
    ap = _Parser(
        description="Comprobaciones estructurales del repo que ningun verificador cubre.",
    )
    ap.add_argument("--json", action="store_true", help="salida en JSON")
    ap.add_argument("--dimension", action="append", default=[],
                    choices=sorted(DIMENSIONES_NUEVAS),
                    help="restringir a estas dimensiones (repetible)")
    ap.add_argument("--raiz", default=str(PROJECT_ROOT), help="raiz del repo")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)

    raiz = Path(args.raiz).resolve()
    if not (raiz / "directives").is_dir():
        print(f"error: {raiz} no parece la raiz del repo (falta directives/)", file=sys.stderr)
        return 3

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
