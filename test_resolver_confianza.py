#!/usr/bin/env python3
"""test_resolver_confianza.py — Tests deterministas (0 créditos) de la confianza
del retrieval en resolver_skill.py (Fase 2).

Cubre `_nivel_confianza` (clasificación alta/media/baja) y el aviso de fundamento
débil inyectado al formulador en `_mensaje_usuario`. No necesita API ni embeddings.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "execution"))

import resolver_skill as r  # noqa: E402

FALLOS = []


def check(nombre, cond, detalle=""):
    tag = "OK " if cond else "FAIL"
    print(f"[{tag}] {nombre}" + (f" — {detalle}" if detalle and not cond else ""))
    if not cond:
        FALLOS.append(nombre)


# ── `_nivel_confianza`: niveles ───────────────────────────────────────────────

def dados(scores):
    return [{"score": s} for s in scores]


# Valores de calibración (umbral de 'alta' y alerta de confianza débil)
ALTA = r.CONFIANZA_ALTA
ALERTA = r.ALERTA_SCORE_DEFAULT
MEDIA = (ALERTA + ALTA) / 2  # un score intermedio que debe caer en 'media'


def test_niveles():
    check("alta: score >= CONFIANZA_ALTA",
          r._nivel_confianza(dados([ALTA + 0.1]), ALERTA)["nivel"] == "alta")
    check("media: score entre alerta y alta",
          r._nivel_confianza(dados([MEDIA]), ALERTA)["nivel"] == "media")
    check("baja: score < alerta",
          r._nivel_confianza(dados([ALERTA - 0.05]), ALERTA)["nivel"] == "baja")
    check("baja: sin secciones (mejor_score=0)",
          r._nivel_confianza([], ALERTA)["nivel"] == "baja")
    check("baja con alerta no vacía",
          r._nivel_confianza(dados([ALERTA - 0.05]), ALERTA)["alerta"] != "")
    check("media con alerta vacía",
          r._nivel_confianza(dados([MEDIA]), ALERTA)["alerta"] == "")
    check("alta con alerta vacía",
          r._nivel_confianza(dados([ALTA + 0.1]), ALERTA)["alerta"] == "")


# ── `_nivel_confianza`: umbral configurable ─────────────────────────────────
def test_umbral():
    check("score entre umbral bajo y alerta default => media con alerta menor",
          r._nivel_confianza(dados([MEDIA]), ALERTA)["nivel"] == "media")
    check("baja si el score < alerta default",
          r._nivel_confianza(dados([ALERTA - 0.05]), ALERTA)["nivel"] == "baja")
    conf = r._nivel_confianza(dados([ALERTA - 0.05]), ALERTA - 0.1)
    check("alerta_score se reporta en la salida",
          conf["alerta_score"] == ALERTA - 0.1)
    check("mejor_score se reporta redondeado",
          r._nivel_confianza(dados([ALTA + 0.22891]), ALERTA)["mejor_score"] == ALTA + 0.2289)


# ── `_nivel_confianza`: casos de frontera deterministas ──────────────────────
def test_borde():
    check("media en exactamente el umbral de alerta",
          r._nivel_confianza(dados([ALERTA]), ALERTA)["nivel"] == "media")
    check("baja justo debajo del umbral de alerta",
          r._nivel_confianza(dados([ALERTA - 0.001]), ALERTA)["nivel"] == "baja")
    check("alta en exactamente CONFIANZA_ALTA",
          r._nivel_confianza(dados([ALTA]), ALERTA)["nivel"] == "alta")
    check("media justo debajo de CONFIANZA_ALTA",
          r._nivel_confianza(dados([ALTA - 0.001]), ALERTA)["nivel"] == "media")


# ── `_mensaje_usuario`: aviso de fundamento débil ────────────────────────────
def test_aviso_fundamento():
    secciones = [{"archivo": "references/formulas.md", "titulo": "Ley de Ohm",
                  "texto": "V = I*R"}]
    base = r._mensaje_usuario("problema", secciones, confianza=None)
    check("sin confianza baja no hay aviso",
          "FUNDAMENTO DÉBIL" not in base)

    conf_baja = {"nivel": "baja", "mejor_score": 0.05, "alerta": "x"}
    aviso = r._mensaje_usuario("problema", secciones, confianza=conf_baja)
    check("confianza baja inyecta aviso al formulador",
          "FUNDAMENTO DÉBIL" in aviso and "alcance" in aviso.lower())

    conf_media = {"nivel": "media", "mejor_score": 0.25, "alerta": ""}
    ok = r._mensaje_usuario("problema", secciones, confianza=conf_media)
    check("confianza media no inyecta aviso",
          "FUNDAMENTO DÉBIL" not in ok)

    fb = r._mensaje_usuario("p", secciones, confianza=conf_baja,
                            feedback="NameError: x no definido")
    check("aviso se conserva con feedback de reflexión",
          "FUNDAMENTO DÉBIL" in fb and "NameError" in fb)


if __name__ == "__main__":
    test_niveles()
    test_umbral()
    test_borde()
    test_aviso_fundamento()
    print()
    if FALLOS:
        print(f"{len(FALLOS)} FALLOS: {FALLOS}")
        sys.exit(1)
    print("TODOS LOS TESTS PASARON (0 créditos).")
    sys.exit(0)
