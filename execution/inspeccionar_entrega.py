#!/usr/bin/env python3
"""
Inventario visual de una entrega de alumno escaneada.

Responde a la pregunta que un PDF de examen planté en `evaluar_examen.py`: ¿la entrega
incluye el enunciado que se.contestó, o son solo respuestas? Sin enunciado el modelo
evalúa a ciegas, y eso no se detecta mirando el texto del PDF porque un escaneo no tiene
capa de texto: hay que mirar la imagen.

Este script NO evalúa y NO corrige. Solo describe. La verdad sobre qué error cometió el
alumno la pone el profesor (directivas/evaluar_examen_estudiante.yaml, salida #1 del
plan de estudio de caso); este script evita que el profesor tenga que abrir el PDF
para dizer si el flujo es viable sobre él.

Determinista en lo que debe serlo: las entradas se validan, la salida se valida contra
un esquema, y un fallo es código de salida, no un `None` silencioso. La descripción del
contenido la produce un LLM (es percepción visual; no hay forma determinista de
saber qué tinta hay en una foto).

Uso:
    python3 execution/inspeccionar_entrega.py --pdf <ruta.pdf> [--dpi 150]
        [--modelo google/gemini-2.5-flash] [--json]

Salida: JSON por stdout con `status`, `archivo`, `paginas`, `modelo`, `tokens` e
`inspeccion`. Códigos: 0 ok · 2 error de uso/entrada · 3 API · 4 modelo no devolvió
JSON válido · 5 esquema inválido.
"""

import argparse
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from evaluar_examen import _find_balanced_json, pdf_to_images_bytes  # noqa: E402
from llm_client import build_multimodal_content, openrouter_chat  # noqa: E402

MODELO_DEFAULT = "google/gemini-2.5-flash"

ESQUEMA_INSPECCION = {
    "incluye_enunciado": ("bool", "true si las páginas contienen el enunciado de las "
                                 "preguntas; false si son solo respuestas del alumno; "
                                 "null si no se puede determinar con confianza."),
    "confianza": ("string", "alta | media | baja"),
    "tipo_documento": ("string", "examen resuelto | solo respuestas | informe | "
                                 "consulta | otro"),
    "asignatura": ("string", "materia que se intuye del encabezado, o 'desconocida'"),
    "tema": ("string", "tema técnico del examen en una frase, o 'desconocido'"),
    "preguntas": ("lista de objetos", "una entrada por pregunta visible, con "
                  "{numero, enunciado_breve, respondida}"),
    "corregido_por": ("string", "si el documento viene corregido o anotado por el "
                        "profesor, quién y qué dice; si no hay corrección, ''."),
    "observaciones": ("lista de strings", "hechos útiles para decidir si el flujo es "
                       "viable: legibilidad, si está en español, páginas en blanco, "
                       "respuestas ilegibles, etc."),
}

INSTRUCCION = """\
Eres un inspector de documentos escaneados de entregas de estudiantes de ELECTRÓNICA.
Recibes todas las páginas de UN solo documento, en orden.

Tu trabajo es DESCRIBIRLO con precisión, NO calificarlo y NO corregirlo. No emitas nota,
no juzgues si las respuestas son buenas o malas: solo reporta lo que el documento contiene
literalmente.

Devuelve un único objeto JSON con EXACTAMENTE estas siete claves. Nada más:

{
  "incluye_enunciado": true,
  "confianza": "alta",
  "tipo_documento": "solo respuestas",
  "asignatura": "Lab II de Física",
  "tema": "medida de corriente y tensión en circuitos",
  "preguntas": [],
  "corregido_por": "",
  "observaciones": ["la letra es legible"]
}

Reglas de cada clave:

- incluye_enunciado: la pregunta principal. Pon true SOLO si ves el texto de las
  preguntas (impreso o escrito) en las mismas páginas de las respuestas. Si solo hay
  respuestas, desarrollo de ejercicios, cálculos sueltos o diagramas sin enunciado, pon
  false. Si no puedes decidir, pon null con confianza "baja": es preferible admitir
  incertidumbre a inventar.
- confianza: "alta", "media" o "baja". Nada más.
- tipo_documento: uno solo de estos cinco literales, tal cual:
  "examen resuelto", "solo respuestas", "informe", "consulta", "otro"
- asignatura y tema: lo que se intuye del encabezado y del contenido. Si no se sabe,
  escribe "desconocido".
- preguntas: lista de objetos con "numero", "enunciado_breve" y "respondida". Déjala
  vacía [] si no hay enunciado visible.
- corregido_por: si el papel viene con anotaciones, tachaduras o comentarios del profesor
  (otra tinta, "ok", "mal", una nota al margen), transcribe qué dicen. Si no hay
  corrección, escribe "".
- observaciones: lista de textos concretos. Incluye legibilidad de la letra, idioma,
  páginas en blanco y respuestas ilegibles. Sé específico: "la pregunta 2 es un garabato
  ilegible" sirve; "es regular" no.

Añade además, si puedes deducirlo del número visible más alto o más bajo, un texto en
observaciones del tipo: "la entrega empieza en el ítem 7, faltan los anteriores".

No uses claves adicionales. No escribas el texto que transcribas del documento en ninguna
clave: describe, no transcribas, salvo en corregido_por. Devuelve SOLO el JSON.
"""


def construir_prompt(paginas: int) -> str:
    return (
        f"Este documento tiene {paginas} página(s) y todas están adjuntas arriba, en orden.\n"
        "Devuelve SOLO el JSON, sin texto antes ni después."
    )


def validar(datos) -> list[str]:
    """Valida el JSON del modelo contra el esquema. Retorna lista de problemas."""
    problemas = []
    if not isinstance(datos, dict):
        return [f"la respuesta no es un objeto JSON sino {type(datos).__name__}"]

    # `incluye_enunciado` es OBLIGATORIA y no optional a propósito. Es la única celda
    # que decide si el flujo de evaluación es viable sobre este documento (sin
    # enunciado el modelo corrige a ciegas), así que su ausencia no puede pasar por
    # "el modelo no sabe": si la clave no está, el JSON es inválido y punto.
    if "incluye_enunciado" not in datos:
        problemas.append(
            "falta incluye_enunciado, que es la clave que decide si la entrega es "
            "evaluable; su ausencia no se puede leer como 'no se sabe'"
        )
    elif not (datos["incluye_enunciado"] is None
              or isinstance(datos["incluye_enunciado"], bool)):
        problemas.append(
            "incluye_enunciado debe ser true/false/null; llegó "
            f"{datos['incluye_enunciado']!r}"
        )

    if datos.get("confianza") not in ("alta", "media", "baja"):
        problemas.append(
            f"confianza debe ser alta|media|baja; llegó {datos.get('confianza')!r}"
        )

    tipo = datos.get("tipo_documento")
    if tipo not in ("examen resuelto", "solo respuestas", "informe", "consulta", "otro"):
        problemas.append(f"tipo_documento fuera del vocabulario: {tipo!r}")

    preguntas = datos.get("preguntas")
    if preguntas is None:
        datos["preguntas"] = []
    elif not isinstance(preguntas, list):
        problemas.append(f"preguntas debe ser una lista; llegó {type(preguntas).__name__}")
        datos["preguntas"] = []
    else:
        for i, p in enumerate(preguntas):
            if not isinstance(p, dict):
                problemas.append(f"preguntas[{i}] no es un objeto")
                continue
            if "numero" not in p:
                problemas.append(f"preguntas[{i}] sin 'numero'")

    if datos.get("corregido_por") is None:
        datos["corregido_por"] = ""

    if datos.get("observaciones") is None:
        datos["observaciones"] = []
    elif not isinstance(datos["observaciones"], list):
        problemas.append("observaciones debe ser una lista")
        datos["observaciones"] = []

    return problemas


def resumir(datos: dict) -> str:
    """Resumen legible para humano (el JSON completo va por stdout)."""
    lineas = [
        f"  tipo            : {datos.get('tipo_documento')}",
        f"  incluye enunciado: {datos.get('incluye_enunciado')}"
        f"  (confianza: {datos.get('confianza')})",
        f"  asignatura/tema : {datos.get('asignatura')} / {datos.get('tema')}",
        f"  preguntas       : {len(datos.get('preguntas', []))}",
    ]
    corregido = str(datos.get("corregido_por", "")).strip()
    if corregido:
        lineas.append(f"  CORREGIDO POR   : {corregido}")
    for obs in datos.get("observaciones", [])[:6]:
        lineas.append(f"  - {obs}")
    return "\n".join(lineas)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inventario visual de una entrega escaneada (no evalúa).",
    )
    parser.add_argument("--pdf", required=True, help="Ruta al PDF de la entrega.")
    parser.add_argument("--dpi", type=int, default=150,
                        help="Resolución de renderizado (default 150; sube a 250 si "
                             "la letra es pequeña).")
    parser.add_argument("--modelo", default=MODELO_DEFAULT)
    parser.add_argument("--json", action="store_true",
                        help="Solo JSON por stdout, sin resumen legible.")
    args = parser.parse_args()

    if not os.path.isfile(args.pdf):
        print(f"[ERROR] No existe el PDF: {args.pdf}", file=sys.stderr)
        return 2
    if args.dpi < 72 or args.dpi > 400:
        print(f"[ERROR] --dpi debe estar entre 72 y 400; llegó {args.dpi}", file=sys.stderr)
        return 2

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        print("[ERROR] Falta OPENROUTER_API_KEY en el entorno.", file=sys.stderr)
        return 3

    try:
        images = pdf_to_images_bytes(args.pdf, dpi=args.dpi)
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] No se pudo renderizar el PDF: {e}", file=sys.stderr)
        return 2

    print(f"[INFO] {os.path.basename(args.pdf)}: {len(images)} página(s) a "
          f"{args.dpi} DPI -> {args.modelo}", file=sys.stderr)

    try:
        contenido, tokens = openrouter_chat(
            messages=[
                {"role": "system", "content": INSTRUCCION},
                {
                    "role": "user",
                    "content": build_multimodal_content(
                        images,
                        labels=[f"Página {i}" for i in range(1, len(images) + 1)],
                        trailing_text=construir_prompt(len(images)),
                    ),
                },
            ],
            model=args.modelo,
            api_key=api_key,
            temperature=0.0,
            max_tokens=int(os.getenv("OPENROUTER_MAX_TOKENS", "2048")),
            response_format={"type": "json_object"},
        )
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] Falló la llamada al modelo: {e}", file=sys.stderr)
        return 3

    crudo = _find_balanced_json(contenido or "")
    if not crudo:
        print("[ERROR] El modelo no devolvió un JSON válido.", file=sys.stderr)
        print(f"[DEBUG] Respuesta cruda: {(contenido or '')[:600]}", file=sys.stderr)
        return 4
    try:
        datos = json.loads(crudo)
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON balanceado pero no parseable: {e}", file=sys.stderr)
        return 4

    problemas = validar(datos)
    if problemas:
        print("[ERROR] El modelo devolvió un JSON que no cumple el esquema:",
              file=sys.stderr)
        for p in problemas:
            print(f"  - {p}", file=sys.stderr)
        salida = {
            "status": "error",
            "code": 5,
            "message": "JSON del modelo fuera de esquema.",
            "archivo": args.pdf,
            "paginas": len(images),
            "modelo": args.modelo,
            "problemas": problemas,
            "inspeccion": datos,
        }
        print(json.dumps(salida, ensure_ascii=False, indent=2))
        return 5

    salida = {
        "status": "ok",
        "archivo": args.pdf,
        "paginas": len(images),
        "modelo": args.modelo,
        "tokens": tokens,
        "inspeccion": datos,
    }
    if not args.json:
        print(f"[OK] {os.path.basename(args.pdf)}")
        print(resumir(datos))
    print(json.dumps(salida, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())