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


# ── Multi-skill: `_combinar_retrievals` (función pura, sin embeddings) ──────

def test_multi_skill():
    ra = [{"score": 0.6, "titulo": "A1", "skill": "/x/electronica"},
          {"score": 0.4, "titulo": "A2", "skill": "/x/electronica"}]
    rb = [{"score": 0.9, "titulo": "B1", "skill": "/y/fisica"},
          {"score": 0.2, "titulo": "B2", "skill": "/y/fisica"}]
    res = r._combinar_retrievals([ra, rb], top_k=2)

    check("combina y corta al top_k GLOBAL",
          len(res["secciones"]) == 2)
    check("ordena por score descendente",
          [s["score"] for s in res["secciones"]] == [0.9, 0.6])
    check("etiqueta cada sección con su fuente",
          res["secciones"][0]["fuente"] == "fisica"
          and res["secciones"][1]["fuente"] == "electronica")
    check("reporta por-skill el mejor score",
          {s["skill"]: s["mejor_score"] for s in res["skills"]}
          == {"electronica": 0.6, "fisica": 0.9})
    check("reporta secciones_recuperadas por skill (reserva 1 c/u con top_k=2)",
          {s["skill"]: s["secciones_recuperadas"] for s in res["skills"]}
          == {"electronica": 1, "fisica": 1})

    # La confianza del retrieval se calcula sobre la combinación: el mejor de todos.
    comb_tags = r._nivel_confianza(res["secciones"], r.ALERTA_SCORE_DEFAULT)
    check("confianza combina el mejor score global (0.9 => alta)",
          comb_tags["nivel"] == "alta" and comb_tags["mejor_score"] == 0.9)

    # Skill sin secciones se omite, no rompe.
    res_vacio = r._combinar_retrievals([[], ra], top_k=6)
    check("skill vacío se omite sin romper",
          len(res_vacio["secciones"]) == 2
          and all(s["fuente"] == "electronica" for s in res_vacio["secciones"])
          and [s["skill"] for s in res_vacio["skills"]] == ["electronica"])

    # Todo vacío => sin secciones, skills vacío.
    res_todo_vacio = r._combinar_retrievals([[], []], top_k=6)
    check("todo vacío => 0 secciones y 0 skills",
          res_todo_vacio["secciones"] == [] and res_todo_vacio["skills"] == [])


# ── Multi-skill: aviso de fundamento débil menciona 'skills' en plural ───────
def test_aviso_multiskill():
    secciones = [{"archivo": "references/formulas.md", "titulo": "Ley de Ohm",
                  "texto": "V = I*R", "fuente": "electronica", "skill": "/x/electronica"}]
    conf_baja = {"nivel": "baja", "mejor_score": 0.05, "alerta": "x"}
    aviso = r._mensaje_usuario("p", secciones, confianza=conf_baja)
    check("aviso de fundamento débil usa 'skills' en plural (multi)",
          "alcance de los" in aviso and "skills" in aviso)


# ── Cuotas por skill: reserva del mejor skill (no-dilución) ──────────────────
def test_cuotas_no_diluciona():
    # Skill de dominio con pocas secciones de score alto, skill lateral con muchas medias.
    dominio = [{"score": 0.67, "titulo": "Thevenin", "texto": "metodo thevenin",
                "skill": "/x/circuitos"},
               {"score": 0.62, "titulo": "divisor", "texto": "divisor tension",
                "skill": "/x/circuitos"}]
    lateral = [{"score": 0.36 + i * 0.01, "titulo": f"b{i}", "texto": f"lateral {i}",
                "skill": "/y/comput"} for i in range(6)]
    res = r._combinar_retrievals([dominio, lateral], top_k=6)

    check("cuotas: skill de dominio no queda desplazado (no-dilución)",
          "circuitos" in [s["fuente"] for s in res["secciones"]])
    check("cuotas: se conserva la mejor sección del dominio",
          any(s["score"] == 0.67 or s["score"] == 0.62
              for s in res["secciones"] if s["fuente"] == "circuitos"))
    check("cuotas: orden final descendente",
          [s["score"] for s in res["secciones"]]
          == sorted([s["score"] for s in res["secciones"]], reverse=True))
    check("cuotas: mejor_score del skill usa TODAS sus secciones (no solo el contexto)",
          {x["skill"]: x["mejor_score"] for x in res["skills"]}
          == {"circuitos": 0.67, "comput": 0.41})
    check("cuotas: secciones_recuperadas = aporte real al contexto",
          {x["skill"]: x["secciones_recuperadas"] for x in res["skills"]}
          == {"circuitos": 2, "comput": 4})


def test_cuotas_topk_menor_que_skills():
    skills = [[{"score": 0.9, "titulo": "a", "texto": "secc a", "skill": "/s1"}],
              [{"score": 0.8, "titulo": "b", "texto": "secc b", "skill": "/s2"}],
              [{"score": 0.7, "titulo": "c", "texto": "secc c", "skill": "/s3"}],
              [{"score": 0.6, "titulo": "d", "texto": "secc d", "skill": "/s4"}]]
    res = r._combinar_retrievals(skills, top_k=3)
    check("cuotas: top_k menor que n_skills => solo top_k secciones",
          len(res["secciones"]) == 3)
    check("cuotas: se toman las 3 mejores reservas",
          sorted(s["score"] for s in res["secciones"]) == [0.7, 0.8, 0.9])


def test_cuotas_llenan_exacto():
    a = [{"score": 0.9, "titulo": f"a{i}", "texto": f"aa {i}", "skill": "/s1"} for i in range(3)]
    b = [{"score": 0.8, "titulo": f"b{i}", "texto": f"bb {i}", "skill": "/s2"} for i in range(3)]
    res = r._combinar_retrievals([a, b], top_k=5)
    check("cuotas: se llena el top_k exactamente (2 skills, top_k=5)",
          len(res["secciones"]) == 5)
    check("cuotas: reparto equitativo (3/2)",
          {x["skill"]: x["secciones_recuperadas"] for x in res["skills"]}
          == {"s1": 3, "s2": 2})


def test_cuotas_dedup_por_texto():
    mismo_texto = "V = I*R"
    ra = [{"score": 0.9, "titulo": "Ohm A", "texto": mismo_texto, "skill": "/s1"},
          {"score": 0.7, "titulo": "otra A", "texto": "extra A", "skill": "/s1"}]
    rb = [{"score": 0.8, "titulo": "Ohm B", "texto": mismo_texto, "skill": "/s2"}]
    res = r._combinar_retrievals([ra, rb], top_k=4)
    textos = [s["texto"] for s in res["secciones"]]
    check("cuotas: se deduplica la misma sección repetida entre skills",
          textos.count(mismo_texto) == 1)
    check("cuotas: se conserva el texto de mayor score al deduplicar",
          any(s["texto"] == mismo_texto and s["score"] == 0.9 for s in res["secciones"]))


if __name__ == "__main__":
    test_niveles()
    test_umbral()
    test_borde()
    test_aviso_fundamento()
    test_multi_skill()
    test_aviso_multiskill()
    test_cuotas_no_diluciona()
    test_cuotas_topk_menor_que_skills()
    test_cuotas_llenan_exacto()
    test_cuotas_dedup_por_texto()
    print()
    if FALLOS:
        print(f"{len(FALLOS)} FALLOS: {FALLOS}")
        sys.exit(1)
    print("TODOS LOS TESTS PASARON (0 créditos).")
    sys.exit(0)
