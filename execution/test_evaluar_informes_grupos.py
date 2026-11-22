#!/usr/bin/env python3
"""Pruebas PURAS del evaluador de informes: sin red, sin API y sin compilación."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "execution"))

import evaluar_informes_grupos as eig  # noqa: E402

SHA = "a" * 40


def descriptor_yaml(**cambios: str) -> str:
    base = {
        "version": 1, "curso": "CIBERSEGURIDAD", "semana": 1,
        "rubrica": "rubrica.yaml", "grupos_esperados": "[1, 2]",
        "backend": "gemini", "modelo": "gemini-2.5-flash",
        "grupos": "[{grupo: 1, rol: Rojo, repo: a/b, commit: " + SHA +
                  ", informe: semana_01/informe.md}]",
    }
    base.update(cambios)
    return "\n".join(f"{k}: {v}" for k, v in base.items()) + "\n"


class TestDescriptor(unittest.TestCase):
    def test_default_evaluar_corte_es_true(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "d.yaml"
            p.write_text(descriptor_yaml(), encoding="utf-8")
            self.assertTrue(eig.cargar_descriptor(p)["evaluar_corte"])

    def test_excepcion_de_la_semana_01_se_respeta(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "d.yaml"
            p.write_text(descriptor_yaml(evaluar_corte="false"), encoding="utf-8")
            self.assertFalse(eig.cargar_descriptor(p)["evaluar_corte"])

    def test_backend_distinto_de_gemini_se_rechaza(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "d.yaml"
            p.write_text(descriptor_yaml(backend="openrouter"), encoding="utf-8")
            with self.assertRaises(ValueError):
                eig.cargar_descriptor(p)

    def test_commit_debe_ser_sha_completo(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "d.yaml"
            texto = descriptor_yaml(grupos=(
                "[{grupo: 1, rol: Rojo, repo: a/b, commit: abc, informe: x.md}]"
            ))
            p.write_text(texto, encoding="utf-8")
            with self.assertRaises(ValueError):
                eig.cargar_descriptor(p)

    def test_cobertura_exacta(self):
        desc = {"grupos_esperados": [1, 2], "grupos": [
            {"grupo": 2, "repo": "b"}, {"grupo": 1, "repo": "a"}]}
        self.assertEqual([g["grupo"] for g in eig.validar_cobertura(desc)], [1, 2])
        with self.assertRaises(ValueError):
            eig.validar_cobertura({**desc, "grupos": desc["grupos"][:1]})

    def test_grupos_repetidos_se_rechazan(self):
        desc = {"grupos_esperados": [1, 2], "grupos": [
            {"grupo": 1, "repo": "a"}, {"grupo": 1, "repo": "b"}]}
        with self.assertRaises(ValueError):
            eig.validar_cobertura(desc)


class TestInforme(unittest.TestCase):
    def test_resuelve_informe_con_mayuscula(self):
        rutas = ["semana_01/README.md", "semana_01/Informe.md"]
        self.assertEqual(
            eig.resolver_informe(rutas, "semana_01/informe.md"),
            "semana_01/Informe.md",
        )

    def test_ambiguedad_no_se_resuelve_a_ciegas(self):
        rutas = ["semana_01/informe.md", "semana_01/INFORME.md"]
        self.assertIsNone(eig.resolver_informe(rutas, "semana_01/Informe.md"))

    def test_rutas_citadas_y_resolucion_en_evidencia(self):
        texto = "Salida en `semana_01/evidencia/nmap.txt` y `juice_headers.txt`."
        citadas = eig.extraer_rutas_citadas(texto)
        self.assertIn("semana_01/evidencia/nmap.txt", citadas)
        self.assertIn("juice_headers.txt", citadas)
        rutas = {"semana_01/evidencia/nmap.txt", "semana_01/juice_headers.txt"}
        self.assertEqual(
            eig.resolver_ruta_citada("juice_headers.txt", rutas),
            "semana_01/juice_headers.txt",
        )
        self.assertIsNone(eig.resolver_ruta_citada("no_existe.txt", rutas))

    def test_rol_rojo_no_se_recorta_a_roj(self):
        # Regresión: rstrip("yreporte") convertía "rojo" en "roj".
        check, _ = eig.chequear_grupo(
            {"grupo": 1, "rol": "Rojo", "informe": "semana_01/informe.md"},
            {"semana_01/informe.md": "Rol Rojo: escanéo el laboratorio.".encode()},
            False, "2026-11-08T23:59:00-04:00",
        )
        self.assertTrue(check["rol_declarado_en_informe"])


class TestEvidencia(unittest.TestCase):
    def test_parseo_y_verificacion_de_hashes(self):
        datos = b"salida cruda\n"
        sha = hashlib.sha256(datos).hexdigest()
        archivos = {
            "semana_01/evidencia/nmap.txt": datos,
            "semana_01/evidencia/hashes.sha256":
                f"{sha}  nmap.txt\n{'0' * 64}  faltante.txt\n".encode(),
        }
        pares = eig.parsear_hashes(archivos["semana_01/evidencia/hashes.sha256"].decode())
        self.assertEqual(len(pares), 2)
        res = eig.verificar_hashes(archivos)
        self.assertEqual(res["declarados"], 2)
        self.assertEqual(res["verificados"], ["semana_01/evidencia/nmap.txt"])
        self.assertEqual(res["fallidos"], [])
        self.assertEqual(res["sin_archivo"], ["faltante.txt"])

    def test_hash_que_no_cuadra_se_reporta(self):
        datos = b"original"
        archivos = {
            "semana_01/evidencia/a.txt": datos,
            "semana_01/evidencia/hashes.sha256":
                f"{'1' * 64}  a.txt\n".encode(),
        }
        self.assertEqual(
            eig.verificar_hashes(archivos)["fallidos"],
            ["semana_01/evidencia/a.txt"],
        )

    def test_secretos_se_reportan_por_ruta(self):
        archivos = {
            "semana_01/evidencia/log.txt": b"token ghp_" + b"A" * 40 + b"\n",
            ".env": b"GOOGLE_API_KEY=x",
        }
        hallazgos = eig.detectar_secretos(archivos)
        self.assertIn(".env", hallazgos)
        self.assertIn("semana_01/evidencia/log.txt", hallazgos)
        self.assertFalse(any("ghp_" in h for h in hallazgos))  # nunca el valor

    def test_puntualidad_no_evaluada(self):
        r = eig.evaluar_puntualidad("2026-11-15T22:00:00-04:00",
                                    "2026-11-08T23:59:00-04:00", False)
        self.assertEqual(r["estado"], "no_evaluada")
        self.assertEqual(eig.evaluar_puntualidad("2026-11-07T10:00:00-04:00",
                                                 "2026-11-08T23:59:00-04:00",
                                                 True)["estado"], "en_plazo")
        self.assertEqual(eig.evaluar_puntualidad("2026-11-15T22:00:00-04:00",
                                                 "2026-11-08T23:59:00-04:00",
                                                 True)["estado"], "tardia")


class TestModelo(unittest.TestCase):
    PESOS = {"cobertura del alcance": 3.0, "evidencia reproducible": 2.5,
             "causa raiz": 2.0, "analisis": 1.5, "calidad": 1.0}

    def test_descarta_nota_del_modelo_y_normaliza_nombre(self):
        crudo = {
            "items": [
                {"item": "Cobertura del alcance", "puntaje_parcial": "2.4/3.0",
                 "justificacion": "Ejecutó los pasos sobre el objetivo autorizado."},
                {"item": "inventado", "puntaje_parcial": "5/5",
                 "justificacion": "Criterio que no está en la rúbrica."},
            ],
            "puntaje_sugerido": "10/10", "nivel_desempeno": "Excelente",
            "observaciones": "Bien.",
        }
        items, avisos, obs = eig.validar_items(crudo, self.PESOS)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["item"], "cobertura del alcance")
        self.assertTrue(any("puntaje_sugerido" in a for a in avisos))
        self.assertTrue(any("inventado" in a for a in avisos))
        self.assertEqual(obs, "Bien.")

    def test_anonimiza_cedulas_en_justificaciones(self):
        crudo = {"items": [{
            "item": "calidad", "puntaje_parcial": "1/1",
            "justificacion": "El alumno V-90000001 anonimizó sus evidencias.",
        }]}
        items, _, _ = eig.validar_items(crudo, self.PESOS)
        self.assertNotIn("90000001", items[0]["justificacion"])
        self.assertIn("[IDENTIFICADOR]", items[0]["justificacion"])

    def test_nota_la_calcula_el_programa_con_los_pesos_de_la_rubrica(self):
        items = [
            {"item": "cobertura del alcance", "puntaje_parcial": "2.4/3.0"},
            {"item": "evidencia reproducible", "puntaje_parcial": "2.0/2.5"},
            {"item": "causa raiz", "puntaje_parcial": "1.6/2.0"},
            {"item": "analisis", "puntaje_parcial": "1.2/1.5"},
            {"item": "calidad", "puntaje_parcial": "0.8/1.0"},
        ]
        datos, avisos = eig.calcular_nota(items, pesos=self.PESOS)
        self.assertTrue(datos["nota_fiable"])
        self.assertEqual(datos["puntaje_numerico"], 8.0)
        self.assertEqual(avisos, [])
        self.assertEqual(datos["items_ausentes"], [])

    def test_criterio_ausente_vale_cero_y_se_avisa(self):
        datos, avisos = eig.calcular_nota([
            {"item": "calidad", "puntaje_parcial": "1/1.0"}
        ], pesos=self.PESOS)
        self.assertEqual(datos["puntaje_numerico"], 1.0)
        self.assertTrue(any("no devolvió 4" in a for a in avisos))

    def test_system_instruction_no_pide_nota(self):
        system = eig.armar_system_instruction(self.PESOS, "Rúbrica de prueba")
        self.assertIn("2.5", system)
        self.assertIn("No emitas nota total", system)
        self.assertIn("puntaje_parcial", system)


class TestActa(unittest.TestCase):
    def test_descriptor_desde_json_es_puro_y_valida(self):
        datos = {"semana": 3, "rubrica": "r.yaml", "grupos": [{"grupo": 1}]}
        esperado = {"semana": 3, "rubrica": "r.yaml"}
        self.assertEqual(eig.descriptor_desde_resultado(datos), esperado)
        self.assertEqual(eig.descriptor_desde_resultado(datos), esperado)
        with self.assertRaises(ValueError):
            eig.descriptor_desde_resultado({"rubrica": "r.yaml"})
        with self.assertRaises(ValueError):
            eig.descriptor_desde_resultado({"semana": 1})

    def test_regenerar_desde_json_no_llama_al_modelo(self):
        # Regresión: las copias finales son gitignored y pueden desaparecer;
        # recuperarlas no debe repetir las 4 llamadas a Gemini.
        with tempfile.TemporaryDirectory() as d:
            datos = {
                "semana": 1, "rubrica": "rubrica.yaml",
                "grupos": [{"grupo": g, "rol": "Rojo", "avisos": [],
                            "nota": {"nota_fiable": True, "puntaje_numerico": 8.0}}
                           for g in (1, 2, 3, 4)],
            }
            ruta_json = Path(d) / "evaluacion.json"
            ruta_json.write_text(json.dumps(datos), encoding="utf-8")
            ruta_tex = Path(d) / "acta.tex"
            desc = eig.descriptor_desde_resultado(datos)
            eig.generar_acta_tex(datos["grupos"], desc, ruta_tex)
            texto = ruta_tex.read_text(encoding="utf-8")
            self.assertIn("Promedio de los 4 grupos: 8.00/10.", texto)

    def test_acta_escapea_porcentaje_y_anonymous(self):
        resultados = [{
            "grupo": 1, "rol": "Rojo", "avisos": ["Desvío 50% sin evidencia"],
            "nota": {"nota_fiable": True, "puntaje_numerico": 8.0},
        }, {
            "grupo": 2, "rol": "Azul", "avisos": [],
            "nota": {"nota_fiable": True, "puntaje_numerico": 7.5},
        }, {
            "grupo": 3, "rol": "Púrpura", "avisos": [],
            "nota": {"nota_fiable": True, "puntaje_numerico": 9.0},
        }, {
            "grupo": 4, "rol": "Legal y reporte", "avisos": [],
            "nota": {"nota_fiable": True, "puntaje_numerico": 6.0},
        }]
        with tempfile.TemporaryDirectory() as d:
            ruta = eig.generar_acta_tex(
                resultados, {"semana": 1, "rubrica": "rubrica.yaml"}, Path(d) / "acta.tex"
            )
            texto = ruta.read_text(encoding="utf-8")
            self.assertIn(r"50\%", texto)
            self.assertIn("Promedio de los 4 grupos: 7.62/10.", texto)
            self.assertIn(r"\begin{document}", texto)
            self.assertNotIn("50% sin evidencia", texto)


if __name__ == "__main__":
    unittest.main(verbosity=2)
