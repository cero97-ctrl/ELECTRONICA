#!/usr/bin/env python3
"""Capa 2: publica la variante alumno de los cuestionarios en GitHub Pages.

Orquesta `execution/publicar_cuestionario.py`. La decisión de qué se publica no
vive aquí: la capa 3 recolecta solo `*_alumno.html`, rechaza cualquier archivo
con la clave o el modo docente y arma el índice sin enlaces al docente. Este
flujo solo resuelve rutas, encadena el script, agrega el resultado y deja
trazabilidad.

El repo del curso es público; `_docente.html` y `fuentes/*_respuestas.md` NUNCA
se publican. Destino por defecto: `cero97-ctrl/cuestionarios` (repo separado),
servido en `https://cero97-ctrl.github.io/cuestionarios/`.

Uso:
    python3 flujo_publicar_cuestionario.py --dry-run
    python3 flujo_publicar_cuestionario.py --push
    python3 flujo_publicar_cuestionario.py --push --repo cero97-ctrl/otro --json

Códigos de salida: 0 ok · 1 error de E/S · 3 payload rechazado (fuga) ·
4 gh/git falló · 5 ruta rechazada.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
EJECUCION = RAIZ / "execution"
PYTHON = sys.executable
PUBLICADOR = EJECUCION / "publicar_cuestionario.py"
SESION_LOG = EJECUCION / "sesion_log.py"
ALERTAR = EJECUCION / "alert_user.py"

sys.path.insert(0, str(EJECUCION))
import run_state  # noqa: E402  (capa 3: vista por corrida)


def _trazar(run_id: str, tipo: str, datos: dict) -> bool:
    try:
        proc = subprocess.run(
            [
                PYTHON,
                str(SESION_LOG),
                "add",
                "--run",
                run_id,
                "--tipo",
                tipo,
                "--datos",
                json.dumps(datos, ensure_ascii=False),
            ],
            cwd=RAIZ,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def _publicar(args: argparse.Namespace) -> dict:
    cmd = [PYTHON, str(PUBLICADOR), "--web-dir", args.web_dir, "--json"]
    if args.repo:
        cmd.extend(["--repo", args.repo])
    if args.push:
        cmd.append("--push")
    if args.visibilidad:
        cmd.extend(["--visibilidad", args.visibilidad])
    if args.dry_run:
        cmd.append("--dry-run")
    try:
        proc = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True, timeout=900)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"status": "error", "code": 1, "message": f"no se pudo ejecutar: {exc}"}
    try:
        datos = json.loads(proc.stdout)
    except json.JSONDecodeError:
        datos = {
            "status": "error",
            "code": 1,
            "message": (proc.stdout or proc.stderr or "sin salida")[-800:],
        }
    datos.setdefault("code", proc.returncode)
    return datos


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publica la variante alumno de los cuestionarios en GitHub Pages."
    )
    parser.add_argument(
        "--web-dir",
        default="cursos/CYBERSEGURIDAD/evaluaciones/web",
        help="Carpeta web del curso.",
    )
    parser.add_argument("--repo", default=None, help="owner/nombre destino.")
    parser.add_argument("--push", action="store_true", help="Crea/actualiza el repo y Pages.")
    parser.add_argument(
        "--visibilidad",
        choices=["public", "private"],
        default=None,
        help=(
            "Cambia la visibilidad del repo destino. `private` deja la URL en 404 "
            "(Pages no sirve repos privados sin plan de pago); `public` la devuelve."
        ),
    )
    parser.add_argument("--dry-run", action="store_true", help="Solo prepara el payload.")
    parser.add_argument("--json", action="store_true", help="Salida JSON.")
    parser.add_argument("--no-alert", action="store_true", help="Sin alerta audible.")
    args = parser.parse_args()

    run_id = run_state.run_id_de_la_corrida("publicar-cuestionario")
    ruta_estado = run_state.ruta_vista(run_id)
    _trazar(
        run_id,
        "flujo/inicio",
        {"web_dir": args.web_dir, "repo": args.repo, "push": args.push},
    )

    resultado = _publicar(args)
    codigo = int(resultado.get("code", 1))
    estado = "ok" if codigo == 0 else "error"
    if args.dry_run and codigo == 0:
        estado = "dry-run"

    if ruta_estado is not None:
        run_state.escribir_vista(
            ruta_estado,
            {
                "run_id": run_id,
                "current_step": 1,
                "status": estado,
                "exit_code": codigo,
                "repo": resultado.get("repo"),
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
            print(f"Publicación — {resultado.get('repo')}")
            for item in resultado.get("archivos", []):
                print(f"  ok    {item['archivo']}  {item['sha256'][:16]}")
            print(f"URL: {resultado.get('url')}")
            if resultado.get("visibilidad"):
                print(f"  visibilidad: {resultado['visibilidad']}")
                if resultado["visibilidad"] == "private":
                    print("  la URL responde 404 mientras el repo sea privado")
            if not resultado.get("publicado"):
                print(
                    "  (solo cambió la visibilidad; no se subió contenido)"
                    if resultado.get("visibilidad")
                    else "  (preparado, sin publicar)"
                )
            elif not resultado.get("pages_visible"):
                print("  aviso: Pages aún no responde (puede tardar un minuto)")
        else:
            print(f"FALLA: {resultado.get('message', 'error')}", file=sys.stderr)
            for problema in resultado.get("problemas", []):
                print(f"  - {problema}", file=sys.stderr)

    if codigo == 0 and args.push and not args.no_alert:
        try:
            subprocess.run(
                [
                    PYTHON,
                    str(ALERTAR),
                    "success",
                    "--message",
                    "Cuestionarios publicados en GitHub Pages",
                ],
                cwd=RAIZ,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            pass

    return codigo


if __name__ == "__main__":
    sys.exit(main())
