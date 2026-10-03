#!/usr/bin/env python3
"""
evaluar_examen.py — Evaluación preliminar de exámenes con LLM multimodal (Layer 3: Execution)

Lee un PDF de examen de estudiante, renderiza cada página como imagen de alta resolución
en memoria y se las envía en bloque a un modelo multimodal (Gemini o OpenRouter) para una
evaluación académica estructurada.

Uso:
    python3 execution/evaluar_examen.py --pdf examenes/01/examen_estudiantes/entrega_alumno.pdf
    python3 execution/evaluar_examen.py --pdf <ruta> [--modelo gemini-2.5-flash] [--dpi 250]
                                        [--tipo examen|laboratorio] [--rubrica <ruta_yaml>]

Tipos de documento (`--tipo`): `examen` (default) evalúa cada pregunta del examen
escrito; `laboratorio` evalúa cada sección del informe. Lo que cambia es el
encuadre de la tarea, no el contrato de salida (`SCHEMA_SALIDA` es único).

Salida (stdout, JSON):
    {
      "estudiante": "...",
      "archivo": "...",
      "modelo": "...",
      "paginas_procesadas": N,
      "evaluacion": {
        "puntaje_sugerido": "X.X/10",
        "nivel_desempeno": "...",
        "resumen_general": "...",
        "fortalezas": [...],
        "areas_de_mejora": [...],
        "observaciones_por_item": [...],
        "errores_conceptuales": [...],
        "errores_procedimentales": [...],
        "recomendaciones_al_estudiante": "...",
        "nota_para_el_profesor": "..."
      },
      "tokens_usados": {...},
      "timestamp": "..."
    }

Códigos de salida:
    0 — Evaluación completada exitosamente
    1 — Argumento inválido o archivo no encontrado
    2 — Error de API (autenticación, límite de tasa, etc.)
    3 — Error al procesar el PDF (corrupto, sin páginas, etc.)
    4 — Respuesta del modelo no parseable como JSON
"""

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

# PyYAML solo se usa para validar la rúbrica (pesos y claves). La rúbrica se entrega al
# modelo como TEXTO; el parseo existe para que el código pueda contrastar los pesos
# reales con lo que el modelo devuelva, no para "structured output" del LLM. Si faltara,
# el script avisa en vez de fingir que la rúbrica es válida.
try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - el entorno del repo trae PyYAML
    yaml = None

# ── Dependencias externas ──────────────────────────────────────────────────────
try:
    import pymupdf as fitz  # PyMuPDF (modern API, avoids deprecated fitz warning)
except ImportError:
    print(json.dumps({
        "status": "error", "code": 1,
        "message": "PyMuPDF no instalado. Ejecuta: pip install pymupdf"
    }))
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # .env opcional si la variable ya está en el entorno

# ── SDKs de LLMs (importación según backend) ────────────────────────────────────
_GEMINI_AVAILABLE = False
_GENAI_SDK = None
try:
    from google import genai
    from google.genai import types as genai_types
    _GEMINI_AVAILABLE = True
    _GENAI_SDK = "new"
except ImportError:
    try:
        import google.generativeai as _genai_legacy
        from google.generativeai import types as _genai_legacy_types
        _GEMINI_AVAILABLE = True
        _GENAI_SDK = "legacy"
    except ImportError:
        pass

_OPENROUTER_AVAILABLE = False
try:
    from openai import OpenAI
    _OPENROUTER_AVAILABLE = True
except ImportError:
    pass

try:
    from execution.llm_client import openrouter_chat, build_multimodal_content
except ImportError:
    from llm_client import openrouter_chat, build_multimodal_content


# ── System Instruction ─────────────────────────────────────────────────────────
#
# El prompt se compone de tres piezas, no es un bloque monolítico:
#
#   PERFIL_COMUN    idéntico para todo tipo de documento (dominio, nivel, el aviso
#                   de que esto es preliminar y apoya al profesor humano).
#   TAREA_POR_TIPO  lo ÚNICO que cambia por tipo: cómo se nombra la unidad de
#                   evaluación (pregunta / sección) y qué se mira en ella.
#   SCHEMA_SALIDA   UN SOLO contrato de salida para ambos tipos. No se parte a
#                   propósito: los criterios de una práctica de laboratorio
#                   (presentación, montaje, mediciones, análisis...) mapean 1:1
#                   sobre la misma forma de "lista de ítems con puntaje parcial y
#                   errores", así que partirlo obligaría a `generar_informe.py` a
#                   ramificar sin ganar nada. Lo protege
#                   `execution/test_evaluar_rubrica.py` (test_schema_unico).

PERFIL_COMUN = """
Eres un asistente académico especializado en la corrección de documentos de **Electrónica** a nivel universitario.
Tu función es realizar una evaluación preliminar rigurosa, objetiva y pedagógicamente útil del trabajo de un estudiante.

## Tu perfil
- Tienes dominio profundo de Electrónica: análisis de circuitos (CC y CA), dispositivos semiconductores (diodos, transistores, amplificadores operacionales), electrónica digital y analógica, leyes de Kirchhoff, teoremas de redes, respuesta en frecuencia y diseño básico de circuitos.
- Comprendes el nivel de formación esperado en estudiantes de Ingeniería Electrónica, Ingeniería Eléctrica o carreras afines.
- Tu evaluación es una **observación preliminar** que apoya al profesor humano, no una calificación definitiva.

## Reglas de evaluación (comunes a todo tipo de documento)
- Sé riguroso pero justo. Penaliza los errores conceptuales más que los procedimentales menores.
- Si una respuesta está parcialmente correcta, reconócelo explícitamente.
- Si una parte está en blanco, ilegible o ausente, indícalo.
- No inventes contenido: evalúa solo lo que está escrito en las imágenes.
- Puntúa cada ítem dentro de su peso, en una escala de 0 a 10 puntos.

## Puntuación: qué decides tú y qué decide el programa

- La escala es **0 a 10**. El 10 es el máximo de la universidad y nadie puede superarlo.
- Tú NO emites la nota total ni el nivel de desempeño. Esos los calcula el programa sumando
  tus `puntaje_parcial`, de forma determinista y exacta. Intentar emitirlos es un error:
  se ignorarán.
- Lo que sí haces es puntuar **cada ítem de 0 a su peso**, que es el denominador de la
  rúbrica. Usa el peso exacto, no uno inventado ni uno aproximado.
- Cuando no haya rúbrica (examen sin pesos), reparte los 10 puntos entre los ítems según
  su importancia y usa esos mismos repartos como denominadores.
"""

TAREA_POR_TIPO = {
    "examen": """
## Tu tarea
Se te entregará un conjunto de imágenes correspondientes a las páginas de un **examen escrito**. Debes:

1. **Identificar cada pregunta o ítem** que aparezca en el examen.
2. **Evaluar la respuesta de cada pregunta** considerando:
   - Corrección conceptual: ¿el estudiante comprendió el principio de funcionamiento del circuito o dispositivo?
   - Corrección procedimental: ¿el análisis matemático/lógico es correcto?
   - Claridad y organización: ¿la respuesta es legible y coherente?
   - Manejo de unidades: ¿las unidades son correctas y consistentes?
   - Uso de fórmulas: ¿son apropiadas y bien aplicadas?
3. **Detectar errores conceptuales** (malentendidos de teoría de circuitos, comportamiento de componentes, polarización, etc.).
4. **Detectar errores procedimentales** (cálculos incorrectos, pasos omitidos, errores de álgebra).
5. **Redactar observaciones** útiles para el estudiante (formativas) y notas para el profesor.

Si el examen declara una estructura de puntaje visible (ej: "Pregunta 1: 20 pts"), úsala como referencia para ponderar cada ítem, pero recuerda que los denominadores deben sumar 10.
""",

    "laboratorio": """
## Tu tarea
Se te entregará un conjunto de imágenes correspondientes a las páginas de un **informe de práctica de laboratorio**. La unidad de evaluación es la SECCIÓN del informe, no una pregunta. Debes:

1. **Identificar cada sección del informe** (presentación, marco teórico, diagramas, montaje, mediciones, análisis, conclusiones y las que aparezcan).
2. **Evaluar cada sección** considerando:
   - Corrección conceptual: ¿comprende los principios físicos y eléctricos involucrados?
   - Corrección procedimental: ¿los cálculos, el montaje y el análisis de datos son correctos?
   - Claridad y organización: ¿la sección es legible y coherente con el resto del informe?
   - Manejo de unidades: ¿las unidades son correctas y consistentes?
   - Uso de fórmulas y referencias: ¿son apropiadas y están bien aplicadas?
3. **Detectar errores conceptuales** (malentendidos de teoría, comportamiento de componentes, conexiones mal identificadas).
4. **Detectar errores procedimentales** (cálculos incorrectos, pasos omitidos, errores de álgebra, lecturas mal tomadas).
5. **Valorar la evidencia experimental**: si la sección de mediciones existe, es completa y los valores son razonables; si el montaje está documentado con diagramas o fotografías.
6. **Redactar observaciones** útiles para el estudiante (formativas) y notas para el profesor.

El montaje experimental (protoboard, instrumentación, polaridad) puede estar fotografiado: si una imagen no es interpretable con confianza, NO la inventes — dilo en `nota_para_el_profesor` como punto que requiere revisión manual.
""",
}

# Un SOLO contrato para los dos tipos. `observaciones_por_item` es el nombre neutro
# (sirve para una pregunta de examen y para una sección de informe). El alias
# `observaciones_por_pregunta` se acepta al LEER, para que un JSON ya generado
# siga rindiendo informe; ver `execution/generar_informe.py`.
#
# `puntaje_sugerido` y `nivel_desempeno` NO se piden al modelo. Se calculan aquí con
# `calcular_nota()` a partir de los parciales. Ver NOTAS_INVENTADAS: pedirle la suma a un
# LLM no falla de forma visible, solo devuelve un número que no cuadra con sus propios
# ítems (ocurrió: 5.5/10 con parciales que sumaban 5.0).
SCHEMA_SALIDA = """
## Formato de respuesta
Debes responder ÚNICAMENTE con un objeto JSON válido, sin texto adicional antes ni después, con exactamente esta estructura:

```json
{
  "resumen_general": "Párrafo breve describiendo el desempeño global del estudiante.",
  "fortalezas": [
    "Descripción de fortaleza 1",
    "Descripción de fortaleza 2"
  ],
  "areas_de_mejora": [
    "Descripción de área de mejora 1"
  ],
  "observaciones_por_item": [
    {
      "item": "Pregunta 1 / Sección 'Mediciones' (o descripción del ítem)",
      "puntaje_parcial": "X.X/PESO (el denominador es el peso EXACTO del criterio, en el mismo formato de la rúbrica)",
      "evaluacion": "Descripción detallada de la evaluación de este ítem.",
      "errores": ["error específico 1", "error específico 2"]
    }
  ],
  "errores_conceptuales": [
    "Descripción del error conceptual 1"
  ],
  "errores_procedimentales": [
    "Descripción del error procedimental 1"
  ],
  "recomendaciones_al_estudiante": "Párrafo con retroalimentación formativa directamente dirigida al estudiante.",
  "nota_para_el_profesor": "Observaciones especiales para el profesor: ambigüedades encontradas, respuestas dudosas, ítems que requieren revisión manual, etc."
}
```

No emitas `puntaje_sugerido` ni `nivel_desempeno`: el programa los calcula sumando tus
puntajes parciales.
"""

TIPOS = tuple(TAREA_POR_TIPO.keys())

# ── La nota se calcula AQUÍ, no la decide el modelo ────────────────────────────
#
# Por qué: una vez la rúbrica de práctica declaraba pesos que sumaban 11.5 mientras
# el contrato pedía "X.X/10". El modelo recibía una escala que no cerraba y la
# normalizaba como podía. No fallaba de forma visible: devolvía JSON bien formado con
# un total que no cuadraba con la suma de sus propios ítems (5.5/10 cuando los
# parciales sumaban 5.0). Ni el test ni el informe lo detectaban, porque nadie
# comparaba la suma contra el total.
#
# El arreglo NO es pedirle mejor aritmética al modelo (eso ya se probó y falló: los
# denominadores pasaron a ser correctos y el total siguió sin cuadrar). Es no pedirle
# aritmética: el modelo puntúa ítems, que es la parte que hace bien; y la suma la
# hace este código, que es la parte que hace bien un LLM.
#
# La tabla de niveles vive AQUÍ y no solo en el YAML de la rúbrica porque el rango es
# política de la institución (la escala de calificación de la universidad), no una
# propiedad del documento evaluado: aplica igual a exámenes y a prácticas.
#
# Aun así el YAML la replica (para que quien lea la rúbrica la vea), y esa duplicación
# es un riesgo: dos tablas de niveles que divergen en silencio. Por eso
# `test_evaluar_rubrica.py::test_niveles_yaml_y_codigo_no_divergen` las compara. Si se
# edita una, hay que editar la otra.

NOTA_MAXIMA = 10.0

# (límite superior inclusivo, nombre del nivel). El último es el techo absoluto.
NIVELES: tuple[tuple[float, str], ...] = (
    (2.9, "Insuficiente"),
    (4.9, "Deficiente"),
    (6.9, "Suficiente"),
    (8.9, "Bueno"),
    (10.0, "Excelente"),
)


def nivel_para_nota(nota: float) -> str:
    """Nivel de desempeño correspondiente a una nota. PURA y total: siempre devuelve."""
    for techo, nombre in NIVELES:
        if nota <= techo:
            return nombre
    return NIVELES[-1][1]


def _parsear_parcial(bruto: object) -> tuple[float | None, float | None]:
    """
    Extrae (obtenido, denominador) de un `puntaje_parcial`.

    Acepta lo que el modelo produce en la práctica: "0.5/1.7", "0.5 / 1.7", "0.5 de 1.7",
    "0.5/10" e incluso un 0.5 a secas. Devuelve (None, None) si no hay número reconocible,
    para que quien llama lo cuente como ítem ilegible en vez de inventar un cero.
    """
    if isinstance(bruto, (int, float)) and not isinstance(bruto, bool):
        return float(bruto), None
    if not isinstance(bruto, str):
        return None, None
    texto = bruto.strip().replace(",", ".")
    # El denominador solo existe si hay un separador explicito ("x/y", "x de y",
    # "x out of y"). Un numero suelto ("0.5") NO tiene denominador: interpretarlo como
    # su propio maximo haria que "0.5" pareciera el tope de un criterio y que la
    # comprobacion de "parcial por encima del peso" se disparara sola.
    sep = re.search(
        r"(-?\d+(?:\.\d+)?)\s*(?:/|de|out\s+of)\s*(-?\d+(?:\.\d+)?)",
        texto,
        re.IGNORECASE,
    )
    if sep:
        return float(sep.group(1)), float(sep.group(2))
    m = re.search(r"(-?\d+(?:\.\d+)?)", texto)
    if not m:
        return None, None
    return float(m.group(1)), None


def calcular_nota(
    items: object,
    *,
    pesos: dict[str, float] | None = None,
    nota_maxima: float = NOTA_MAXIMA,
) -> tuple[dict, list[str]]:
    """
    Calcula la nota total y el nivel a partir de los ítems del modelo. PURA.

    (mismos ítems, mismos pesos) -> (misma nota, mismos avisos). No toca disco ni red.

    `pesos` es el mapa criterio -> peso que declara la RÚBRICA (ver `cargar_rubrica`), o
    `None` si esta evaluación no tiene rúbrica (un examen sin pesos). Es lo que permite
    dos cosas que antes eran imposibles:

      1. **Detectar el ítem ausente.** Si la rúbrica tiene 8 criterios y el modelo
         devuelve 7, se sabe cuál falta en vez de asumir que el alumno no lo respondió.
      2. **No Creerle los pesos al modelo.** El peso lo escribió el profesor en la
         rúbrica; si el modelo dice `0.4/0.5` para `gramatica`, se usa el 0.4 de la
         rúbrica y se avisa, en vez de puntuar sobre un 10 que nadie declaró.

    Escala: la nota se calcula sobre `NOTA_MAXIMA` SIEMPRE, escale lo que escale lo que
    devuelva el modelo. Si los denominadores suman 3 (un punto por pregunta, lo normal en
    un examen de 3 preguntas) la nota es `10 · obtenido/3`, no `obtenido`: sumar en crudo
    daba 1.5/10 a un alumno que approved la mitad, y sin un solo aviso cuando el modelo
    además olvidaba los denominadores. Si NO hay denominadores ni rúbrica, la escala es
    indescifrable y la nota se marca `nota_fiable: false` en vez de publicarse como si
    fuera buena: una nota inventada es peor que ninguna.

    Devuelve `(datos, avisos)`:
      datos  {"puntaje_sugerido": "5.0/10", "nivel_desempeno": "Suficiente",
              "puntaje_numerico": 5.0, "maximo_alcanzable": 10.0, "items_legibles": N,
              "items_ausentes": [...], "nota_fiable": True, "escala_aplicada": "10.0"}
      avisos  lista de strings legible por el humano, para `nota_para_el_profesor`.

    Los avisos existen porque un total calculado sin más ocultaría los fallos que un
    modelo puede cometer al puntuar: parciales ilegibles, parciales por encima de su
    peso, pesos que no son los de la rúbrica, ítems que faltan y denominadores que no
    cierran a la nota máxima.
    """
    lista = items if isinstance(items, list) else []
    pesos_norm = (
        {_normalizar_nombre(k): float(v) for k, v in pesos.items()}
        if isinstance(pesos, dict) and pesos
        else None
    )
    # Nombre original de cada criterio, indexado por su clave normalizada: el aviso
    # debe decir "marco_teorico" (lo que escribió el profesor), no una clave sin tildes.
    nombres_rubrica = (
        {_normalizar_nombre(k): str(k) for k in pesos} if pesos_norm else {}
    )

    suma_obtenido = 0.0
    suma_pesos = 0.0
    ilegibles = 0
    excedidos = 0
    n = 0
    criterios_vistos: dict[str, str] = {}
    pesos_distintos: list[str] = []
    fuera_de_rubrica: list[str] = []

    for item in lista:
        if not isinstance(item, dict):
            ilegibles += 1
            continue
        obtenido, denominador = _parsear_parcial(item.get("puntaje_parcial"))
        if obtenido is None:
            ilegibles += 1
            continue
        n += 1

        # La rúbrica es la autoridad del peso; el modelo solo aporta el cuánto Sacó.
        nombre_item = item.get("item") or item.get("criterio") or item.get("pregunta") or ""
        esperado = pesos_norm.get(_normalizar_nombre(nombre_item)) if pesos_norm else None
        if esperado is not None:
            criterios_vistos[_normalizar_nombre(nombre_item)] = str(nombre_item)
            if denominador is None:
                denominador = esperado
            elif abs(denominador - esperado) > 0.05:
                pesos_distintos.append(
                    f"{nombre_item} (modelo {denominador:g}, rúbrica {esperado:g})"
                )
                denominador = esperado

        suma_obtenido += obtenido
        if denominador and denominador > 0:
            suma_pesos += denominador
            if obtenido > denominador + 1e-9:
                excedidos += 1
                # No se puntúa por encima del máximo de ese ítem.
                suma_obtenido -= (obtenido - denominador)
            if pesos_norm is not None and _normalizar_nombre(nombre_item) not in pesos_norm:
                fuera_de_rubrica.append(str(nombre_item))

    # Ítems de la rúbrica que el modelo no devolvió. Es la diferencia entre "el alumno no
    # respondió el montaje" y "el modelo se comió un criterio": sin esto, ambas dan la
    # misma nota y solo una es verdad.
    ausentes: list[str] = []
    if pesos_norm:
        ausentes = sorted(
            nombres_rubrica[clave] for clave in nombres_rubrica
            if clave not in criterios_vistos
        )

    avisos: list[str] = []
    if ilegibles:
        avisos.append(
            f"Cálculo automático: {ilegibles} ítem(s) sin puntaje parcial legible; "
            "no participaron en la suma. Revisar si el modelo los omitió."
        )
    if excedidos:
        avisos.append(
            f"Cálculo automático: {excedidos} ítem(s) con parcial por encima de su propio "
            "peso; se recortaron al peso (un ítem no puede valer más que su máximo)."
        )
    if pesos_distintos:
        avisos.append(
            "Cálculo automático: el modelo cambió el peso de "
            f"{len(pesos_distintos)} criterio(s) respecto a la rúbrica: "
            + "; ".join(pesos_distintos[:6])
            + ". Se usó el peso de la rúbrica."
        )
    if ausentes:
        avisos.append(
            f"Cálculo automático: la rúbrica declara {len(pesos_norm)} criterios y el modelo "
            f"no devolvió {len(ausentes)} (" + ", ".join(ausentes[:8]) + "); puntúan 0 "
            "porque no hay evidencia de ellos. Si el informe sí los contiene, el modelo "
            "los omitió: revisar."
        )
    if fuera_de_rubrica:
        avisos.append(
            "Cálculo automático: puntuados "
            f"{len(fuera_de_rubrica)} ítem(s) que NO están en la rúbrica ("
            + ", ".join(sorted(set(fuera_de_rubrica))[:6])
            + "); usa el denominador que dio el modelo."
        )

    # ── De los parciales a la nota ─────────────────────────────────────────────
    # Con rúbrica, la escala la FIJA la rúbrica (los pesos suman `nota_maxima`, ya
    # validado al cargar). Da igual lo que el modelo diga: si se le olvidó un criterio,
    # ese criterio vale 0 y la escala sigue siendo 10. Al revés, si la escala se
    # tomara de los denominadores devueltos, omitir un criterio REDIRIGE la nota hacia
    # arriba (4.3 se convertía en 4.9 pornormalizar sobre 8.7): se bonificaba al
    # alumno por un fallo del modelo.
    #
    # Sin rúbrica (examen sin pesos) la escala la declara el propio modelo con sus
    # denominadores, y se normaliza a `nota_maxima`. Sumar en crudo solo sería
    # correcto si esa escala ya fuese 10.
    fiable = True
    escala = NOTA_MAXIMA
    if pesos_norm:
        escala = sum(pesos_norm.values())
        nota = suma_obtenido
        if abs(escala - nota_maxima) > 0.05:  # pragma: no cover - cargar_rubrica lo impide
            nota = nota_maxima * suma_obtenido / escala
    elif suma_pesos <= 0:
        # No hay rúbrica ni denominadores: la escala es indescifrable. Antes esto
        # publicaba la suma cruda como si fuera sobre 10, y un examen de 3 preguntas
        # puntuadas "0.5, 0.7, 0.3" salía 1.5/10 con cero avisos.
        fiable = False
        nota = 0.0
        escala = 0.0  # 0 = escala desconocida, que es exactamente el problema
        avisos.append(
            "Cálculo automático: SIN ESCALA FIABLE. Los ítems no traen denominador y esta "
            "evaluación no tiene rúbrica, así que no hay forma de saber sobre qué base "
            "están puntuados: la nota NO es publicable tal cual. Suma de lo que el modelo "
            f"devolvió: {suma_obtenido:.2f} (base desconocida). Repasar a mano o "
            "evaluar con rúbrica."
        )
    else:
        escala = suma_pesos
        if abs(suma_pesos - nota_maxima) > 0.05:
            nota = nota_maxima * suma_obtenido / suma_pesos
            avisos.append(
                f"Cálculo automático: los pesos de los ítems suman {suma_pesos:.2f} y la nota "
                f"máxima es {nota_maxima:g}; la nota se normalizó a {nota_maxima:g} "
                "(proporción obtenida/pesos), no se suman en crudo."
            )
        else:
            nota = suma_obtenido

    if not lista:
        avisos.append(
            "Cálculo automático: el modelo no devolvió ítems, así que la nota es 0. "
            "Revisar el JSON generado."
        )
        fiable = False

    # Techo absoluto: el máximo de la universidad. Ningún camino lo rebasa, ni aunque
    # el modelo devuelva una suma enorme o unos pesos inflados.
    techo = min(max(nota, 0.0), nota_maxima)

    datos = {
        "puntaje_sugerido": (
            f"{techo:.1f}/{nota_maxima:g}" if fiable else "No publicable"
        ),
        "nivel_desempeno": nivel_para_nota(techo) if fiable else "No publicable",
        "puntaje_numerico": round(techo, 2) if fiable else None,
        "maximo_alcanzable": nota_maxima,
        "items_legibles": n,
        "items_ausentes": ausentes,
        "nota_fiable": fiable,
        "escala_aplicada": round(escala, 2),
    }
    return datos, avisos

# Encabezado de la rúbrica cuando se concatena al prompt. Es texto CRUDO pegado al
# final del prompt, no configuración estructurada: por eso una clave mal escrita en
# una rúbrica no da error, simplemente el modelo la ignora. Ver AGENTS.md.
RUBRICA_ENCABEZADO = "## Rúbrica específica de este documento"


def componer_system_instruction(tipo: str, rubrica_texto: str | None = None) -> str:
    """
    Compone el System Instruction completo. PURA: mismo (tipo, rubrica) -> mismo
    string, siempre. No toca disco ni red; leer el fichero de la rúbrica es otra
    función (`leer_rubrica`), igual que separar la medición de la política.
    """
    if tipo not in TAREA_POR_TIPO:
        raise ValueError(
            f"Tipo de documento desconocido: {tipo!r}. Validos: {', '.join(TIPOS)}"
        )
    partes = [PERFIL_COMUN.strip(), TAREA_POR_TIPO[tipo].strip(), SCHEMA_SALIDA.strip()]
    if rubrica_texto:
        partes.append(f"{RUBRICA_ENCABEZADO}\n{rubrica_texto.strip()}")
    return "\n\n".join(partes)


# Alias histórico. Se conserva porque el resto del repo lo referencia, y porque un
# JSON ya generado debe seguir siendo legible.
SYSTEM_INSTRUCTION = componer_system_instruction("examen")


# ── Funciones de renderizado PDF ───────────────────────────────────────────────

def leer_rubrica(rubrica_path: str) -> str:
    """
    Lee el fichero de rúbrica y devuelve su TEXTO CRUDO, tal cual se concatena al prompt.

    Falla ruidosamente si no existe: una ruta mal escrita es un error de operador, no un
    caso de uso, y tragarse el error produciría una evaluación con el criterio por
    defecto sin que nadie lo notara.

    El texto se entrega sin parsear a propósito (el prompt lee prosa, no estructuras), pero
    eso no exime de VALIDAR: `cargar_rubrica` hace las dos cosas y esta es la mitad
    "solo texto" para las cosas que no necesitan pesos.
    """
    return cargar_rubrica(rubrica_path)[0]


def _normalizar_nombre(nombre: str) -> str:
    """
    Reduce un nombre de criterio a una clave comparable: minúsculas, sin acentos, sin
    separadores. Para que "Marco teórico", "marco_teorico" y "MARCO TEORICO" sean el
    mismo criterio al cruzar el JSON del modelo contra la rúbrica.
    """
    plano = unicodedata.normalize("NFKD", str(nombre).lower())
    sin_acentos = "".join(c for c in plano if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", sin_acentos)


def cargar_rubrica(rubrica_path: str) -> tuple[str, dict[str, float] | None]:
    """
    Lee la rúbrica y devuelve `(texto_crudo, pesos)`.

    `pesos` mapea nombre de criterio -> peso, y es `None` si la rúbrica no declara pesos
    (examen sin rúbrica, o rúbrica sin sección de pesos). El texto crudo sigue siendo lo
    que va al prompt: el modelo lee prosa; los pesos son para que el CÓDIGO pueda
    contrastar lo que el modelo devuelva.

    Por qué parsear además de concatenar: antes, una clave mal escrita en la rúbrica
    (`pesos:` en vez de `peso:`) llegaba al modelo, este no encontraba los pesos y se los
    inventaba. El resultado era una nota sobre una escala que nadie había escrito, sin un
    solo aviso. Un fichero de configuración que se entrega al modelo pero no se valida
    es un fichero que nadie está leyendo.

    Falla ruidosamente (`ValueError`) si la rúbrica declara pesos que no cierran o que no
    son numéricos: es un error de mantenimiento, no algo que el modelo pueda arreglar.
    """
    obj = Path(rubrica_path)
    if not obj.exists():
        raise FileNotFoundError(f"Rúbrica no encontrada: {rubrica_path}")
    texto = obj.read_text(encoding="utf-8")

    if yaml is None:  # pragma: no cover - degradación explícita, no silencio
        raise RuntimeError(
            "PyYAML no está instalado y la rúbrica no se puede validar. "
            "pip install PyYAML"
        )
    try:
        datos = yaml.safe_load(texto)
    except yaml.YAMLError as exc:  # pragma: no cover - depende del fichero
        raise ValueError(f"Rúbrica ilegible como YAML ({rubrica_path}): {exc}") from exc

    # Sin YAML legible (fichero vacío o texto plano): se entrega tal cual, sin pesos.
    if not isinstance(datos, dict):
        return texto, None

    criterios = datos.get("criterios", datos.get("criteria"))
    if criterios is None:
        return texto, None
    if not isinstance(criterios, dict) or not criterios:
        raise ValueError(
            f"Rúbrica con 'criterios' vacío o que no es un mapa ({rubrica_path}): "
            f"se recibió {type(criterios).__name__}"
        )

    pesos: dict[str, float] = {}
    for nombre, cuerpo in criterios.items():
        if not isinstance(cuerpo, dict):
            raise ValueError(
                f"Criterio '{nombre}' de la rúbrica no es un mapa ({rubrica_path}); "
                "cada criterio debe tener sus claves (peso, descripcion...)"
            )
        # Aceptar 'peso' y 'weight': el mismo concepto con dos idiomas, y una rúbrica
        # escrita en inglés no debería fallar por una palabra.
        bruto = cuerpo.get("peso", cuerpo.get("weight"))
        if bruto is None:
            raise ValueError(
                f"Criterio '{nombre}' de la rúbrica sin peso ni 'peso:' ({rubrica_path}). "
                f"Claves encontradas: {sorted(cuerpo)}. Sin pesos el modelo los inventa."
            )
        try:
            peso = float(bruto)
        except (TypeError, ValueError):
            raise ValueError(
                f"Peso del criterio '{nombre}' no numérico: {bruto!r} ({rubrica_path})"
            ) from None
        if peso <= 0:
            raise ValueError(
                f"Peso del criterio '{nombre}' es {peso}; debe ser > 0 ({rubrica_path})"
            )
        pesos[str(nombre)] = peso

    suma = sum(pesos.values())
    if abs(suma - NOTA_MAXIMA) > 0.05:
        # El error original: pesos que sumaban 11.5 sobre una base declarada de 10. Lo
        # queived de verdad era este número; ahora se dice al carregar la rúbrica.
        raise ValueError(
            f"Los pesos de la rúbrica suman {suma:.2f} y la nota máxima es {NOTA_MAXIMA:g} "
            f"({rubrica_path}). Ajusta los pesos para que cierren; el modelo normalizaría "
            "una escala rota y su nota no sería reproducible."
        )

    return texto, pesos


def pdf_to_images_bytes(pdf_path: str, dpi: int = 250) -> list[bytes]:
    """
    Renderiza cada página del PDF como PNG en memoria.
    Retorna lista de bytes PNG (una por página).
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        raise RuntimeError(f"No se pudo abrir el PDF '{pdf_path}': {e}")

    if len(doc) == 0:
        raise RuntimeError(f"El PDF '{pdf_path}' no contiene páginas.")

    zoom = dpi / 72.0  # 72 DPI es la resolución base de PDF
    mat = fitz.Matrix(zoom, zoom)
    images = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB, alpha=False)
        images.append(pix.tobytes("png"))

    doc.close()
    return images


# ── Funciones de extracción JSON ───────────────────────────────────────────────

def _find_balanced_json(text: str) -> str | None:
    """Encuentra el primer objeto JSON balanceado en el texto, respetando strings."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            if in_string:
                escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def extract_json_from_response(text: str) -> dict:
    """
    Intenta extraer el JSON de la respuesta del modelo.
    Maneja casos donde el modelo envuelva el JSON en bloques de código markdown.
    """
    # 1. Intentar parsear directamente toda la respuesta
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # 2. Buscar bloque ```json ... ``` y extraer todo su contenido
    match = re.search(r"```(?:json)?\s*(\{.*)\s*```", text, re.DOTALL)
    if match:
        candidate = _find_balanced_json(match.group(1))
        if candidate:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

    # 3. Buscar el primer objeto JSON balanceado en todo el texto
    candidate = _find_balanced_json(text)
    if candidate:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    raise ValueError("No se pudo extraer un JSON válido de la respuesta del modelo.")


# ── Pipeline con nuevo SDK (google-genai) ──────────────────────────────────────

def evaluar_con_nuevo_sdk(
    images_bytes: list[bytes],
    modelo: str,
    system_instruction: str,
    api_key: str,
) -> tuple[str, dict]:
    """Usa el SDK moderno google-genai."""
    client = genai.Client(api_key=api_key)

    # Construir contenidos multimodales
    contents = []
    for i, img_bytes in enumerate(images_bytes, start=1):
        contents.append(f"--- Página {i} de {len(images_bytes)} ---")
        contents.append(
            genai_types.Part.from_bytes(data=img_bytes, mime_type="image/png")
        )
    contents.append(
        "\nAnaliza el examen completo mostrado en las imágenes anteriores y responde con el JSON de evaluación."
    )

    response = client.models.generate_content(
        model=modelo,
        contents=contents,
        config=genai_types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2,
            max_output_tokens=8192,
            response_mime_type="application/json",
            # gemini-3.x+ gasta el presupuesto de salida en "thoughts" internos;
            # sin límite el JSON final se trunca (código 4). Forzar budget 0.
            thinking_config=genai_types.ThinkingConfig(
                thinking_budget=0,
                include_thoughts=False,
            ),
        ),
    )

    tokens = {}
    try:
        tokens = {
            "prompt": response.usage_metadata.prompt_token_count,
            "respuesta": response.usage_metadata.candidates_token_count,
            "total": response.usage_metadata.total_token_count,
        }
    except (AttributeError, TypeError):
        pass

    return response.text, tokens


# ── Pipeline con SDK legacy (google-generativeai) ──────────────────────────────

def evaluar_con_sdk_legacy(
    images_bytes: list[bytes],
    modelo: str,
    system_instruction: str,
    api_key: str,
) -> tuple[str, dict]:
    """Usa el SDK legacy google-generativeai como fallback."""
    import warnings
    warnings.filterwarnings("ignore")  # Suprimir FutureWarnings del SDK deprecated

    _genai_legacy.configure(api_key=api_key)

    model = _genai_legacy.GenerativeModel(
        model_name=modelo,
        system_instruction=system_instruction,
        generation_config=_genai_legacy_types.GenerationConfig(
            temperature=0.2,
            top_p=0.95,
            max_output_tokens=8192,
            response_mime_type="application/json",
        ),
    )

    parts = []
    for i, img_bytes in enumerate(images_bytes, start=1):
        parts.append(f"--- Página {i} de {len(images_bytes)} ---")
        parts.append(_genai_legacy_types.Part.from_bytes(
            data=img_bytes, mime_type="image/png"
        ))
    parts.append(
        "\nAnaliza el examen completo mostrado en las imágenes anteriores y responde con el JSON de evaluación."
    )

    response = model.generate_content(parts)

    tokens = {}
    try:
        tokens = {
            "prompt": response.usage_metadata.prompt_token_count,
            "respuesta": response.usage_metadata.candidates_token_count,
            "total": response.usage_metadata.total_token_count,
        }
    except (AttributeError, TypeError):
        pass

    return response.text, tokens


# ── Pipeline con OpenRouter (API compatible con OpenAI) ─────────────────────────

def evaluar_con_openrouter(
    images_bytes: list[bytes],
    modelo: str,
    system_instruction: str,
    api_key: str,
) -> tuple[str, dict]:
    """Evalúa usando OpenRouter (API compatible con OpenAI)."""
    labels = [f"Página {i} de {len(images_bytes)}" for i in range(1, len(images_bytes) + 1)]
    user_content = build_multimodal_content(
        images_bytes,
        labels=labels,
        trailing_text="Analiza el examen completo mostrado en las imágenes anteriores y responde con el JSON de evaluación.",
    )
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": user_content},
    ]
    return openrouter_chat(
        messages,
        modelo,
        api_key,
        temperature=0.2,
        max_tokens=8192,
        title="ELECTRONICA - Evaluacion de Examenes",
    )


def evaluar_con_groq(
    images_bytes: list[bytes],
    modelo: str,
    system_instruction: str,
    api_key: str,
) -> tuple[str, dict]:
    """Evalúa usando Groq (API compatible con OpenAI)."""
    import base64
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )

    user_content = []
    for i, img_bytes in enumerate(images_bytes, start=1):
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        user_content.append({
            "type": "text",
            "text": f"--- Página {i} de {len(images_bytes)} ---",
        })
        user_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{b64}",
                "detail": "high",
            },
        })
    user_content.append({
        "type": "text",
        "text": "Analiza el examen completo mostrado en las imágenes anteriores y responde con el JSON de evaluación.",
    })

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": user_content},
    ]

    response = client.chat.completions.create(
        model=modelo,
        messages=messages,
        temperature=0.2,
        max_tokens=8192,
        response_format={"type": "json_object"},
    )

    tokens = {}
    try:
        if hasattr(response, 'usage') and response.usage:
            tokens = {
                "prompt": response.usage.prompt_tokens,
                "respuesta": response.usage.completion_tokens,
                "total": response.usage.total_tokens,
            }
    except (AttributeError, TypeError):
        pass

    if not response or not hasattr(response, 'choices') or not response.choices:
        raise RuntimeError(f"El modelo no devolvió una respuesta válida. Es probable que no soporte imágenes o esté caído en Groq.")

    choice = response.choices[0]
    if not choice.message or choice.message.content is None:
        raise RuntimeError(f"El modelo devolvió un mensaje vacío. Verifica si el modelo '{modelo}' soporta multimodalidad en Groq.")

    return choice.message.content, tokens


def evaluar_con_huggingface(
    images_bytes: list[bytes],
    modelo: str,
    system_instruction: str,
    api_key: str,
) -> tuple[str, dict]:
    """Evalúa usando Hugging Face Inference Providers (API compatible con OpenAI)."""
    import base64
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url="https://router.huggingface.co/v1",
    )

    user_content = []
    for i, img_bytes in enumerate(images_bytes, start=1):
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        user_content.append({
            "type": "text",
            "text": f"--- Página {i} de {len(images_bytes)} ---",
        })
        user_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{b64}",
                "detail": "high",
            },
        })
    user_content.append({
        "type": "text",
        "text": "Analiza el examen completo mostrado en las imágenes anteriores y responde con el JSON de evaluación.",
    })

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": user_content},
    ]

    response = client.chat.completions.create(
        model=modelo,
        messages=messages,
        temperature=0.2,
        max_tokens=8192,
        response_format={"type": "json_object"},
    )

    tokens = {}
    try:
        if hasattr(response, 'usage') and response.usage:
            tokens = {
                "prompt": response.usage.prompt_tokens,
                "respuesta": response.usage.completion_tokens,
                "total": response.usage.total_tokens,
            }
    except (AttributeError, TypeError):
        pass

    if not response or not hasattr(response, 'choices') or not response.choices:
        raise RuntimeError(f"El modelo no devolvió una respuesta válida. Es probable que no soporte imágenes o esté caído en Hugging Face.")

    choice = response.choices[0]
    if not choice.message or choice.message.content is None:
        raise RuntimeError(f"El modelo devolvió un mensaje vacío. Verifica si el modelo '{modelo}' soporta multimodalidad (visión) en Hugging Face.")

    return choice.message.content, tokens


# ── Orquestador principal ──────────────────────────────────────────────────────

def evaluar_examen(
    pdf_path: str,
    modelo: str,
    dpi: int,
    rubrica_path: str | None,
    api_key: str,
    api_backend: str = "gemini",
    tipo: str = "examen",
) -> dict:
    """Orquesta el pipeline completo de evaluación."""

    # ── 1. Renderizar PDF ──────────────────────────────────────────────────────
    images_bytes = pdf_to_images_bytes(pdf_path, dpi=dpi)

    # ── 2. Construir System Instruction (tipo + rúbrica opcional) ───────────────
    # El tipo se valida ANTES de cualquier llamada: un `--tipo` inválido no puede
    # costar una API.
    if tipo not in TAREA_POR_TIPO:
        raise ValueError(
            f"Tipo de documento desconocido: {tipo!r}. Validos: {', '.join(TIPOS)}"
        )
    # La rúbrica se lee una vez y en dos formatos: el TEXTO va al prompt y los PESOS se
    # quedan aquí para que `calcular_nota` pueda contrastar lo que devuelva el modelo. No
    # es solo un accessor: la validación de que los pesos cierren a 10 ocurre al leer.
    rubrica_texto, pesos_rubrica = cargar_rubrica(rubrica_path) if rubrica_path else (None, None)
    system_instruction = componer_system_instruction(tipo, rubrica_texto)

    # ── 3. Llamar al modelo según backend ──────────────────────────────────────
    def _llamar_modelo():
        if api_backend == "huggingface":
            return evaluar_con_huggingface(
                images_bytes, modelo, system_instruction, api_key
            )
        if api_backend == "openrouter":
            return evaluar_con_openrouter(
                images_bytes, modelo, system_instruction, api_key
            )
        if api_backend == "groq":
            return evaluar_con_groq(
                images_bytes, modelo, system_instruction, api_key
            )
        if _GENAI_SDK == "new":
            return evaluar_con_nuevo_sdk(
                images_bytes, modelo, system_instruction, api_key
            )
        return evaluar_con_sdk_legacy(
            images_bytes, modelo, system_instruction, api_key
        )

    # ── 4. Extraer y validar JSON (con reintentos) ─────────────────────────────
    # gemini-3.x a veces entrega JSON truncado o con llaves duplicadas.
    # Retry budget: máximo 3 intentos antes de fallar.
    response_text, tokens, evaluacion_dict = "", {}, None
    MAX_REINTENTOS = 3
    for intento in range(1, MAX_REINTENTOS + 1):
        response_text, tokens = _llamar_modelo()
        try:
            evaluacion_dict = extract_json_from_response(response_text)
            break
        except ValueError:
            if intento == MAX_REINTENTOS:
                raise ValueError(
                    "No se pudo extraer un JSON válido de la respuesta del modelo "
                    f"tras {MAX_REINTENTOS} intentos."
                )
    if evaluacion_dict is None:
        raise ValueError("No se pudo extraer un JSON válido de la respuesta del modelo.")

    # ── 5. Calcular la nota (determinista, no la decide el modelo) ─────────────
    # Si el modelo emittera `puntaje_sugerido` / `nivel_desempeno` (aun sin pedírselo,
    # los modelos tiende a añadirlos), se sobrescriben aquí. Prefijar la nota no es
    # opcional: si un JSON viejo llega con un total inventado, el informe lo mostraría.
    evaluacion_dict = dict(evaluacion_dict)
    evaluacion_dict.pop("puntaje_sugerido", None)
    evaluacion_dict.pop("nivel_desempeno", None)

    # Se aceptan las dos grafías de la clave de ítems: `observaciones_por_item` es la
    # canónica, `observaciones_por_pregunta` la histórica (ver `generar_informe.py`).
    clave_items = next(
        (c for c in ("observaciones_por_item", "observaciones_por_pregunta")
         if isinstance(evaluacion_dict.get(c), list)),
        "observaciones_por_item",
    )
    nota, avisos = calcular_nota(evaluacion_dict.get(clave_items), pesos=pesos_rubrica)

    # Los avisos van al campo que el profesor lee, no a un canal aparte: si el cálculo
    # automático tuvo que recortar, limar o ignorar algo, el humano tiene que saberlo.
    if avisos:
        nota_profesor = str(evaluacion_dict.get("nota_para_el_profesor") or "").strip()
        bloque = " ".join(avisos)
        evaluacion_dict["nota_para_el_profesor"] = (
            f"{nota_profesor} [{bloque}]" if nota_profesor else f"[{bloque}]"
        )

    evaluacion_dict.update(nota)

    # ── 6. Construir resultado final ───────────────────────────────────────────
    nombre_estudiante = (
        Path(pdf_path).stem
        .replace("evaluacion_", "")
        .replace("examen_", "")
        .replace("_", " ")
    )

    result = {
        "status": "ok",
        "api_backend": api_backend,
        "estudiante": nombre_estudiante,
        "archivo": str(Path(pdf_path).resolve()),
        "modelo": modelo,
        "dpi_renderizado": dpi,
        "paginas_procesadas": len(images_bytes),
        "evaluacion": evaluacion_dict,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "tipo": tipo,
    }

    if tokens:
        result["tokens_usados"] = tokens

    return result


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Evalúa exámenes de Electrónica con LLM multimodal.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 execution/evaluar_examen.py --pdf examenes/01/examen_estudiantes/entrega_alumno.pdf
  python3 execution/evaluar_examen.py --pdf <ruta> --modelo gemini-1.5-pro --dpi 300
  python3 execution/evaluar_examen.py --pdf <ruta> --api-backend openrouter --modelo qwen/qwen-2.5-vl-72b-instruct:free
  python3 execution/evaluar_examen.py --pdf <ruta> --api-backend huggingface --modelo Qwen/Qwen2.5-VL-72B-Instruct:cheapest
        """,
    )
    parser.add_argument(
        "--pdf",
        required=True,
        help="Ruta al archivo PDF del examen del estudiante.",
    )
    parser.add_argument(
        "--modelo",
        default="gemini-2.5-flash",
        help="Modelo a usar (default: gemini-2.5-flash). Con --api-backend openrouter usa IDs de OpenRouter.",
    )
    parser.add_argument(
        "--api-backend",
        default="gemini",
        choices=["gemini", "openrouter", "groq", "huggingface"],
        help="Backend de API a usar: gemini, openrouter, groq o huggingface. (default: gemini).",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=250,
        help="Resolución de renderizado del PDF en DPI (default: 250). Rango recomendado: 150-300.",
    )
    parser.add_argument(
        "--tipo",
        default="examen",
        choices=["examen", "laboratorio"],
        help="Tipo de documento a evaluar (default: examen): 'examen' o 'laboratorio'.",
    )
    parser.add_argument(
        "--rubrica",
        default=None,
        help="(Opcional) Ruta a un archivo YAML o TXT con la rúbrica específica del documento.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # ── Validar PDF ────────────────────────────────────────────────────────────
    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(json.dumps({
            "status": "error", "code": 1,
            "message": f"PDF no encontrado: {args.pdf}"
        }))
        sys.exit(1)

    if pdf_path.suffix.lower() != ".pdf":
        print(json.dumps({
            "status": "error", "code": 1,
            "message": f"El archivo no es un PDF: {args.pdf}"
        }))
        sys.exit(1)

    # ── Validar DPI ────────────────────────────────────────────────────────────
    if not (72 <= args.dpi <= 600):
        print(json.dumps({
            "status": "error", "code": 1,
            "message": f"DPI fuera de rango. Usa un valor entre 72 y 600. Recibido: {args.dpi}"
        }))
        sys.exit(1)

    # ── Validar SDK según backend ──────────────────────────────────────────────
    if args.api_backend in ["openrouter", "groq", "huggingface"]:
        if not _OPENROUTER_AVAILABLE:
            print(json.dumps({
                "status": "error", "code": 1,
                "message": "SDK de OpenAI no instalado. Ejecuta: pip install openai"
            }))
            sys.exit(1)
    elif args.api_backend == "gemini":
        if not _GEMINI_AVAILABLE:
            print(json.dumps({
                "status": "error", "code": 1,
                "message": "SDK de Gemini no instalado. Ejecuta: pip install google-genai"
            }))
            sys.exit(1)

    # ── Obtener API Key según backend ──────────────────────────────────────────
    if args.api_backend == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        key_name = "OPENROUTER_API_KEY"
    elif args.api_backend == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            try:
                with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".groq_api_key"), "r") as f:
                    api_key = f.read().strip()
            except Exception:
                pass
        key_name = "GROQ_API_KEY"
    elif args.api_backend == "huggingface":
        api_key = os.getenv("HF_TOKEN")
        key_name = "HF_TOKEN"
    else:
        api_key = os.getenv("GOOGLE_API_KEY")
        key_name = "GOOGLE_API_KEY"

    if not api_key:
        print(json.dumps({
            "status": "error", "code": 2,
            "message": (
                f"API key no encontrada. Define {key_name} "
                "en tu archivo .env o como variable de entorno."
            )
        }))
        sys.exit(2)

    # ── Ejecutar evaluación ────────────────────────────────────────────────────
    try:
        result = evaluar_examen(
            pdf_path=str(pdf_path),
            modelo=args.modelo,
            dpi=args.dpi,
            rubrica_path=args.rubrica,
            tipo=args.tipo,
            api_key=api_key,
            api_backend=args.api_backend,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)

    except FileNotFoundError as e:
        print(json.dumps({"status": "error", "code": 1, "message": str(e)}))
        sys.exit(1)

    except RuntimeError as e:
        print(json.dumps({"status": "error", "code": 3, "message": str(e)}))
        sys.exit(3)

    except ValueError as e:
        print(json.dumps({"status": "error", "code": 4, "message": str(e)}))
        sys.exit(4)

    except Exception as e:
        error_type = type(e).__name__
        print(json.dumps({
            "status": "error", "code": 2,
            "message": f"Error de API ({error_type}): {str(e)}"
        }))
        sys.exit(2)


if __name__ == "__main__":
    main()
