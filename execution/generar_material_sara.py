#!/usr/bin/env python3
r"""generar_material_sara.py — Genera el sitio de estudio de Sara (Layer 3).

Contrato:
  - Entrada: una carpeta con lecciones en YAML (por defecto
    `SARA/contenido/`). Cada archivo describe un tema con objetivo, idea
    clave, pasos, ejemplo resuelto, esquema, práctica y recordatorio.
  - Salida: HTML autocontenido y offline (CSS y JS inline, sin CDN, sin
    imágenes externas) en `SARA/`: portada, una página por materia y una
    página por tema.
  - Determinismo: el mismo contenido produce exactamente los mismos bytes.
    No hay timestamps, aleatoriedad ni orden dependiente del sistema de
    ficheros (todo se ordena por materia y por `orden`).
  - Validación: un tema mal escrito falla antes de escribir con código 3 y
    la lista de problemas. Nunca se publica contenido a medias.
  - Barrera: solo escribe dentro de `SARA/` y solo archivos `.html`.

Diseño pensado para lectura sin sobrecarga:
  - Una idea por sección, siempre en el mismo orden.
  - Lenguaje literal, frases cortas, sin metáforas ni tiempos límite.
  - Sin animaciones, sin sonidos, sin puntajes que generen presión.
  - Botones grandes, foco visible, contraste ajustable y texto ampliable.

Uso:
    python3 execution/generar_material_sara.py --check
    python3 execution/generar_material_sara.py --dry-run --json
    python3 execution/generar_material_sara.py

Códigos de salida:
    0 -> ok o contenido válido en --check/--dry-run
    1 -> error de entrada/salida
    3 -> contenido inválido (campo faltante, opción fuera de rango, etc.)
    5 -> ruta de salida fuera de SARA/
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import unicodedata
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SARA_DIR = PROJECT_ROOT / "SARA"
CONTENIDO_POR_DEFECTO = SARA_DIR / "contenido"

MATERIAS = {
    "matematicas": {
        "nombre": "Matemáticas",
        "letra": "M",
        "descripcion": "Funciones, ecuaciones y sistemas.",
    },
    "fisica": {
        "nombre": "Física",
        "letra": "F",
        "descripcion": "Movimiento, fuerzas y circuitos.",
    },
    "quimica": {
        "nombre": "Química",
        "letra": "Q",
        "descripcion": "Átomo, enlaces y cantidad de sustancia.",
    },
}

TIPOS_ESQUEMA = ("tabla", "flujo", "lista")
MAX_OPCIONES = 6
MIN_OPCIONES = 2

CSS = r"""
:root {
  --fondo: #fbfaf7;
  --texto: #1e2a33;
  --suave: #4a5a66;
  --linea: #d5dde3;
  --papel: #ffffff;
  --materia: #2f4a5f;
  --tinte: #eef2f5;
  --base: 18px;
  --radio: 14px;
  --ancho: 920px;
}
html { -webkit-text-size-adjust: 100%; }
html[data-texto="p"] { --base: 16px; }
html[data-texto="g"] { --base: 21px; }
html[data-texto="xg"] { --base: 24px; }
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--fondo);
  color: var(--texto);
  font-family: "Atkinson Hyperlegible", "Source Sans Pro", "Segoe UI", system-ui, -apple-system, sans-serif;
  font-size: var(--base);
  line-height: 1.65;
}
.matematicas { --materia: #2f6f8f; --tinte: #e9f2f6; }
.fisica { --materia: #6b4fa3; --tinte: #efeaf7; }
.quimica { --materia: #2f7d5d; --tinte: #e7f3ed; }
a { color: #1b5f86; }
a:focus-visible, button:focus-visible, label:focus-within {
  outline: 3px solid #17557a;
  outline-offset: 2px;
}
.saltar {
  position: absolute;
  left: -999px;
  top: 0;
  background: #ffffff;
  color: #000000;
  padding: .7rem 1rem;
  z-index: 20;
  border-radius: 0 0 8px 0;
}
.saltar:focus { left: 0; }
.contenedor {
  max-width: var(--ancho);
  margin: 0 auto;
  padding: 0 1.1rem;
}
.barra {
  background: #22313f;
  color: #ffffff;
  padding: .7rem 0 0;
}
.barra-fila {
  display: flex;
  flex-wrap: wrap;
  gap: .8rem;
  align-items: center;
  justify-content: space-between;
}
.marca {
  color: #ffffff;
  text-decoration: none;
  display: inline-flex;
  align-items: baseline;
  gap: .55rem;
}
.marca-sara {
  font-size: 1.35rem;
  font-weight: 800;
  letter-spacing: .06em;
}
.marca-sub {
  font-size: .82rem;
  color: #c9d8e4;
}
.ajustes { display: flex; gap: .4rem; }
.ajuste {
  min-width: 46px;
  min-height: 44px;
  padding: .35rem .65rem;
  border: 1px solid #8fa6b8;
  border-radius: 9px;
  background: transparent;
  color: #ffffff;
  font: inherit;
  font-size: .95rem;
  cursor: pointer;
}
.ajuste:hover { background: #33495c; }
.ajuste[aria-pressed="true"] {
  background: #ffffff;
  color: #22313f;
  border-color: #ffffff;
}
.migas {
  padding-top: .55rem;
  padding-bottom: .65rem;
  font-size: .9rem;
  color: #c9d8e4;
  display: flex;
  flex-wrap: wrap;
  gap: .35rem;
}
.migas a { color: #ffffff; }
.migas .sep { color: #8fa6b8; }
.portada {
  background: var(--tinte);
  border-bottom: 1px solid var(--linea);
  padding: 2.2rem 0 1.9rem;
}
.portada h1 { margin: .15rem 0 .5rem; }
.etiqueta {
  margin: 0;
  color: var(--materia);
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
  font-size: .78rem;
}
h1, h2, h3 { line-height: 1.25; }
h1 {
  font-size: clamp(1.7rem, 4.2vw, 2.5rem);
  font-weight: 800;
  margin: .2rem 0 .6rem;
}
h2 {
  font-size: 1.28rem;
  margin: 0 0 .8rem;
  padding-bottom: .35rem;
  border-bottom: 2px solid var(--linea);
}
h2::before {
  content: "";
  display: inline-block;
  width: .55rem;
  height: 1.05em;
  background: var(--materia);
  border-radius: 3px;
  margin-right: .55rem;
  vertical-align: -.14em;
}
h3 { font-size: 1.06rem; margin: .2rem 0 .7rem; }
p { margin: .55rem 0; }
.entrada {
  font-size: 1.08rem;
  max-width: 62ch;
  color: var(--suave);
  margin: 0;
}
.seccion { margin: 2.1rem 0; }
.objetivo {
  background: var(--tinte);
  border-radius: var(--radio);
  padding: .9rem 1.1rem;
  margin: 0;
  font-weight: 600;
}
.idea {
  background: #fff7d6;
  border-left: 6px solid #c79a1e;
  border-radius: 0 var(--radio) var(--radio) 0;
  padding: 1rem 1.15rem;
  margin: 0;
  font-size: 1.06em;
  font-weight: 600;
}
ol.pasos {
  counter-reset: paso;
  list-style: none;
  padding: 0;
  margin: 0;
}
ol.pasos li {
  counter-increment: paso;
  position: relative;
  padding: .5rem 0 .5rem 2.7rem;
}
ol.pasos li::before {
  content: counter(paso);
  position: absolute;
  left: 0;
  top: .45rem;
  width: 1.85rem;
  height: 1.85rem;
  border-radius: 50%;
  background: var(--materia);
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: .95rem;
}
.ejemplo {
  background: var(--papel);
  border: 1px solid var(--linea);
  border-radius: var(--radio);
  padding: 1rem 1.2rem;
}
.ejemplo ol { margin: .2rem 0 .8rem; padding-left: 1.3rem; }
.ejemplo li { margin: .3rem 0; }
.resultado {
  margin: .9rem 0 0;
  background: var(--tinte);
  border-radius: 9px;
  padding: .75rem .9rem;
  font-weight: 700;
}
.flujo { list-style: none; padding: 0; margin: 0; }
.flujo li {
  background: var(--papel);
  border: 2px solid var(--materia);
  border-radius: 10px;
  padding: .65rem .9rem;
  text-align: center;
  font-weight: 600;
}
.flujo .flecha {
  border: 0;
  background: none;
  padding: .15rem 0;
  color: var(--materia);
  font-size: 1.3rem;
  line-height: 1;
  font-weight: 700;
}
.tabla-caja { overflow-x: auto; }
table {
  width: 100%;
  border-collapse: collapse;
  background: var(--papel);
  border: 1px solid var(--linea);
  border-radius: 10px;
}
caption {
  text-align: left;
  font-weight: 700;
  padding: 0 0 .5rem;
}
th, td {
  padding: .6rem .7rem;
  border-bottom: 1px solid var(--linea);
  text-align: left;
  vertical-align: top;
}
th {
  background: var(--materia);
  color: #ffffff;
  font-size: .96rem;
}
tbody tr:last-child td { border-bottom: 0; }
tbody tr:nth-child(even) { background: var(--tinte); }
ul.lista-esquema { list-style: none; padding: 0; margin: 0; display: grid; gap: .6rem; }
ul.lista-esquema li {
  background: var(--papel);
  border-left: 5px solid var(--materia);
  border-radius: 0 9px 9px 0;
  padding: .6rem .9rem;
}
ul.recordar { margin: 0; padding-left: 1.2rem; }
ul.recordar li { margin: .35rem 0; }
ul.recordar li::marker { color: var(--materia); }
.titulo-esquema {
  margin: 0 0 .6rem;
  font-weight: 700;
  color: var(--materia);
}
.ayuda { color: var(--suave); margin-top: -.2rem; }
.ejercicio {
  background: var(--papel);
  border: 1px solid var(--linea);
  border-radius: var(--radio);
  padding: 1rem 1.1rem;
  margin: 1rem 0;
}
.ejercicio legend {
  font-weight: 700;
  padding: 0 .4rem;
}
.opciones { display: grid; gap: .5rem; margin: .75rem 0; }
.opciones label {
  display: flex;
  gap: .7rem;
  align-items: flex-start;
  padding: .6rem .75rem;
  min-height: 44px;
  border: 1px solid var(--linea);
  border-radius: 9px;
  cursor: pointer;
}
.opciones label:hover { border-color: var(--materia); }
.opciones input {
  width: 1.15rem;
  height: 1.15rem;
  margin: .15rem 0 0;
  accent-color: var(--materia);
}
.opciones label:has(input:checked) {
  border-color: var(--materia);
  background: var(--tinte);
}
.comprobar, .boton {
  display: inline-block;
  min-height: 44px;
  padding: .65rem 1.15rem;
  border: 0;
  border-radius: 10px;
  background: var(--materia);
  color: #ffffff;
  font: inherit;
  font-weight: 700;
  text-decoration: none;
  cursor: pointer;
}
.comprobar:hover, .boton:hover { filter: brightness(1.12); }
.boton-suave {
  background: transparent;
  color: var(--materia);
  border: 2px solid var(--materia);
}
.feedback {
  margin: .8rem 0 0;
  padding: .75rem .95rem;
  border-radius: 9px;
  font-weight: 600;
}
.feedback:empty { display: none; }
.feedback.bien {
  background: #e6f4ea;
  color: #14532d;
  border: 1px solid #9ed3ae;
}
.feedback.intenta {
  background: #fff4dc;
  color: #6b4a00;
  border: 1px solid #e7c26a;
}
.feedback.aviso {
  background: var(--tinte);
  color: var(--texto);
  border: 1px solid var(--linea);
}
.nota {
  background: #fff1f0;
  border: 1px solid #e8b4ae;
  border-left: 6px solid #b5534a;
  border-radius: 0 var(--radio) var(--radio) 0;
  padding: .9rem 1.05rem;
}
.calma {
  background: #eef6f1;
  border: 1px solid #b9d8c6;
  border-left: 6px solid #2f7d5d;
  border-radius: 0 var(--radio) var(--radio) 0;
  padding: .9rem 1.05rem;
}
.nota h2 { border-bottom: 0; font-size: 1.1rem; }
.nota h2::before { background: #b5534a; }
.rejilla {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(235px, 1fr));
  gap: 1rem;
}
.tarjeta {
  display: flex;
  flex-direction: column;
  gap: .3rem;
  background: var(--papel);
  border: 1px solid var(--linea);
  border-top: 6px solid var(--materia);
  border-radius: var(--radio);
  padding: 1.1rem;
  text-decoration: none;
  color: var(--texto);
}
.tarjeta:hover { border-color: var(--materia); }
.tarjeta:focus-visible { outline-offset: 3px; }
.insignia {
  width: 46px;
  height: 46px;
  border-radius: 50%;
  background: var(--materia);
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.25rem;
  font-weight: 800;
  margin-bottom: .3rem;
}
.tarjeta-nombre { font-size: 1.16rem; font-weight: 800; }
.tarjeta-desc { color: var(--suave); font-size: .97rem; }
.tarjeta-meta { margin-top: .35rem; font-size: .86rem; font-weight: 700; color: var(--materia); }
ol.temas { list-style: none; padding: 0; margin: 0; display: grid; gap: .8rem; }
ol.temas a {
  display: block;
  background: var(--papel);
  border: 1px solid var(--linea);
  border-left: 6px solid var(--materia);
  border-radius: 0 var(--radio) var(--radio) 0;
  padding: .9rem 1.05rem;
  text-decoration: none;
  color: var(--texto);
}
ol.temas a:hover { border-color: var(--materia); }
.tema-num {
  display: block;
  font-size: .8rem;
  font-weight: 800;
  letter-spacing: .07em;
  text-transform: uppercase;
  color: var(--materia);
}
.tema-titulo { display: block; font-size: 1.1rem; font-weight: 700; }
.tema-desc { display: block; color: var(--suave); font-size: .96rem; }
.nav-tema {
  display: flex;
  flex-wrap: wrap;
  gap: .7rem;
  justify-content: space-between;
  margin: 2.6rem 0 0;
}
.pie {
  border-top: 1px solid var(--linea);
  margin-top: 3.5rem;
  padding: 1.4rem 0 2rem;
  color: var(--suave);
  font-size: .9rem;
}
.pie p { margin: .2rem 0; }
html[data-contraste="alto"] {
  --fondo: #ffffff;
  --texto: #000000;
  --suave: #111111;
  --linea: #000000;
  --papel: #ffffff;
  --tinte: #ffffff;
}
html[data-contraste="alto"] .barra { background: #000000; }
html[data-contraste="alto"] .matematicas,
html[data-contraste="alto"] .fisica,
html[data-contraste="alto"] .quimica {
  --tinte: #ffffff;
}
html[data-contraste="alto"] .objetivo,
html[data-contraste="alto"] .resultado {
  background: #ffffff;
  border: 1px solid #000000;
}
html[data-contraste="alto"] .flujo li { border-color: #000000; }
html[data-contraste="alto"] .flujo .flecha { color: #000000; }
html[data-contraste="alto"] .idea,
html[data-contraste="alto"] .nota,
html[data-contraste="alto"] .feedback.bien,
html[data-contraste="alto"] .feedback.intenta {
  background: #ffffff;
  color: #000000;
  border-color: #000000;
}
html[data-contraste="alto"] .tarjeta,
html[data-contraste="alto"] .ejemplo,
html[data-contraste="alto"] .ejercicio,
html[data-contraste="alto"] .opciones label,
html[data-contraste="alto"] .calma,
html[data-contraste="alto"] table {
  background: #ffffff;
  border-color: #000000;
}
html[data-contraste="alto"] th { background: #000000; color: #ffffff; }
html[data-contraste="alto"] tbody tr:nth-child(even) { background: #ffffff; }
@media (max-width: 620px) {
  .barra-fila { align-items: flex-start; }
  .marca-sub { display: none; }
  .nav-tema { flex-direction: column; }
  .nav-tema .boton { text-align: center; }
}
@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; scroll-behavior: auto !important; }
}
@media print {
  .barra, .ajustes, .nav-tema, .saltar, .comprobar, .feedback { display: none !important; }
  body { background: #ffffff; font-size: 12pt; }
  .portada { background: #ffffff; border-bottom: 1px solid #000000; }
  .seccion, .ejercicio, .ejemplo { break-inside: avoid; }
  a { color: inherit; text-decoration: none; }
}
"""

JS_BASE = r"""
(function () {
  var raiz = document.documentElement;
  var niveles = ["p", "", "g", "xg"];
  function aplicar(k, v) {
    if (v) { raiz.setAttribute(k, v); } else { raiz.removeAttribute(k); }
  }
  function guardar(k, v) {
    try {
      if (v) { localStorage.setItem(k, v); } else { localStorage.removeItem(k); }
    } catch (e) {}
  }
  function nivelActual() {
    var v = raiz.getAttribute("data-texto") || "";
    var i = niveles.indexOf(v);
    return i < 0 ? 1 : i;
  }
  function pintarContraste() {
    var b = document.querySelector('[data-accion="contraste"]');
    if (b) {
      b.setAttribute("aria-pressed", raiz.getAttribute("data-contraste") === "alto" ? "true" : "false");
    }
  }
  try {
    aplicar("data-texto", localStorage.getItem("sara-texto"));
    aplicar("data-contraste", localStorage.getItem("sara-contraste"));
  } catch (e) {}
  pintarContraste();
  Array.prototype.forEach.call(document.querySelectorAll("[data-accion]"), function (b) {
    b.addEventListener("click", function () {
      var accion = b.getAttribute("data-accion");
      if (accion === "menos" || accion === "mas") {
        var delta = accion === "mas" ? 1 : -1;
        var i = Math.min(niveles.length - 1, Math.max(0, nivelActual() + delta));
        aplicar("data-texto", niveles[i]);
        guardar("sara-texto", niveles[i]);
      } else if (accion === "contraste") {
        var alto = raiz.getAttribute("data-contraste") === "alto";
        aplicar("data-contraste", alto ? "" : "alto");
        guardar("sara-contraste", alto ? "" : "alto");
        pintarContraste();
      }
    });
  });
})();
"""

JS_EJERCICIOS = r"""
(function () {
  Array.prototype.forEach.call(document.querySelectorAll(".ejercicio"), function (ej) {
    var boton = ej.querySelector(".comprobar");
    var salida = ej.querySelector(".feedback");
    var explicacion = ej.querySelector(".explicacion");
    if (!boton || !salida) { return; }
    boton.addEventListener("click", function () {
      var elegida = ej.querySelector('input[type="radio"]:checked');
      if (!elegida) {
        salida.textContent = "Primero elige una opción.";
        salida.className = "feedback aviso";
        return;
      }
      var acierto = elegida.value === ej.getAttribute("data-correcta");
      var texto = explicacion ? explicacion.textContent : "";
      salida.textContent = (acierto ? "Correcto. " : "Todavía no. ") + texto;
      salida.className = "feedback " + (acierto ? "bien" : "intenta");
    });
  });
})();
"""


class ContenidoInvalido(Exception):
    """El contenido YAML no cumple el contrato de la directiva."""

    def __init__(self, problemas: list[str]):
        self.problemas = problemas
        super().__init__("; ".join(problemas[:3]))


def _esc(valor: object) -> str:
    return html.escape(str(valor), quote=True)


def _slug(texto: str) -> str:
    normal = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in normal if not unicodedata.combining(c))
    limpio = []
    for c in sin_tildes.lower():
        if c.isalnum():
            limpio.append(c)
        elif c in " -_/":
            limpio.append("-")
    return re.sub(r"-+", "-", "".join(limpio)).strip("-")


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _texto_no_vacio(valor: object) -> bool:
    return isinstance(valor, str) and bool(valor.strip())


def _lista_textos(valor: object, minimo: int = 1) -> bool:
    return (
        isinstance(valor, list)
        and len(valor) >= minimo
        and all(_texto_no_vacio(v) for v in valor)
    )


def _recorrer_textos(valor: object):
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, dict):
        for v in valor.values():
            yield from _recorrer_textos(v)
    elif isinstance(valor, list):
        for v in valor:
            yield from _recorrer_textos(v)


def validar_leccion(datos: dict) -> list[str]:
    """Devuelve la lista de problemas del tema. Vacía significa válido."""
    problemas: list[str] = []

    materia = datos.get("materia")
    if materia not in MATERIAS:
        problemas.append(
            "materia debe ser una de: " + ", ".join(MATERIAS)
        )
    if not _texto_no_vacio(datos.get("titulo")):
        problemas.append("falta titulo (texto no vacío)")
    orden = datos.get("orden")
    if not isinstance(orden, int) or isinstance(orden, bool) or orden < 1:
        problemas.append("orden debe ser un entero mayor o igual que 1")
    if not _texto_no_vacio(datos.get("objetivo")):
        problemas.append("falta objetivo (texto no vacío)")
    if not _texto_no_vacio(datos.get("idea_clave")):
        problemas.append("falta idea_clave (texto no vacío)")

    pasos = datos.get("pasos")
    if not _lista_textos(pasos, minimo=2):
        problemas.append("pasos debe ser una lista de al menos 2 textos")

    ejemplo = datos.get("ejemplo")
    if not isinstance(ejemplo, dict):
        problemas.append("falta ejemplo (mapa con titulo, pasos y resultado)")
    else:
        if not _texto_no_vacio(ejemplo.get("titulo")):
            problemas.append("ejemplo.titulo debe ser un texto no vacío")
        if not _lista_textos(ejemplo.get("pasos"), minimo=2):
            problemas.append("ejemplo.pasos debe ser una lista de al menos 2 textos")
        if not _texto_no_vacio(ejemplo.get("resultado")):
            problemas.append("ejemplo.resultado debe ser un texto no vacío")

    esquema = datos.get("esquema")
    if not isinstance(esquema, dict):
        problemas.append("falta esquema (mapa con tipo y contenido)")
    else:
        tipo = esquema.get("tipo")
        if tipo not in TIPOS_ESQUEMA:
            problemas.append("esquema.tipo debe ser tabla, flujo o lista")
        if not _texto_no_vacio(esquema.get("titulo")):
            problemas.append("esquema.titulo debe ser un texto no vacío")
        if tipo == "tabla":
            columnas = esquema.get("columnas")
            if not _lista_textos(columnas, minimo=2):
                problemas.append("esquema.columnas debe tener al menos 2 textos")
            filas = esquema.get("filas")
            if not isinstance(filas, list) or not filas:
                problemas.append("esquema.filas debe ser una lista no vacía")
            elif isinstance(columnas, list):
                for i, fila in enumerate(filas, 1):
                    if not isinstance(fila, list) or len(fila) != len(columnas):
                        problemas.append(
                            f"esquema.filas[{i}] debe tener {len(columnas)} celdas"
                        )
                    elif not all(_texto_no_vacio(c) for c in fila):
                        problemas.append(f"esquema.filas[{i}] tiene celdas vacías")
        elif tipo == "flujo":
            if not _lista_textos(esquema.get("pasos"), minimo=2):
                problemas.append("esquema.pasos debe tener al menos 2 textos")
        elif tipo == "lista":
            if not _lista_textos(esquema.get("items"), minimo=1):
                problemas.append("esquema.items debe tener al menos 1 texto")

    practica = datos.get("practica")
    if not isinstance(practica, list) or not practica:
        problemas.append("practica debe ser una lista no vacía de ejercicios")
    else:
        for i, ejercicio in enumerate(practica, 1):
            if not isinstance(ejercicio, dict):
                problemas.append(f"practica[{i}] debe ser un mapa")
                continue
            if not _texto_no_vacio(ejercicio.get("pregunta")):
                problemas.append(f"practica[{i}].pregunta debe ser un texto no vacío")
            opciones = ejercicio.get("opciones")
            if not isinstance(opciones, list) or not (
                MIN_OPCIONES <= len(opciones) <= MAX_OPCIONES
            ):
                problemas.append(
                    f"practica[{i}].opciones debe tener entre {MIN_OPCIONES} y {MAX_OPCIONES} textos"
                )
            elif not all(_texto_no_vacio(o) for o in opciones):
                problemas.append(f"practica[{i}].opciones tiene una opción vacía")
            correcta = ejercicio.get("correcta")
            if not isinstance(correcta, int) or isinstance(correcta, bool):
                problemas.append(f"practica[{i}].correcta debe ser un entero")
            elif isinstance(opciones, list) and not (0 <= correcta < len(opciones)):
                problemas.append(
                    f"practica[{i}].correcta debe estar entre 0 y {len(opciones) - 1}"
                )
            if not _texto_no_vacio(ejercicio.get("explicacion")):
                problemas.append(f"practica[{i}].explicacion debe ser un texto no vacío")

    if not _lista_textos(datos.get("recordar"), minimo=1):
        problemas.append("recordar debe ser una lista con al menos 1 texto")

    nota = datos.get("nota")
    if nota is not None and not _texto_no_vacio(nota):
        problemas.append("nota, si existe, debe ser un texto no vacío")

    for texto in _recorrer_textos(datos):
        if "http://" in texto or "https://" in texto:
            problemas.append(
                "el contenido no puede tener enlaces externos; esta página debe funcionar sin internet"
            )
            break

    return problemas


def cargar(contenido: Path | str) -> list[tuple[Path, dict]]:
    """Lee y valida todas las lecciones. Lanza ContenidoInvalido si algo falla."""
    contenido = Path(contenido)
    if not contenido.is_dir():
        raise FileNotFoundError(f"no existe la carpeta de contenido: {contenido}")
    archivos = sorted(contenido.rglob("*.yaml"))
    if not archivos:
        raise ContenidoInvalido([f"no hay archivos .yaml en {contenido}"])

    problemas: list[str] = []
    lecciones: list[tuple[Path, dict]] = []
    for ruta in archivos:
        try:
            datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            problemas.append(f"{ruta}: YAML inválido: {exc}")
            continue
        if not isinstance(datos, dict):
            problemas.append(f"{ruta}: la raíz debe ser un mapa YAML")
            continue
        errores = validar_leccion(datos)
        if errores:
            problemas.extend(f"{ruta.name}: {error}" for error in errores)
            continue
        lecciones.append((ruta, datos))

    vistos_orden: dict[tuple[str, int], Path] = {}
    vistos_slug: dict[tuple[str, str], Path] = {}
    for ruta, datos in lecciones:
        clave_orden = (datos["materia"], datos["orden"])
        if clave_orden in vistos_orden:
            problemas.append(
                f"{ruta.name}: el orden {datos['orden']} de {datos['materia']} "
                f"ya lo usa {vistos_orden[clave_orden].name}"
            )
        else:
            vistos_orden[clave_orden] = ruta
        clave_slug = (datos["materia"], _slug(datos["titulo"]))
        if clave_slug in vistos_slug:
            problemas.append(
                f"{ruta.name}: el título genera el mismo nombre de archivo que "
                f"{vistos_slug[clave_slug].name}"
            )
        else:
            vistos_slug[clave_slug] = ruta

    if problemas:
        raise ContenidoInvalido(problemas)
    return lecciones


def _migas(partes: list[tuple[str, str | None]]) -> str:
    trozos = []
    for i, (texto, href) in enumerate(partes):
        if i:
            trozos.append('<span class="sep" aria-hidden="true">/</span>')
        if href is None:
            trozos.append(f'<span aria-current="page">{_esc(texto)}</span>')
        else:
            trozos.append(f'<a href="{_esc(href)}">{_esc(texto)}</a>')
    return '<nav class="migas contenedor" aria-label="Ubicación">' + "".join(trozos) + "</nav>"


def _cabecera(prefijo: str, migas: str) -> str:
    return (
        '<a class="saltar" href="#contenido">Saltar al contenido</a>\n'
        '<header class="barra">\n'
        '<div class="contenedor barra-fila">\n'
        f'<a class="marca" href="{prefijo}index.html">'
        '<span class="marca-sara">Material de estudio</span>'
        '<span class="marca-sub">3.º año de bachillerato</span></a>\n'
        '<div class="ajustes" role="group" aria-label="Ajustes de lectura">\n'
        '<button type="button" class="ajuste" data-accion="menos" '
        'aria-label="Reducir el tamaño del texto">A−</button>\n'
        '<button type="button" class="ajuste" data-accion="mas" '
        'aria-label="Aumentar el tamaño del texto">A+</button>\n'
        '<button type="button" class="ajuste" data-accion="contraste" '
        'aria-pressed="false">Contraste</button>\n'
        '</div>\n'
        '</div>\n'
        + migas +
        '\n</header>\n'
    )


def _pie() -> str:
    return (
        '<footer class="pie">\n<div class="contenedor">\n'
        '<p>Material de estudio · 3.º año de bachillerato</p>\n'
        '<p>Se puede leer sin prisa y repetir las veces que haga falta.</p>\n'
        '</div>\n</footer>\n'
    )


def _documento(
    titulo: str,
    cuerpo: str,
    clase_cuerpo: str = "",
    scripts: tuple[str, ...] = (),
) -> str:
    clases = f' class="{clase_cuerpo}"' if clase_cuerpo else ""
    extra = "".join(f"\n<script>\n{script}\n</script>" for script in scripts)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="es">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_esc(titulo)}</title>\n"
        "<style>\n" + CSS + "</style>\n"
        "</head>\n"
        f"<body{clases}>\n"
        + cuerpo
        + _pie()
        + "\n<script>\n" + JS_BASE + "\n</script>"
        + extra
        + "\n</body>\n</html>\n"
    )


def _render_esquema(esquema: dict) -> str:
    tipo = esquema["tipo"]
    titulo = _esc(esquema["titulo"])
    if tipo == "tabla":
        cabeceras = "".join(f"<th scope=\"col\">{_esc(c)}</th>" for c in esquema["columnas"])
        filas = []
        for fila in esquema["filas"]:
            celdas = "".join(f"<td>{_esc(c)}</td>" for c in fila)
            filas.append(f"<tr>{celdas}</tr>")
        return (
            '<div class="tabla-caja">\n<table>\n'
            f"<caption>{titulo}</caption>\n"
            f"<thead><tr>{cabeceras}</tr></thead>\n"
            "<tbody>\n" + "\n".join(filas) + "\n</tbody>\n</table>\n</div>"
        )
    if tipo == "flujo":
        piezas = []
        for i, paso in enumerate(esquema["pasos"]):
            if i:
                piezas.append('<li class="flecha" aria-hidden="true">↓</li>')
            piezas.append(f"<li>{_esc(paso)}</li>")
        return (
            f'<p class="titulo-esquema">{titulo}</p>\n'
            '<ol class="flujo">\n' + "\n".join(piezas) + "\n</ol>"
        )
    items = "".join(f"<li>{_esc(item)}</li>\n" for item in esquema["items"])
    return (
        f'<p class="titulo-esquema">{titulo}</p>\n'
        f'<ul class="lista-esquema">\n{items}</ul>'
    )


def _render_ejercicio(indice: int, ejercicio: dict, prefijo_nombre: str) -> str:
    nombre = f"{prefijo_nombre}-p{indice}"
    opciones = []
    for i, opcion in enumerate(ejercicio["opciones"]):
        opciones.append(
            f'<label><input type="radio" name="{_esc(nombre)}" value="{i}">'
            f'<span>{_esc(opcion)}</span></label>'
        )
    return (
        f'<fieldset class="ejercicio" data-correcta="{ejercicio["correcta"]}">\n'
        f"<legend>Pregunta {indice}</legend>\n"
        f'<p>{_esc(ejercicio["pregunta"])}</p>\n'
        '<div class="opciones">\n' + "\n".join(opciones) + "\n</div>\n"
        '<button type="button" class="comprobar">Comprobar</button>\n'
        '<p class="feedback" role="status" aria-live="polite"></p>\n'
        f'<p class="explicacion" hidden>{_esc(ejercicio["explicacion"])}</p>\n'
        "</fieldset>"
    )


def _render_leccion(
    materia: str,
    datos: dict,
    posicion: int,
    total: int,
    anterior: tuple[str, str] | None,
    siguiente: tuple[str, str] | None,
) -> str:
    info = MATERIAS[materia]
    migas = _migas([
        ("Inicio", "../index.html"),
        (info["nombre"], "index.html"),
        (datos["titulo"], None),
    ])
    cuerpo = [_cabecera("../", migas)]
    cuerpo.append('<main id="contenido" class="contenedor">')
    cuerpo.append(
        f'<p class="etiqueta">Tema {posicion} de {total} · {_esc(info["nombre"])}</p>'
    )
    cuerpo.append(f'<h1>{_esc(datos["titulo"])}</h1>')

    cuerpo.append('<section class="seccion">')
    cuerpo.append("<h2>Qué vas a aprender</h2>")
    cuerpo.append(f'<p class="objetivo">{_esc(datos["objetivo"])}</p>')
    cuerpo.append("</section>")

    cuerpo.append('<section class="seccion">')
    cuerpo.append("<h2>Idea clave</h2>")
    cuerpo.append(f'<p class="idea">{_esc(datos["idea_clave"])}</p>')
    cuerpo.append("</section>")

    cuerpo.append('<section class="seccion">')
    cuerpo.append("<h2>Paso a paso</h2>")
    cuerpo.append('<ol class="pasos">')
    for paso in datos["pasos"]:
        cuerpo.append(f"<li>{_esc(paso)}</li>")
    cuerpo.append("</ol>")
    cuerpo.append("</section>")

    cuerpo.append('<section class="seccion">')
    cuerpo.append("<h2>Ejemplo resuelto</h2>")
    cuerpo.append('<div class="ejemplo">')
    cuerpo.append(f'<h3>{_esc(datos["ejemplo"]["titulo"])}</h3>')
    cuerpo.append("<ol>")
    for paso in datos["ejemplo"]["pasos"]:
        cuerpo.append(f"<li>{_esc(paso)}</li>")
    cuerpo.append("</ol>")
    cuerpo.append(
        f'<p class="resultado">Resultado: {_esc(datos["ejemplo"]["resultado"])}</p>'
    )
    cuerpo.append("</div>")
    cuerpo.append("</section>")

    cuerpo.append('<section class="seccion">')
    cuerpo.append("<h2>Esquema</h2>")
    cuerpo.append(_render_esquema(datos["esquema"]))
    cuerpo.append("</section>")

    cuerpo.append('<section class="seccion">')
    cuerpo.append("<h2>Practica</h2>")
    cuerpo.append(
        '<p class="ayuda">Elige una opción y pulsa Comprobar. '
        "Puedes intentarlo otra vez las veces que necesites.</p>"
    )
    prefijo_nombre = _slug(datos["titulo"])
    for i, ejercicio in enumerate(datos["practica"], 1):
        cuerpo.append(_render_ejercicio(i, ejercicio, prefijo_nombre))
    cuerpo.append("</section>")

    cuerpo.append('<section class="seccion">')
    cuerpo.append("<h2>Para recordar</h2>")
    cuerpo.append('<ul class="recordar">')
    for item in datos["recordar"]:
        cuerpo.append(f"<li>{_esc(item)}</li>")
    cuerpo.append("</ul>")
    cuerpo.append("</section>")

    if datos.get("nota"):
        cuerpo.append('<aside class="nota seccion">')
        cuerpo.append("<h2>Nota importante</h2>")
        cuerpo.append(f"<p>{_esc(datos['nota'])}</p>")
        cuerpo.append("</aside>")

    cuerpo.append('<nav class="nav-tema" aria-label="Navegación entre temas">')
    if anterior is not None:
        titulo_anterior, archivo_anterior = anterior
        cuerpo.append(
            f'<a class="boton boton-suave" rel="prev" href="{_esc(archivo_anterior)}">'
            f"Anterior: {_esc(titulo_anterior)}</a>"
        )
    else:
        cuerpo.append("<span></span>")
    cuerpo.append(f'<a class="boton boton-suave" href="index.html">Volver a {_esc(info["nombre"])}</a>')
    if siguiente is not None:
        titulo_siguiente, archivo_siguiente = siguiente
        cuerpo.append(
            f'<a class="boton" rel="next" href="{_esc(archivo_siguiente)}">'
            f"Siguiente: {_esc(titulo_siguiente)}</a>"
        )
    else:
        cuerpo.append("<span></span>")
    cuerpo.append("</nav>")
    cuerpo.append("</main>")

    return _documento(
        f'{datos["titulo"]} · {info["nombre"]} · Material de estudio',
        "\n".join(cuerpo),
        clase_cuerpo=materia,
        scripts=(JS_EJERCICIOS,),
    )


def _render_materia(materia: str, lecciones: list[dict]) -> str:
    info = MATERIAS[materia]
    migas = _migas([("Inicio", "../index.html"), (info["nombre"], None)])
    cuerpo = [_cabecera("../", migas)]
    cuerpo.append('<main id="contenido">')
    cuerpo.append('<section class="portada"><div class="contenedor">')
    cuerpo.append('<p class="etiqueta">Materia</p>')
    cuerpo.append(f'<h1>{_esc(info["nombre"])}</h1>')
    cuerpo.append(f'<p class="entrada">{_esc(info["descripcion"])}</p>')
    cuerpo.append("</div></section>")
    cuerpo.append('<div class="contenedor">')
    cuerpo.append('<section class="seccion">')
    cuerpo.append(f'<h2>Temas de {_esc(info["nombre"])}</h2>')
    if not lecciones:
        cuerpo.append("<p>Todavía no hay temas en esta materia.</p>")
    else:
        cuerpo.append('<ol class="temas">')
        for datos in lecciones:
            archivo = f'{datos["orden"]:02d}-{_slug(datos["titulo"])}.html'
            cuerpo.append(
                f'<li><a href="{_esc(archivo)}">'
                f'<span class="tema-num">Tema {datos["orden"]}</span>'
                f'<span class="tema-titulo">{_esc(datos["titulo"])}</span>'
                f'<span class="tema-desc">{_esc(datos["objetivo"])}</span>'
                "</a></li>"
            )
        cuerpo.append("</ol>")
    cuerpo.append("</section>")
    cuerpo.append('<p><a class="boton" href="../index.html">Volver al inicio</a></p>')
    cuerpo.append("</div>")
    cuerpo.append("</main>")
    return _documento(
        f'{info["nombre"]} · Material de estudio',
        "\n".join(cuerpo),
        clase_cuerpo=materia,
    )


def _render_indice(por_materia: dict[str, list[dict]]) -> str:
    total = sum(len(v) for v in por_materia.values())
    migas = _migas([("Inicio", None)])
    cuerpo = [_cabecera("", migas)]
    cuerpo.append('<main id="contenido">')
    cuerpo.append('<section class="portada"><div class="contenedor">')
    cuerpo.append('<p class="etiqueta">3.º año de bachillerato</p>')
    cuerpo.append("<h1>Material de estudio</h1>")
    cuerpo.append(
        '<p class="entrada">Explicaciones paso a paso, esquemas y práctica de '
        "Matemáticas, Física y Química.</p>"
    )
    cuerpo.append("</div></section>")
    cuerpo.append('<div class="contenedor">')

    cuerpo.append('<section class="seccion">')
    cuerpo.append("<h2>Cómo usar esta página</h2>")
    cuerpo.append('<ol class="flujo">')
    pasos_uso = [
        "Elige una materia.",
        "Lee la idea clave y el paso a paso.",
        "Practica y comprueba tu respuesta.",
    ]
    for i, paso in enumerate(pasos_uso):
        if i:
            cuerpo.append('<li class="flecha" aria-hidden="true">↓</li>')
        cuerpo.append(f"<li>{_esc(paso)}</li>")
    cuerpo.append("</ol>")
    cuerpo.append("</section>")

    cuerpo.append('<section class="seccion">')
    cuerpo.append("<h2>Elige una materia</h2>")
    cuerpo.append('<div class="rejilla">')
    for clave, info in MATERIAS.items():
        lista = por_materia.get(clave, [])
        cuerpo.append(
            f'<a class="tarjeta {clave}" href="{clave}/index.html">'
            f'<span class="insignia" aria-hidden="true">{_esc(info["letra"])}</span>'
            f'<span class="tarjeta-nombre">{_esc(info["nombre"])}</span>'
            f'<span class="tarjeta-desc">{_esc(info["descripcion"])}</span>'
            f'<span class="tarjeta-meta">{_plural(len(lista), "tema", "temas")}</span>'
            "</a>"
        )
    cuerpo.append("</div>")
    cuerpo.append("</section>")

    cuerpo.append(
        '<p class="calma seccion"><strong>No hay tiempo límite.</strong> '
        "Puedes repetir un tema las veces que necesites. La página no guarda "
        "notas ni envía nada a internet.</p>"
    )
    cuerpo.append("</div>")
    cuerpo.append("</main>")
    return _documento(
        "Material de estudio · 3.º año de bachillerato",
        "\n".join(cuerpo),
    )


def construir(contenido: Path | str) -> tuple[dict[str, str], dict]:
    """Devuelve (páginas, resumen). No escribe nada."""
    lecciones = cargar(contenido)
    por_materia: dict[str, list[dict]] = {clave: [] for clave in MATERIAS}
    for _ruta, datos in lecciones:
        por_materia[datos["materia"]].append(datos)
    for clave in por_materia:
        por_materia[clave].sort(key=lambda d: d["orden"])

    paginas: dict[str, str] = {"index.html": _render_indice(por_materia)}
    for clave, lista in por_materia.items():
        paginas[f"{clave}/index.html"] = _render_materia(clave, lista)
        archivos = [
            f'{d["orden"]:02d}-{_slug(d["titulo"])}.html' for d in lista
        ]
        for i, datos in enumerate(lista):
            anterior = (lista[i - 1]["titulo"], archivos[i - 1]) if i > 0 else None
            siguiente = (
                (lista[i + 1]["titulo"], archivos[i + 1])
                if i + 1 < len(lista)
                else None
            )
            paginas[f"{clave}/{archivos[i]}"] = _render_leccion(
                clave, datos, i + 1, len(lista), anterior, siguiente
            )

    resumen = {
        "materias": {clave: len(lista) for clave, lista in por_materia.items()},
        "temas": sum(len(lista) for lista in por_materia.values()),
        "paginas": len(paginas),
    }
    return paginas, resumen


def _salida_permitida(salida: Path | str) -> bool:
    destino = Path(salida).resolve()
    raiz = SARA_DIR.resolve()
    return destino == raiz or raiz in destino.parents


def escribir(paginas: dict[str, str], salida: Path | str) -> list[str]:
    destino = Path(salida)
    escritos = []
    for relativo in sorted(paginas):
        if not relativo.endswith(".html"):
            raise ValueError(f"la salida solo admite .html: {relativo}")
        ruta = destino / relativo
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with open(ruta, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(paginas[relativo])
        escritos.append(relativo)
    return escritos


def _fallo(codigo: int, detalle: object, json_out: bool) -> int:
    if json_out:
        print(json.dumps(
            {"status": "error", "code": codigo, "detalle": detalle},
            ensure_ascii=False,
            indent=2,
        ))
    else:
        print(f"ERROR ({codigo})", file=sys.stderr)
        if isinstance(detalle, list):
            for linea in detalle:
                print(f"  - {linea}", file=sys.stderr)
        else:
            print(f"  {detalle}", file=sys.stderr)
    return codigo


def ejecutar(
    contenido: Path | str = CONTENIDO_POR_DEFECTO,
    salida: Path | str = SARA_DIR,
    check: bool = False,
    dry_run: bool = False,
    json_out: bool = False,
) -> int:
    try:
        paginas, resumen = construir(contenido)
    except FileNotFoundError as exc:
        return _fallo(1, str(exc), json_out)
    except ContenidoInvalido as exc:
        return _fallo(3, exc.problemas, json_out)

    if not _salida_permitida(salida):
        return _fallo(
            5,
            f"la salida debe estar dentro de {SARA_DIR}; se recibió {salida}",
            json_out,
        )

    if check or dry_run:
        if json_out:
            print(json.dumps(
                {"status": "ok", **resumen, "archivos": sorted(paginas)},
                ensure_ascii=False,
                indent=2,
            ))
        else:
            print(
                f"Contenido válido: {_plural(resumen['temas'], 'tema', 'temas')} "
                f"en {len(MATERIAS)} materias."
            )
            if dry_run:
                for archivo in sorted(paginas):
                    print(f"  {archivo}")
        return 0

    try:
        escritos = escribir(paginas, salida)
    except OSError as exc:
        return _fallo(1, str(exc), json_out)

    if json_out:
        print(json.dumps(
            {
                "status": "ok",
                **resumen,
                "salida": str(Path(salida)),
                "archivos": escritos,
            },
            ensure_ascii=False,
            indent=2,
        ))
    else:
        print(
            f"Listo: {_plural(resumen['temas'], 'tema', 'temas')} y "
            f"{_plural(resumen['paginas'], 'página', 'páginas')} en {Path(salida)}"
        )
        print(f"Abre {Path(salida) / 'index.html'} en el navegador.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Genera el sitio de estudio de Sara (HTML offline)."
    )
    ap.add_argument("--contenido", default=str(CONTENIDO_POR_DEFECTO))
    ap.add_argument("--salida", default=str(SARA_DIR))
    ap.add_argument("--check", action="store_true", help="valida sin escribir")
    ap.add_argument("--dry-run", action="store_true", help="muestra archivos sin escribir")
    ap.add_argument("--json", action="store_true", help="salida JSON")
    args = ap.parse_args()
    return ejecutar(
        contenido=args.contenido,
        salida=args.salida,
        check=args.check,
        dry_run=args.dry_run,
        json_out=args.json,
    )


if __name__ == "__main__":
    sys.exit(main())
