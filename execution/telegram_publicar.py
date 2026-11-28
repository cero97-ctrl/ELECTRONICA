#!/usr/bin/env python3
"""Capa 3: resuelve y ejecuta las órdenes de publicación recibidas por Telegram.

El gateway (capa 2) NO interpreta lenguaje natural: recibe un comando fijo y
llama a este módulo. Aquí vive toda la lógica de decisión, con un vocabulario
cerrado y funciones puras verificables sin red:

    preparar(chat_id, token, "/publicar s02")  -> orden de dry-run
    preparar(chat_id, token, "/confirmar s02") -> orden de push

El flujo es siempre de dos pasos: `/publicar <curso>` sólo prepara y muestra el
payload; `/confirmar <curso>` lo publica. Un token de confirmación ligado al
dry-run evita que un `/confirmar` aislado publique algo que nadie revisó.

`ejecutar_orden()` es el único punto con efectos externos: delega en
`flujo_publicar_cuestionario.py` (capa 2 de publicación) y, en última instancia,
en `execution/publicar_cuestionario.py` (barrera anti-fuga). Esta capa no
reimplementa esa barrera; sólo valida la orden y reporta el resultado.

Códigos de salida (CLI): 0 ok · 2 comando/token inválido · 3 chat no autorizado ·
4 fallo del publicador.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

PYTHON = sys.executable
FLUJO_PUBLICAR = RAIZ / "flujo_publicar_cuestionario.py"

# Vocabulario cerrado. No se aceptan rutas ni nombres de repo desde Telegram.
CURSOS: dict[str, dict[str, str]] = {
    "s02": {
        "web_dir": "cursos/CYBERSEGURIDAD/evaluaciones/web/SEMANA_02",
        "repo": "cero97-ctrl/cuestionarios-ciberseguridad-s02",
        "etiqueta": "Ciberseguridad SEMANA_02 (4 roles)",
    },
}


@dataclass(frozen=True)
class Orden:
    """Orden ya validada, lista para ejecutar."""

    accion: str  # "preparar" | "confirmar"
    curso: str
    web_dir: str
    repo: str
    etiqueta: str
    token: str = ""
    codigo: int = 0
    motivo: str = ""


def _chat_autorizado(chat_id: int, config: dict) -> bool:
    """El chat debe estar en la lista blanca de la directiva del gateway."""
    try:
        permitidos = config["configuration"]["security"]["allowed_chat_ids"]
    except (KeyError, TypeError):
        return False
    return chat_id in {int(item) for item in permitidos}


def _token_esperado(chat_id: int, curso: str, nonce: str, secreto: str) -> str:
    """Token determinista: HMAC del par (chat, curso, nonce) con un secreto local.

    El nonce es un número de época en segundos, así que el token caduca con la
    ventana definida en `preparar()`. No se guarda estado: el mismo triple
    (chat, curso, nonce) con el mismo secreto da siempre el mismo token.
    """
    mensaje = f"{chat_id}|{curso}|{nonce}".encode("utf-8")
    return hmac.new(secreto.encode("utf-8"), mensaje, hashlib.sha256).hexdigest()[:16]


def preparar(
    chat_id: int, texto: str, config: dict, secreto: str, ahora: float | None = None
) -> Orden:
    """Parsea un comando fijo y devuelve una orden validada o un error.

    Formatos aceptados (sin argumentos extra, sin texto libre):
        /publicar s02
        /confirmar s02 <token>
    """
    ahora = time.time() if ahora is None else ahora
    if not _chat_autorizado(chat_id, config):
        return Orden("", "", "", "", "", codigo=3, motivo="chat no autorizado")

    partes = (texto or "").strip().split()
    if len(partes) < 2 or partes[0] not in ("/publicar", "/confirmar"):
        return Orden(
            "", "", "", "", "",
            codigo=2,
            motivo="comando no reconocido; usa /publicar s02 o /confirmar s02 <token>",
        )
    comando, curso = partes[0], partes[1]
    datos = CURSOS.get(curso)
    if datos is None:
        return Orden(
            "", "", "", "", "",
            codigo=2,
            motivo=f"curso {curso!r} no permitido; disponibles: {', '.join(CURSOS)}",
        )

    if comando == "/publicar":
        if len(partes) != 2:
            return Orden(
                "", "", "", "", "",
                codigo=2,
                motivo="uso: /publicar s02 (sin argumentos adicionales)",
            )
        nonce = str(int(ahora))
        return Orden(
            "preparar",
            curso,
            datos["web_dir"],
            datos["repo"],
            datos["etiqueta"],
            token=_token_esperado(chat_id, curso, nonce, secreto),
        )

    # /confirmar: exige exactamente el token del dry-run y dentro de la ventana.
    if len(partes) != 3:
        return Orden(
            "", "", "", "", "",
            codigo=2,
            motivo="uso: /confirmar s02 <token>",
        )
    token = partes[2]
    try:
        ventana = int(config["configuration"]["telegram"].get("confirm_window_seconds", 900))
    except (KeyError, TypeError, ValueError):
        ventana = 900
    for delta in range(0, ventana + 1, 30):
        esperado = _token_esperado(chat_id, curso, str(int(ahora) - delta), secreto)
        if hmac.compare_digest(token, esperado):
            return Orden(
                "confirmar",
                curso,
                datos["web_dir"],
                datos["repo"],
                datos["etiqueta"],
                token=token,
            )
    return Orden(
        "", "", "", "", "",
        codigo=2,
        motivo="token ausente, incorrecto o caducado; vuelve a /publicar s02",
    )


def comando_publicar(orden: Orden) -> list[str]:
    """Construye el argv del orquestador de publicación (sin shell, sin injection)."""
    base = [
        PYTHON,
        str(FLUJO_PUBLICAR),
        "--web-dir",
        orden.web_dir,
        "--repo",
        orden.repo,
        "--json",
        "--no-alert",
    ]
    if orden.accion == "preparar":
        return base + ["--dry-run"]
    return base + ["--push", "--visibilidad", "public"]


def ejecutar_orden(orden: Orden, timeout: int = 900) -> dict:
    """Ejecuta la orden ya validada y devuelve un dict serializable."""
    if orden.codigo:
        return {"status": "error", "code": orden.codigo, "message": orden.motivo}
    cmd = comando_publicar(orden)
    try:
        proc = subprocess.run(
            cmd, cwd=RAIZ, capture_output=True, text=True, timeout=timeout
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"status": "error", "code": 4, "message": f"no se pudo ejecutar: {exc}"}
    try:
        datos = json.loads(proc.stdout)
    except json.JSONDecodeError:
        datos = {
            "status": "error",
            "code": 4,
            "message": (proc.stdout or proc.stderr or "sin salida")[-800:],
        }
    datos.setdefault("code", proc.returncode)
    datos["accion"] = orden.accion
    datos["curso"] = orden.curso
    datos["etiqueta"] = orden.etiqueta
    return datos


def ruta_opencode() -> str:
    """Resuelve el binario del CLI sin depender del PATH del servicio systemd."""
    hallado = shutil.which("opencode")
    if hallado:
        return hallado
    candidato = Path.home() / ".opencode" / "bin" / "opencode"
    if candidato.exists():
        return str(candidato)
    raise FileNotFoundError("no se encontró el CLI de opencode")


def reenviar_a_sesion(
    texto: str,
    session_id: str,
    idempotencia: str,
    *,
    binario: str | None = None,
    timeout: int = 60,
    enviar=None,
) -> dict:
    """Deposita un comando fijo en la sesión de OpenCode del orquestador.

    No interpreta el texto: lo valida contra el mismo vocabulario que
    `preparar()` antes de enviarlo. Usa `POST /api/session/{id}/prompt` vía el
    CLI `opencode api` (descubre servicio y auth) y un `id` de idempotencia
    derivado del update_id de Telegram, así que un reintento no duplica la orden.

    `enviar` permite inyectar un transporte falso en las pruebas (sin red).
    """
    if not re.fullmatch(r"ses_[A-Za-z0-9]+", session_id):
        return {"status": "error", "code": 2, "message": "session_id inválido"}
    # Barrera: sólo se reenvían los dos comandos canónicos, nunca texto libre.
    if not (
        re.fullmatch(r"/publicar s02", texto)
        or re.fullmatch(r"/confirmar s02 [0-9a-f]{16}", texto)
    ):
        return {
            "status": "error",
            "code": 2,
            "message": "solo se reenvían /publicar s02 o /confirmar s02 <token>",
        }
    payload = {
        # Session.Message.ID exige el prefijo msg_ (OpenAPI de v2.4.2).
        "id": f"msg_telegram_{idempotencia}",
        "text": texto,
        "delivery": "queue",
    }
    if enviar is not None:
        return enviar(session_id, payload)
    cmd = [
        binario or os.getenv("OPENCODE_BIN") or ruta_opencode(),
        "api",
        "post",
        f"/api/session/{session_id}/prompt",
        "--data",
        json.dumps(payload, ensure_ascii=False),
    ]
    try:
        proc = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"status": "error", "code": 4, "message": f"no se pudo reenviar: {exc}"}
    if proc.returncode != 0:
        return {
            "status": "error",
            "code": 4,
            "message": (proc.stderr or proc.stdout or "sin salida")[-800:],
        }
    try:
        respuesta = json.loads(proc.stdout)
    except json.JSONDecodeError:
        respuesta = {"respuesta": proc.stdout.strip()[:400]}
    respuesta["status"] = "ok"
    respuesta["code"] = 0
    respuesta["session_id"] = session_id
    respuesta["texto"] = texto
    return respuesta


def mensaje_puente(orden: Orden, reenvio: dict) -> str:
    """Confirmación determinista para Telegram (el token lo calcula este módulo)."""
    if orden.codigo:
        return f"❌ {orden.motivo}"
    if reenvio.get("code", 1) != 0:
        return f"❌ No pude entregar la orden a la sesión: {reenvio.get('message', 'error')}"
    if orden.accion == "preparar":
        return (
            "✅ Orden enviada a tu sesión de OpenCode: `/publicar s02`.\n"
            f"Token de confirmación: `{orden.token}` (válido 15 min).\n"
            "La respuesta del dry-run la verás en OpenCode. "
            f"Para publicar: `/confirmar s02 {orden.token}`"
        )
    return (
        "✅ Orden de confirmación enviada a tu sesión de OpenCode: "
        f"`/confirmar s02 {orden.token}`.\n"
        "La ejecución y su resultado los verás en OpenCode."
    )


def resumen_telegram(orden: Orden, resultado: dict) -> str:
    """Texto corto para Telegram; nunca incluye la clave ni rutas privadas."""
    if orden.codigo:
        return f"❌ {orden.motivo}"
    if resultado.get("code", 1) != 0:
        return f"❌ Falló la publicación: {resultado.get('message', 'error')}"
    if orden.accion == "preparar":
        archivos = resultado.get("archivos", [])
        nombres = ", ".join(item.get("archivo", "?") for item in archivos)
        return (
            f"✅ *Dry-run listo* — {orden.etiqueta}\n"
            f"Archivos (solo alumno): {nombres or 'ninguno'}\n"
            f"Para publicar: `/confirmar {orden.curso} {orden.token}`"
        )
    visibilidad = resultado.get("visibilidad", "?")
    return (
        f"✅ *Publicado* — {orden.etiqueta}\n"
        f"Repo: {orden.repo} · visibilidad: {visibilidad}\n"
        f"URL: {resultado.get('url', '?')}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chat-id", type=int, required=True)
    parser.add_argument("--texto", required=True, help="Comando fijo de Telegram.")
    parser.add_argument(
        "--config", default="directives/telegram_gateway.yaml", help="Directiva YAML."
    )
    args = parser.parse_args()

    import yaml
    from dotenv import load_dotenv

    load_dotenv()
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    secreto = os.getenv("TELEGRAM_PUBLISH_SECRET") or os.getenv("TELEGRAM_BOT_TOKEN") or ""
    ahora = datetime.now(timezone.utc).timestamp()

    orden = preparar(args.chat_id, args.texto, config, secreto, ahora=ahora)
    if orden.codigo:
        print(json.dumps({"status": "error", "code": orden.codigo, "message": orden.motivo}))
        return orden.codigo
    resultado = ejecutar_orden(orden)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return int(resultado.get("code", 1))


if __name__ == "__main__":
    sys.exit(main())
