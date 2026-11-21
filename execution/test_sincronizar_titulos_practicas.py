#!/usr/bin/env python3
"""
Pruebas del sincronizador de títulos (capa 3), sin red y sin escritura.

Fija dos reglas que ya_costaron un bug real:
  1. Los scalar citados se leen SIN comillas y se reescriben con el MISMO
     estilo de citado. Un título con ': ' escrito como scalar plano rompe YAML.
  2. Laboratorio I mezcla talleres (1..4) y prácticas (5..10); se detectan por
     existencia de archivo, nunca por adivinanza ni por nombre de curso.

Ejecutar: python3 execution/test_sincronizar_titulos_practicas.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "execution"))
import sincronizar_titulos_practicas as mod  # noqa: E402

FALLOS: list[str] = []
PRUEBAS = 0


def comprobar(nombre: str, condicion: bool, detalle: str = "") -> None:
    global PRUEBAS
    PRUEBAS += 1
    if condicion:
        print(f"  ok   {nombre}")
    else:
        FALLOS.append(f"{nombre}: {detalle}")
        print(f"  FAIL {nombre}: {detalle}")


# --- descomillar / cotizar: el bug del ':' -----------------------------------
comprobar("descomilla comillas simples",
          mod.descomillar("'Del objeto: propagar'") == "Del objeto: propagar")
comprobar("descomilla comillas dobles",
          mod.descomillar('"Del objeto: propagar"') == "Del objeto: propagar")
comprobar("deja el scalar plano intacto",
          mod.descomillar("Práctica 05 — Volumen") == "Práctica 05 — Volumen")
comprobar("no confunde comillas internas",
          mod.descomillar("'Curso de 'Física''") == "Curso de 'Física'")

comprobar(" preserva comillas simples",
          mod.cotizar("Taller 02 — Del objeto: propagar", "'resumen'") ==
          "'Taller 02 — Del objeto: propagar'")
comprobar("cita un ': ' aunque el original fuera plano",
          mod.cotizar("Taller 02 — Del objeto: propagar", "resumen") ==
          "'Taller 02 — Del objeto: propagar'")
comprobar("deja plano un título sin caracteres especiales",
          mod.cotizar("Práctica 05 — Volumen", "resumen") ==
          "Práctica 05 — Volumen")
comprobar("duplica comillas simples internas",
          mod.cotizar("Curso de 'Física'", "'resumen'") == "'Curso de ''Física'''")

# --- edición quirúrgica sobre un fragmento con el caso real de Lab I ----------
FRAGMENTO = """  - numero: 1
    titulo: La medición
    practica:
      titulo: 'Medición, apreciación y expresión de resultados'
      horas: 2
  - numero: 2
    titulo: Propagación
    practica:
      titulo: 'Del objeto al resultado: propagar sin inventar cifras'
      horas: 2
"""
OFICIALES = {
    1: "Taller 01 — Medición, apreciación y expresión de resultados",
    2: "Taller 02 — Del objeto al resultado: propagar sin inventar cifras",
}
actuales = mod.titulos_actuales(FRAGMENTO)
comprobar("titulos_actuales quita las comillas",
          actuales == {1: "Medición, apreciación y expresión de resultados",
                       2: "Del objeto al resultado: propagar sin inventar cifras"},
          str(actuales))

editado, cambios = mod.sustituir_titulos(FRAGMENTO, OFICIALES)
comprobar("detecta exactamente 2 cambios", len(cambios) == 2, str(cambios))
comprobar("el cambio anterior se reporta sin comillas",
          cambios[1]["anterior"] == "Del objeto al resultado: propagar sin inventar cifras")
comprobar("respeta los titulos de nivel semana",
          "titulo: La medición" in editado and "titulo: Propagación" in editado)
comprobar("respeta otras claves del bloque", "horas: 2" in editado)
comprobar("escribe el título con ':' entre comillas simples",
          "titulo: 'Taller 02 — Del objeto al resultado: propagar sin inventar cifras'" in editado,
          editado)

# La barrera real: el YAML resultante debe seguir siendo válido y decir exactamente
# lo que el .tex impone. json no basta; aquí sí hay un parser YAML disponible.
datos = yaml.safe_load(editado)
comprobar("el YAML editado sigue siendo válido", isinstance(datos, list))
comprobar("el parser lee los títulos oficiales",
          [s["practica"]["titulo"] for s in datos] == [OFICIALES[1], OFICIALES[2]],
          str([s["practica"]["titulo"] for s in datos]))
comprobar("aplicar dos veces no cambia nada",
          mod.sustituir_titulos(editado, OFICIALES)[1] == [])

# --- detección real de talleres y prácticas en los dos cursos -----------------
LAB1 = RAIZ / "cursos/LABORATORIO_I_FISICA/curso.yaml"
LAB2 = RAIZ / "cursos/LABORATORIO_II_FISICA/curso.yaml"

ruta, prefijo = mod.ruta_y_prefijo(LAB1, 1)
comprobar("Lab I semana 1 apunta a taller_01.tex",
          ruta.name == "taller_01.tex" and prefijo == "Taller 01")
ruta, prefijo = mod.ruta_y_prefijo(LAB1, 5)
comprobar("Lab I semana 5 apunta a practica_05.tex",
          ruta.name == "practica_05.tex" and prefijo == "Práctica 05")
ruta, prefijo = mod.ruta_y_prefijo(LAB2, 1)
comprobar("Lab II semana 1 apunta a practica_01.tex",
          ruta.name == "practica_01.tex" and prefijo == "Práctica 01")

oficiales_lab1 = mod.titulos_oficiales(LAB1)
comprobar("Lab I extrae 10 títulos", len(oficiales_lab1) == 10)
comprobar("Lab I: semanas 1..4 son talleres",
          all(oficiales_lab1[n].startswith(f"Taller {n:02d} —") for n in range(1, 5)),
          str([oficiales_lab1[n] for n in range(1, 5)]))
comprobar("Lab I: semanas 5..10 son prácticas",
          all(oficiales_lab1[n].startswith(f"Práctica {n:02d} —") for n in range(5, 11)),
          str([oficiales_lab1[n] for n in range(5, 11)]))
comprobar("Lab I preserva el ':' del título 2",
          oficiales_lab1[2] ==
          "Taller 02 — Del objeto al resultado: propagar sin inventar cifras",
          oficiales_lab1[2])

oficiales_lab2 = mod.titulos_oficiales(LAB2)
comprobar("Lab II extrae 10 títulos de práctica",
          len(oficiales_lab2) == 10 and
          all(t.startswith(f"Práctica {n:02d} —") for n, t in oficiales_lab2.items()))

# Un archivo inexistente debe fallar ruidosamente, no inventar un título.
try:
    mod.extraer_titulo_tex(LAB1.parent / "practicas" / "no_existe.tex", 1, "Taller 01")
except ValueError:
    comprobar("un .tex inexistente falla con ValueError", True)
else:
    comprobar("un .tex inexistente falla con ValueError", False)

print("=" * 60)
print(f"{PRUEBAS - len(FALLOS)}/{PRUEBAS} aserciones OK")
if FALLOS:
    print("Fallos:")
    for fallo in FALLOS:
        print(f"  - {fallo}")
    sys.exit(1)
print("Sin fallos.")
