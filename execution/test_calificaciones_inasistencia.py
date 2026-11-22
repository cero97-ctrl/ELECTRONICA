#!/usr/bin/env python3
"""Pruebas del descriptor de calificaciones por inasistencia (capa 3).

Sin red, sin pdflatex y sin tocar el repo real. Congela las barreras que impiden
que un cero por ausencia se cuele en el acta como si fuera una entrega: cédula ya
entregada, cédula ajena a la nómina, grupo divergente, total distinto y nota
fuera de 0..10.

Ejecutar: python3 execution/test_calificaciones_inasistencia.py
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FALLOS: list[str] = []
PRUEBAS = 0

BASE = """fecha_decision: 2026-11-22
total_preguntas: 10
motivo: "Sin entrega; no justificó su ausencia"
referencia: Sessions/2026-11-22_prueba.md
calificaciones:
  - {cedula: V-90000001, nombre: AUSENTE-1, grupo: 4, nota: 0.0}
"""


def comprobar(nombre: str, condicion: bool, detalle: str = "") -> None:
    global PRUEBAS
    PRUEBAS += 1
    if condicion:
        print(f"  ok   {nombre}")
    else:
        print(f"  FALLA {nombre}" + (f" -- {detalle}" if detalle else ""))
        FALLOS.append(nombre)


def _cargar():
    spec = importlib.util.spec_from_file_location(
        "calificaciones_inasistencia_bajo_test",
        RAIZ / "execution/calificaciones_inasistencia.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["calificaciones_inasistencia_bajo_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def _rechaza(fn, nombre: str, fragmento: str = "") -> None:
    try:
        fn()
    except ValueError as exc:
        comprobar(nombre, not fragmento or fragmento in str(exc), str(exc))
    else:
        comprobar(nombre, False, "no lanzó ValueError")


def main() -> int:
    mod = _cargar()

    with tempfile.TemporaryDirectory() as temporal:
        tmp = Path(temporal)
        ruta = tmp / "calificaciones.yaml"
        ruta.write_text(BASE, encoding="utf-8")

        print("leer_descriptor")
        desc = mod.leer_descriptor(ruta)
        comprobar("lee la fecha ISO", desc["fecha_decision"] == "2026-11-22")
        comprobar("normaliza la cédula", desc["calificaciones"][0]["cedula"] == "V-90000001")
        comprobar("total y motivo", (desc["total_preguntas"], desc["motivo"][:11]) == (10, "Sin entrega"))
        comprobar("referencia", desc["referencia"] == "Sessions/2026-11-22_prueba.md")

        _rechaza(lambda: mod.leer_descriptor(tmp / "no-existe.yaml"),
                 "archivo inexistente se rechaza")
        malos = {
            "YAML roto": "calificaciones: [",
            "clave desconocida": BASE + "inventada: 1\n",
            "sin motivo": BASE.replace('motivo: "Sin entrega; no justificó su ausencia"\n', ""),
            "fecha no ISO": BASE.replace("2026-11-22", "22-11-2026", 1),
            "total cero": BASE.replace("total_preguntas: 10", "total_preguntas: 0"),
            "motivo vacío": BASE.replace('motivo: "Sin entrega; no justificó su ausencia"', 'motivo: ""'),
            "lista vacía": BASE.split("calificaciones:")[0] + "calificaciones: []\n",
            "cédula inválida": BASE.replace("V-90000001", "no-es-cedula"),
            "nota fuera de rango": BASE.replace("nota: 0.0", "nota: 11.0"),
            "grupo inválido": BASE.replace("grupo: 4", "grupo: 0"),
            "nombre vacío": BASE.replace("nombre: AUSENTE-1", 'nombre: ""'),
        }
        for nombre, contenido in malos.items():
            ruta_mala = tmp / f"malo_{len(FALLOS)}.yaml"
            ruta_mala.write_text(contenido, encoding="utf-8")
            _rechaza(lambda p=ruta_mala: mod.leer_descriptor(p), f"{nombre} se rechaza")

        dos = tmp / "repetida.yaml"
        dos.write_text(BASE + "  - {cedula: V-90000001, nombre: OTRA VEZ, grupo: 4, nota: 0.0}\n",
                       encoding="utf-8")
        _rechaza(lambda: mod.leer_descriptor(dos), "cédula repetida en el descriptor se rechaza",
                 "repetida")

        print("filas_para")
        entregas = [{
            "grupo": 1, "cedula": "V-11111111", "nombre": "ANA", "aciertos": 10,
            "total": 10, "nota_recalculada": 10.0, "enviado_en": "2026-11-16T15:00:00Z",
            "estado": "ok", "justif_estado": "ok", "avisos": "",
        }]
        ausentes = [{"cedula": "V-90000001", "nombre": "AUSENTE-1", "grupo": 4}]
        filas = mod.filas_para(entregas, ausentes, desc)
        comprobar("una fila por calificación", len(filas) == 1)
        comprobar("estado sin_entrega", filas[0]["estado"] == "sin_entrega")
        comprobar("cero sobre el total", (filas[0]["aciertos"], filas[0]["total"],
                                          filas[0]["nota_recalculada"]) == (0, 10, 0.0))
        comprobar("sin fecha de envío", filas[0]["enviado_en"] == "")
        comprobar("motivo y referencia en el aviso",
                  "Sin entrega" in filas[0]["avisos"]
                  and "Sessions/2026-11-22_prueba.md" in filas[0]["avisos"])
        comprobar("justificación no aplica", filas[0]["justif_estado"] == "n/a")

        _rechaza(lambda: mod.filas_para(
            [dict(entregas[0], cedula="V-90000001")], ausentes, desc),
            "cédula ya entregada se rechaza", "ya entregó")
        _rechaza(lambda: mod.filas_para(entregas, [], desc),
                 "cédula ajena a la nómina se rechaza", "no figura")
        _rechaza(lambda: mod.filas_para(
            entregas, [{"cedula": "V-90000001", "nombre": "X", "grupo": 3}], desc),
            "grupo divergente se rechaza", "grupo")
        _rechaza(lambda: mod.filas_para([dict(entregas[0], total=8)], ausentes, desc),
                 "total distinto al de las actas se rechaza", "no coincide")

        print("incorporar")
        finales, meta = mod.incorporar(entregas, ausentes, ruta)
        comprobar("uno + uno = dos filas", len(finales) == 2)
        comprobar("orden por (grupo, cédula)", [r["grupo"] for r in finales] == [1, 4])
        comprobar("metadata de la decisión", meta["calificados"] == filas)
        comprobar("determinista", mod.incorporar(entregas, ausentes, ruta)[0] == finales)

    print()
    if FALLOS:
        print(f"{len(FALLOS)} FALLOS de {PRUEBAS} aserciones")
        for fallo in FALLOS:
            print(f"  - {fallo}")
        return 1
    print(f"{PRUEBAS}/{PRUEBAS} aserciones OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
