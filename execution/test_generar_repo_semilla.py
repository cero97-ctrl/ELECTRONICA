#!/usr/bin/env python3
"""Pruebas de `execution/generar_repo_semilla.py` (capa 3).

Fijan el contrato del repo semilla: 10 semanas con datos/analisis/figuras,
README con roles y tabla de entregas, plantilla sin datos personales, salida
determinista, y que `--forzar` nunca borre trabajo existente del grupo.

Ejecutar: python3 execution/test_generar_repo_semilla.py
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "execution/generar_repo_semilla.py"
CURSO = RAIZ / "cursos/LABORATORIO_II_FISICA/curso.yaml"
FALLOS: list[str] = []
PRUEBAS = 0


def comprobar(nombre: str, condicion: bool, detalle: str = "") -> None:
    global PRUEBAS
    PRUEBAS += 1
    if condicion:
        print(f"  ok   {nombre}")
    else:
        print(f"  FALLA {nombre}" + (f" -- {detalle}" if detalle else ""))
        FALLOS.append(nombre)


spec = importlib.util.spec_from_file_location("semilla_bajo_test", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

datos = mod.cargar_descriptor(CURSO)
titulos = mod.titulos_practicas(datos)
plan = mod.plan_de_archivos(datos)

comprobar("el descriptor real se carga", isinstance(datos, dict) and "semanas" in datos)
comprobar("hay 10 semanas", len(titulos) == 10 and set(titulos) == set(range(1, 11)))
comprobar("semana 1 trae el título oficial de practica_01.tex",
          titulos[1] == "Práctica 01 — MANEJO DEL INSTRUMENTAL ELÉCTRICO Y DETERMINACIÓN DE LA CARACTERÍSTICA CORRIENTE-VOLTAJE (I-V) DE ALGUNOS DISPOSITIVOS",
          titulos.get(1, ""))
comprobar("semana 10 trae el título oficial de practica_10.tex",
          titulos[10] == "Práctica 10 — Examen práctico individual y cierre del portafolio",
          titulos.get(10, ""))
comprobar("los cuatro roles vienen del descriptor",
          mod.nombres_roles(datos) == ["Medición", "Análisis", "Documentación", "Verificación"],
          str(mod.nombres_roles(datos)))
comprobar("el corte viene del descriptor", "Domingo" in mod.corte_entrega(datos))

comprobar("el plan tiene 43 archivos", len(plan) == 43, str(len(plan)))
for esperada in ("README.md", ".gitignore", "semana_01/README.md",
                 "semana_01/datos/.gitkeep", "semana_01/analisis/.gitkeep",
                 "semana_01/figuras/.gitkeep", "semana_10/portafolio/.gitkeep"):
    comprobar(f"el plan incluye {esperada}", esperada in plan)

comprobar("no se versiona un informe.pdf vacío",
          not any(ruta.endswith("informe.pdf") for ruta in plan))

raiz_readme = plan["README.md"]
comprobar("README raíz lista las 10 semanas",
          all(f"semana_{n:02d}" in raiz_readme for n in range(1, 11)))
comprobar("README raíz trae los roles",
          all(rol in raiz_readme for rol in ("Medición", "Análisis", "Documentación", "Verificación")))
comprobar("README raíz usa marcadores, no nombres reales",
          "[Nombre del integrante 1]" in raiz_readme and "V-" not in raiz_readme)
comprobar("README raíz trae el corte", "Domingo" in raiz_readme)
comprobar("README raíz explica la privacidad", "privado" in raiz_readme.lower())

semanal1 = plan["semana_01/README.md"]
comprobar("README semanal 1 empieza por el título exacto de la práctica",
          semanal1.splitlines()[0] ==
          "# Práctica 01 — MANEJO DEL INSTRUMENTAL ELÉCTRICO Y DETERMINACIÓN DE LA CARACTERÍSTICA CORRIENTE-VOLTAJE (I-V) DE ALGUNOS DISPOSITIVOS",
          semanal1.splitlines()[0])
comprobar("README semanal 1 traza las cifras", "Trazabilidad de cifras" in semanal1)
semanal10 = plan["semana_10/README.md"]
comprobar("README semanal 10 pide informe individual y portafolio",
          "`informe.pdf` individual" in semanal10 and "`portafolio/`" in semanal10)

gitignore = plan[".gitignore"]
comprobar(".gitignore ignora .env", ".env" in gitignore)
comprobar(".gitignore NO ignora informe.pdf",
          not any(line.strip().startswith(("informe.pdf", "*.pdf"))
                  for line in gitignore.splitlines()))

comprobar("el plan es determinista (mismo descriptor, mismos bytes)",
          plan == mod.plan_de_archivos(mod.cargar_descriptor(CURSO)))
comprobar("la plantilla no lleva fecha de generación",
          not any("2026-" in contenido for contenido in plan.values()))

# Pruebas de escritura en un directorio temporal.
with tempfile.TemporaryDirectory() as temporal:
    salida = Path(temporal) / "repo_grupo"
    comprobar("verificar_plan detecta salida ausente", bool(mod.verificar_plan(plan, salida)))
    mod.escribir_plan(plan, salida)
    comprobar("escribir_plan deja 43 archivos verificables",
              mod.verificar_plan(plan, salida) == [])
    comprobar("la salida tiene 10 carpetas de semana",
              len([p for p in salida.iterdir() if p.is_dir() and p.name.startswith("semana_")]) == 10)

    intento_fallo = False
    try:
        mod.escribir_plan(plan, salida)
    except ValueError:
        intento_fallo = True
    comprobar("sin --forzar rechaza sobrescribir", intento_fallo)

    propio = salida / "semana_01/datos/lecturas_mias.csv"
    propio.write_text("V,I\n1,0.01\n", encoding="utf-8")
    mod.escribir_plan(plan, salida, forzar=True)
    comprobar("--forzar NO borra archivos del grupo", propio.exists() and propio.read_text().startswith("V,I"))
    comprobar("--forzar deja la plantilla intacta", mod.verificar_plan(plan, salida) == [])

# Fallos de validación del descriptor.
for nombre, descriptor in (
    ("sin semanas", {}),
    ("semanas incompletas", {"semanas": [{"numero": n, "practica": {"titulo": f"P{n}"}}
                                          for n in range(1, 10)]}),
    ("sin roles", {"semanas": [{"numero": n, "practica": {"titulo": f"P{n}"}}
                               for n in range(1, 11)]}),
):
    fallo = False
    try:
        mod.plan_de_archivos(descriptor)
    except ValueError:
        fallo = True
    comprobar(f"rechaza descriptor {nombre}", fallo)

# CLI: --check no escribe y la corrida real respeta códigos de salida.
with tempfile.TemporaryDirectory() as temporal:
    salida = Path(temporal) / "check"
    ejecucion = subprocess.run(
        [sys.executable, str(SCRIPT), "--curso", str(CURSO), "--salida", str(salida),
         "--check", "--json"],
        capture_output=True, text=True, encoding="utf-8",
    )
    datos_json = json.loads(ejecucion.stdout)
    comprobar("--check sale 0 y no escribe",
              ejecucion.returncode == 0 and not salida.exists() and datos_json["check"] is True)
    comprobar("--check informa 43 archivos", datos_json["archivos"] == 43)

    ejecucion = subprocess.run(
        [sys.executable, str(SCRIPT), "--curso", str(CURSO), "--salida", str(salida), "--json"],
        capture_output=True, text=True, encoding="utf-8",
    )
    comprobar("la corrida real sale 0", ejecucion.returncode == 0)
    comprobar("la corrida real escribe 43 archivos",
              len([p for p in salida.rglob("*") if p.is_file()]) == 43)

    ejecucion = subprocess.run(
        [sys.executable, str(SCRIPT), "--curso", str(CURSO), "--salida", str(salida), "--json"],
        capture_output=True, text=True, encoding="utf-8",
    )
    comprobar("repetir sin --forzar sale 3", ejecucion.returncode == 3)

# --- Laboratorio I: misma plantilla, descriptor y títulos distintos ----------
CURSO_LAB1 = RAIZ / "cursos/LABORATORIO_I_FISICA/curso.yaml"
datos_lab1 = mod.cargar_descriptor(CURSO_LAB1)
titulos_lab1 = mod.titulos_practicas(datos_lab1)
plan_lab1 = mod.plan_de_archivos(datos_lab1)

comprobar("Lab I tiene 10 semanas", len(titulos_lab1) == 10)
comprobar("Lab I toma el nombre de meta.titulo",
          mod.nombre_curso(datos_lab1) == "Laboratorio I de Física")
comprobar("Lab II toma el nombre de meta.titulo",
          mod.nombre_curso(datos) == "Laboratorio II de Física")
comprobar("README raíz de Lab II no cambió de encabezado",
          raiz_readme.startswith("# Laboratorio II de Física — Repositorio del grupo"))
comprobar("README raíz de Lab I usa su nombre",
          plan_lab1["README.md"].startswith("# Laboratorio I de Física — Repositorio del grupo"))
comprobar("Lab I: semanas 1..4 son talleres",
          all(titulos_lab1[n].startswith(f"Taller {n:02d} —") for n in range(1, 5)),
          str([titulos_lab1[n] for n in range(1, 5)]))
comprobar("Lab I: semanas 5..10 son prácticas",
          all(titulos_lab1[n].startswith(f"Práctica {n:02d} —") for n in range(5, 11)),
          str([titulos_lab1[n] for n in range(5, 11)]))
comprobar("README semanal 1 de Lab I empieza por su título oficial",
          plan_lab1["semana_01/README.md"].splitlines()[0] == f"# {titulos_lab1[1]}")
comprobar("README de taller cita taller_NN.tex",
          "Los títulos de los talleres se toman de" in plan_lab1["semana_01/README.md"] and
          "`practicas/taller_NN.tex`" in plan_lab1["semana_01/README.md"])
comprobar("README de práctica cita practica_NN.tex",
          "Los títulos de las prácticas se toman de" in plan_lab1["semana_05/README.md"] and
          "`practicas/practica_NN.tex`" in plan_lab1["semana_05/README.md"])
comprobar("el plan de Lab I es determinista",
          plan_lab1 == mod.plan_de_archivos(mod.cargar_descriptor(CURSO_LAB1)))
comprobar("el plan de Lab I tiene 43 archivos", len(plan_lab1) == 43)
comprobar("los planes de Lab I y Lab II no son idénticos", plan_lab1 != plan)

print("=" * 60)
print(f"{PRUEBAS - len(FALLOS)}/{PRUEBAS} aserciones OK")
if FALLOS:
    print("Fallos:")
    for fallo in FALLOS:
        print(f"  - {fallo}")
    sys.exit(1)
print("Sin fallos.")
