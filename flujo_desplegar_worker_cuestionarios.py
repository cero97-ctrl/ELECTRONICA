#!/usr/bin/env python3
"""Capa 2: despliega el Worker que recibe, califica y archiva las entregas.

Orquesta tres cosas que no decide por sí mismo:
  - la clave sale de `<fuente>_respuestas.md` con el parser de
    `execution/md_a_html.py` (una sola definición de «qué es una clave válida»);
  - el despliegue y los secretos los hace `wrangler` en
    `Proyectos/cuestionarios-worker`;
  - el archivado en el repo privado lo hace el Worker con `GITHUB_TOKEN`.

La clave NUNCA se pasa como argumento de shell: se escribe en `.tmp/` con
permisos 600 y se envía por stdin a `wrangler secret put`.

Uso:
    python3 flujo_desplegar_worker_cuestionarios.py --check
    python3 flujo_desplegar_worker_cuestionarios.py
    python3 flujo_desplegar_worker_cuestionarios.py --actualizar-fuente --json

Códigos de salida: 0 ok · 1 error de E/S · 3 fuente o clave inválida ·
4 wrangler no autenticado, falló el despliegue o falta un secreto ·
5 el Worker desplegado no responde en `/salud`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
EJECUCION = RAIZ / "execution"
PYTHON = sys.executable
SESION_LOG = EJECUCION / "sesion_log.py"
ALERTAR = EJECUCION / "alert_user.py"
WORKER_DIR = RAIZ / "Proyectos" / "cuestionarios-worker"
FUENTE = RAIZ / "cursos/CYBERSEGURIDAD/evaluaciones/web/fuentes/ROL_ROJO_Cuestionario.md"
WRANGLER_HERMANO = RAIZ / "Proyectos/cloudflare-agent/node_modules/.bin/wrangler"
URL_WORKER = re.compile(r"https://[a-z0-9-]+\.[a-z0-9-]+\.workers\.dev")
# Cloudflare responde 403 (error code 1010) al User-Agent por defecto de urllib,
# así que las peticiones del flujo fingen un navegador (mismo criterio que
# execution/scrape_single_site.py, ver .agent/python.md #18).
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

sys.path.insert(0, str(EJECUCION))
import descargar_resultados  # noqa: E402  (capa 3: lector único del JSONC del Worker)
import md_a_html  # noqa: E402  (capa 3: parser y validación de la fuente)
import run_state  # noqa: E402  (capa 3: vista por corrida)


def _trazar(run_id: str, tipo: str, datos: dict) -> bool:
    try:
        proc = subprocess.run(
            [PYTHON, str(SESION_LOG), "add", "--run", run_id, "--tipo", tipo,
             "--datos", json.dumps(datos, ensure_ascii=False)],
            cwd=RAIZ, capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def _wrangler(explicito: str | None) -> str:
    if explicito:
        return explicito
    if WRANGLER_HERMANO.exists():
        return str(WRANGLER_HERMANO)
    encontrado = shutil.which("wrangler")
    if encontrado:
        return encontrado
    raise FileNotFoundError(
        "no se encontró wrangler: pasar --wrangler o instalarlo en el proyecto"
    )


def _leer_clave(fuente: Path, respuestas: Path) -> tuple[dict[str, str], int]:
    datos = md_a_html.cargar_clave(fuente, respuestas)
    clave = datos["clave"]
    ordenada = {str(n): clave[n] for n in sorted(clave)}
    return ordenada, datos["n_preguntas"]


def _escribir_clave(clave: dict[str, str], cuestionario: str) -> Path:
    destino = RAIZ / ".tmp" / f"clave_{cuestionario}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(clave, ensure_ascii=False, indent=2) + "\n"
    destino.write_text(texto, encoding="utf-8")
    os.chmod(destino, 0o600)
    return destino


def _entorno() -> dict[str, str]:
    """Entorno para wrangler: hereda el del shell y completa desde `.env`."""
    entorno = dict(os.environ)
    ruta = RAIZ / ".env"
    if not ruta.exists():
        return entorno
    for linea in ruta.read_text(encoding="utf-8", errors="ignore").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        nombre, _, valor = linea.partition("=")
        nombre = nombre.strip()
        valor = valor.strip().strip('"').strip("'")
        if nombre and nombre not in entorno:
            entorno[nombre] = valor
    return entorno


def _token_resultados() -> str | None:
    valor = _entorno().get("GITHUB_TOKEN_RESULTADOS", "").strip()
    return valor or None


def _ejecutar(
    cmd: list[str],
    cwd: Path,
    entrada: str | None = None,
    timeout: int = 300,
):
    return subprocess.run(
        cmd, cwd=cwd, input=entrada, capture_output=True, text=True,
        timeout=timeout, env=_entorno(),
    )


def _desplegar(wrangler: str, cwd: Path, entorno: str | None = None) -> tuple[str | None, str]:
    cmd = [wrangler, "deploy"] + (["--env", entorno] if entorno else [])
    proc = _ejecutar(cmd, cwd, timeout=600)
    salida = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        return None, salida
    urls = URL_WORKER.findall(salida)
    return (urls[-1] if urls else None), salida


def _secretos(wrangler: str, cwd: Path, entorno: str | None = None) -> dict[str, bool]:
    cmd = [wrangler, "secret", "list", "--format", "json"]
    if entorno:
        cmd += ["--env", entorno]
    proc = _ejecutar(cmd, cwd)
    nombres: set[str] = set()
    if proc.returncode == 0:
        try:
            for item in json.loads(proc.stdout or "[]"):
                if isinstance(item, dict) and item.get("name"):
                    nombres.add(str(item["name"]))
        except json.JSONDecodeError:
            pass
    if not nombres:
        nombres = set(re.findall(r'"name"\s*:\s*"([A-Z_]+)"', proc.stdout or ""))
    return {"CLAVE_JSON": "CLAVE_JSON" in nombres, "GITHUB_TOKEN": "GITHUB_TOKEN" in nombres}


def _config_entorno(worker_dir: Path, entorno: str | None) -> tuple[str, dict]:
    """Nombre y `vars` efectivos que wrangler usará para ese entorno.

    En wrangler los `vars` de `env.<x>` NO se heredan del nivel superior, y un
    `CUESTIONARIO_ID` desalineado con la fuente es la peor avería posible:
    `wrangler secret put` escribiría la clave de este cuestionario en el Worker
    de otro y el suyo quedaría rechazando entregas. Por eso se lee el archivo y
    se compara antes de tocar la cuenta.
    """
    ruta = worker_dir / "wrangler.jsonc"
    try:
        crudo = ruta.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"no se pudo leer {ruta}: {exc}") from exc
    try:
        # Una sola implementación del JSONC del repo: la del acta, que respeta
        # `//` dentro de cadenas (las URLs de ORIGENES).
        config = json.loads(descargar_resultados._quitar_comentarios(crudo))
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"wrangler.jsonc inválido: {exc}") from exc
    if not isinstance(config, dict):
        raise ValueError("wrangler.jsonc no es un objeto")

    if entorno is None:
        nombre = str(config.get("name") or "")
        return nombre, dict(config.get("vars") or {})

    entornos = config.get("env") or {}
    if entorno not in entornos:
        raise ValueError(
            f"wrangler.jsonc no declara env.{entorno}: añadir el entorno (name + "
            "vars con su CUESTIONARIO_ID) antes de desplegar"
        )
    bloque = entornos[entorno] or {}
    nombre = str(bloque.get("name") or f"{config.get('name')}-{entorno}")
    return nombre, dict(bloque.get("vars") or {})


def _salud(url: str) -> tuple[bool, str]:
    peticion = urllib.request.Request(
        url.rstrip("/") + "/salud",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(peticion, timeout=15) as res:
            datos = json.loads(res.read().decode("utf-8"))
            return res.status == 200 and datos.get("ok") is True, ""
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}: {exc.reason}"
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return False, str(exc)


def _fijar_entrega_url(fuente: Path, url: str) -> str:
    texto = fuente.read_text(encoding="utf-8")
    if not texto.startswith("---"):
        raise ValueError("la fuente no tiene front matter")
    fin = texto.find("\n---", 3)
    if fin == -1:
        raise ValueError("el front matter no cierra con ---")
    cabecera, resto = texto[:fin], texto[fin:]
    if re.search(r"(?m)^entrega_url:", cabecera):
        cabecera = re.sub(r"(?m)^entrega_url:.*$", f"entrega_url: {url}", cabecera)
    else:
        cabecera = cabecera.rstrip("\n") + f"\nentrega_url: {url}"
    fuente.write_text(cabecera + resto, encoding="utf-8")
    return f"{cabecera.count(chr(10))} líneas de cabecera"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Despliega el Worker de entregas y fija su URL en la fuente."
    )
    parser.add_argument("--fuente", default=str(FUENTE), help="Cuestionario .md.")
    parser.add_argument("--respuestas", default=None, help="Archivo de respuestas.")
    parser.add_argument("--worker-dir", default=str(WORKER_DIR), help="Proyecto del Worker.")
    parser.add_argument("--wrangler", default=None, help="Binario de wrangler.")
    parser.add_argument(
        "--env",
        default=None,
        help="Entorno de wrangler (`env.<nombre>`); sin él, el Worker base (ROL ROJO).",
    )
    parser.add_argument("--check", action="store_true", help="Valida sin desplegar (sin cuenta).")
    parser.add_argument("--actualizar-fuente", action="store_true", help="Escribe entrega_url en el .md.")
    parser.add_argument("--json", action="store_true", help="Salida JSON.")
    parser.add_argument("--no-alert", action="store_true", help="Sin alerta audible.")
    args = parser.parse_args()

    worker_dir = Path(args.worker_dir).resolve()
    fuente = Path(args.fuente).resolve()
    respuestas = (
        Path(args.respuestas).resolve()
        if args.respuestas
        else fuente.with_name(fuente.stem + "_respuestas.md")
    )
    cuestionario = md_a_html._slug(fuente.stem)

    run_id = run_state.run_id_de_la_corrida("desplegar-worker-cuestionarios")
    ruta_estado = run_state.ruta_vista(run_id)
    _trazar(run_id, "flujo/inicio", {"cuestionario": cuestionario, "check": args.check})

    def terminar(resultado: dict, codigo: int, estado: str) -> int:
        if ruta_estado is not None:
            run_state.escribir_vista(
                ruta_estado,
                {
                    "run_id": run_id,
                    "current_step": 1,
                    "status": estado,
                    "exit_code": codigo,
                    "cuestionario": cuestionario,
                    "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                },
            )
        _trazar(run_id, "flujo/fin", {"status": estado, "exit_code": codigo})
        if ruta_estado is not None:
            run_state.retirar_vista(ruta_estado)
        if args.json:
            print(json.dumps(resultado, ensure_ascii=False, indent=2))
        else:
            if codigo == 0:
                print(f"Worker de {cuestionario}: {resultado.get('url', '(sin desplegar)')}")
                if resultado.get("secretos"):
                    for nombre, presente in resultado["secretos"].items():
                        print(f"  {'ok  ' if presente else 'FALTA'} {nombre}")
            else:
                print(f"FALLA: {resultado.get('message', 'error')}", file=sys.stderr)
        return codigo

    try:
        nombre_worker, vars_worker = _config_entorno(worker_dir, args.env)
    except ValueError as exc:
        return terminar(
            {"status": "error", "code": 3, "message": str(exc), "env": args.env},
            3,
            "error",
        )
    declarado = str(vars_worker.get("CUESTIONARIO_ID") or "")
    if declarado != cuestionario:
        return terminar(
            {
                "status": "error",
                "code": 3,
                "message": (
                    f"wrangler.jsonc declara CUESTIONARIO_ID={declarado!r} pero la "
                    f"fuente es {cuestionario!r}: desplegar así escribiría la clave de "
                    "este cuestionario en el Worker de otro y dejaría ambos sin "
                    "servicio. Corregir el entorno (o usar --env) antes de repetir."
                ),
                "env": args.env,
                "worker": nombre_worker,
            },
            3,
            "error",
        )
    try:
        clave, preguntas = _leer_clave(fuente, respuestas)
    except (OSError, ValueError) as exc:
        return terminar({"status": "error", "code": 3, "message": str(exc)}, 3, "error")

    resumen = {
        "cuestionario": cuestionario,
        "env": args.env,
        "worker": nombre_worker,
        "preguntas": preguntas,
        "clave_sha256": hashlib.sha256(
            json.dumps(clave, sort_keys=True).encode("utf-8")
        ).hexdigest(),
    }

    try:
        wrangler = _wrangler(args.wrangler)
    except FileNotFoundError as exc:
        return terminar({"status": "error", "code": 4, "message": str(exc), **resumen}, 4, "error")

    if args.check:
        proc = _ejecutar(
            [wrangler, "deploy", "--dry-run"] + (["--env", args.env] if args.env else []),
            worker_dir,
            timeout=300,
        )
        if proc.returncode != 0:
            mensaje = ((proc.stdout or "") + (proc.stderr or ""))[-800:]
            return terminar({"status": "error", "code": 4, "message": mensaje, **resumen}, 4, "error")
        return terminar(
            {"status": "ok", "code": 0, "deploy": "dry-run", **resumen}, 0, "ok"
        )

    quien = _ejecutar([wrangler, "whoami"], worker_dir, timeout=120)
    if quien.returncode != 0:
        return terminar(
            {
                "status": "error",
                "code": 4,
                "message": (
                    "wrangler no está autenticado: ejecutar `wrangler login` (OAuth, "
                    "un clic en el navegador) o definir CLOUDFLARE_API_TOKEN y "
                    "CLOUDFLARE_ACCOUNT_ID en .env"
                ),
                **resumen,
            },
            4,
            "error",
        )

    ruta_clave = _escribir_clave(clave, cuestionario)
    url, salida = _desplegar(wrangler, worker_dir, args.env)
    if url is None:
        return terminar(
            {
                "status": "error",
                "code": 4,
                "message": ("no se pudo desplegar o no se leyó la URL:\n" + salida[-800:]),
                **resumen,
            },
            4,
            "error",
        )

    if args.env:
        esperado = f"https://{nombre_worker}."
        if not url.startswith(esperado):
            return terminar(
                {
                    "status": "error",
                    "code": 4,
                    "message": (
                        f"el despliegue devolvió {url}, que no pertenece a env."
                        f"{args.env} ({esperado}…): no se escribe entrega_url para no "
                        "apuntar el cuestionario al Worker equivocado"
                    ),
                    **resumen,
                },
                4,
                "error",
            )

    secreto = _ejecutar(
        [wrangler, "secret", "put", "CLAVE_JSON"] + (["--env", args.env] if args.env else []),
        worker_dir,
        entrada=ruta_clave.read_text(encoding="utf-8"),
        timeout=180,
    )
    if secreto.returncode != 0:
        return terminar(
            {
                "status": "error",
                "code": 4,
                "message": ("no se pudo fijar CLAVE_JSON:\n" + (secreto.stderr or "")[-500:]),
                "url": url,
                **resumen,
            },
            4,
            "error",
        )

    presentes = _secretos(wrangler, worker_dir, args.env)
    if not presentes["GITHUB_TOKEN"]:
        token = _token_resultados()
        if token:
            alta = _ejecutar(
                [wrangler, "secret", "put", "GITHUB_TOKEN"]
                + (["--env", args.env] if args.env else []),
                worker_dir,
                entrada=token,
                timeout=180,
            )
            if alta.returncode == 0:
                presentes = _secretos(wrangler, worker_dir, args.env)
    if not presentes["GITHUB_TOKEN"]:
        return terminar(
            {
                "status": "error",
                "code": 4,
                "message": (
                    "falta el secreto GITHUB_TOKEN: añadir "
                    "GITHUB_TOKEN_RESULTADOS=<PAT fine-grained con Contents: Read "
                    "and write solo en cero97-ctrl/cuestionarios-resultados> a "
                    ".env y repetir, o ejecutar `wrangler secret put GITHUB_TOKEN` "
                    f"en {worker_dir}"
                ),
                "url": url,
                "secretos": presentes,
                **resumen,
            },
            4,
            "error",
        )

    bien, detalle = _salud(url)
    if not bien:
        return terminar(
            {
                "status": "error",
                "code": 5,
                "message": f"el Worker no responde en /salud: {detalle}",
                "url": url,
                "secretos": presentes,
                **resumen,
            },
            5,
            "error",
        )

    siguiente = []
    if args.actualizar_fuente:
        try:
            _fijar_entrega_url(fuente, url)
        except (OSError, ValueError) as exc:
            return terminar(
                {"status": "error", "code": 1, "message": str(exc), "url": url, **resumen},
                1,
                "error",
            )
        siguiente = [
            f"python3 flujo_evaluacion_web.py --fuente {fuente}",
            "python3 flujo_publicar_cuestionario.py --push",
        ]

    resultado = {
        "status": "ok",
        "code": 0,
        "url": url,
        "secretos": presentes,
        "salud": True,
        "siguiente": siguiente,
        **resumen,
    }
    if not args.no_alert:
        try:
            subprocess.run(
                [PYTHON, str(ALERTAR), "success", "--message",
                 "Worker de cuestionarios desplegado"],
                cwd=RAIZ, capture_output=True, text=True, timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            pass
    return terminar(resultado, 0, "ok")


if __name__ == "__main__":
    sys.exit(main())
