#!/usr/bin/env python3
"""Pruebas sin red del parser de publicación por Telegram.

Verifica que la lógica de decisión vive en la capa 3: vocabulario cerrado,
chat autorizado, token con caducidad y argv que nunca sale del publicador
oficial. No llama a Telegram ni a GitHub.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import telegram_publicar as T  # noqa: E402

CONFIG = {
    "configuration": {
        "security": {"allowed_chat_ids": [8671067338]},
        "telegram": {"confirm_window_seconds": 900},
    }
}
SECRETO = "secreto-de-prueba"
AHORA = 1_800_000_000.0


def test_chat_autorizado():
    assert T._chat_autorizado(8671067338, CONFIG) is True
    assert T._chat_autorizado(1315284048, CONFIG) is False
    assert T._chat_autorizado(8671067338, {"configuration": {}}) is False


def test_publicar_solo_prepara():
    orden = T.preparar(8671067338, "/publicar s02", CONFIG, SECRETO, AHORA)
    assert orden.codigo == 0
    assert orden.accion == "preparar"
    assert orden.curso == "s02"
    assert orden.web_dir.endswith("SEMANA_02")
    assert orden.repo == "cero97-ctrl/cuestionarios-ciberseguridad-s02"
    assert len(orden.token) == 16


def test_argv_no_es_shell_y_solo_pide_dry_run():
    orden = T.preparar(8671067338, "/publicar s02", CONFIG, SECRETO, AHORA)
    argv = T.comando_publicar(orden)
    assert argv[0].endswith("python") or "python" in argv[0]
    assert str(T.FLUJO_PUBLICAR) in argv
    assert "--dry-run" in argv
    assert "--push" not in argv
    assert "--visibilidad" not in argv
    assert "--web-dir" in argv and orden.web_dir in argv
    assert ";" not in " ".join(argv)


def test_confirmar_con_token_valido():
    preparada = T.preparar(8671067338, "/publicar s02", CONFIG, SECRETO, AHORA)
    orden = T.preparar(
        8671067338, f"/confirmar s02 {preparada.token}", CONFIG, SECRETO, AHORA + 60
    )
    assert orden.codigo == 0
    assert orden.accion == "confirmar"
    argv = T.comando_publicar(orden)
    assert "--push" in argv
    assert "--visibilidad" in argv and "public" in argv
    assert "--dry-run" not in argv


def test_token_caducado_se_rechaza():
    preparada = T.preparar(8671067338, "/publicar s02", CONFIG, SECRETO, AHORA)
    vencida = T.preparar(
        8671067338,
        f"/confirmar s02 {preparada.token}",
        CONFIG,
        SECRETO,
        AHORA + 901,
    )
    assert vencida.codigo == 2
    assert "caducado" in vencida.motivo or "token" in vencida.motivo


def test_token_de_otro_chat_no_vale():
    preparada = T.preparar(8671067338, "/publicar s02", CONFIG, SECRETO, AHORA)
    ajena = T.preparar(
        999, f"/confirmar s02 {preparada.token}", CONFIG, SECRETO, AHORA
    )
    assert ajena.codigo == 3  # ni siquiera se parsea: chat no autorizado


def test_texto_libre_se_rechaza():
    for texto in ("publica el cuestionario", "/publica s02", "/publicar", "/publicar s02 extra"):
        orden = T.preparar(8671067338, texto, CONFIG, SECRETO, AHORA)
        assert orden.codigo == 2, texto
        assert orden.accion == ""


def test_curso_desconocido_y_ruta_inyectada_se_rechazan():
    for texto in ("/publicar s01", "/publicar ../secreto", "/publicar /etc/passwd"):
        orden = T.preparar(8671067338, texto, CONFIG, SECRETO, AHORA)
        assert orden.codigo == 2, texto
        assert "no permitido" in orden.motivo


def test_resumen_no_filtra_rutas_privadas_ni_clave():
    orden = T.preparar(8671067338, "/publicar s02", CONFIG, SECRETO, AHORA)
    mensaje = T.resumen_telegram(
        orden, {"code": 0, "archivos": [{"archivo": "rol_rojo_alumno.html"}]}
    )
    assert "rol_rojo_alumno.html" in mensaje
    assert "fuentes" not in mensaje
    assert "const CLAVE" not in mensaje
    assert orden.token in mensaje


def test_resumen_de_fallo_no_dice_publicado():
    orden = T.preparar(8671067338, "/publicar s02", CONFIG, SECRETO, AHORA)
    mensaje = T.resumen_telegram(orden, {"code": 3, "message": "fuga detectada"})
    assert mensaje.startswith("❌")
    assert "Publicado" not in mensaje


def test_offset_persistido_sobrevive_a_reinicio(tmp_path=None):
    """Un reinicio no debe reprocesar un /confirmar viejo."""
    import tempfile

    with tempfile.TemporaryDirectory() as temporal:
        ruta = Path(temporal) / "offset.txt"
        import telegram_api

        anterior = telegram_api.OFFSET_PATH
        try:
            telegram_api.OFFSET_PATH = ruta
            assert telegram_api.leer_offset() is None
            telegram_api.guardar_offset(4321)
            assert telegram_api.leer_offset() == 4321
            # Simula un nuevo proceso: nueva lectura desde disco.
            assert telegram_api.leer_offset() == 4321
        finally:
            telegram_api.OFFSET_PATH = anterior


def main() -> int:
    pruebas = [obj for nombre, obj in sorted(globals().items()) if nombre.startswith("test_")]
    fallos = 0
    for prueba in pruebas:
        try:
            prueba()
        except AssertionError as exc:
            fallos += 1
            print(f"FALLO {prueba.__name__}: {exc}")
        else:
            print(f"ok    {prueba.__name__}")
    print(f"\n{len(pruebas) - fallos}/{len(pruebas)} pruebas OK")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
