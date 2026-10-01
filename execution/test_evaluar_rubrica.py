#!/usr/bin/env python3
"""Pruebas de regresion de la rúbrica de evaluacion (execution/evaluar_examen.py).

Por qué existe este fichero: una vez la directiva `evaluar_practica_laboratorio.yaml`
prometió en su `expected_output` una clave `observaciones_por_seccion` que el prompt
NO producía (producía `observaciones_por_pregunta`), y `generar_informe.py` solo leía
esa segunda. El resultado era silencioso: el PDF de una práctica salía titulado
"Evaluación de Exámenes" y, si el modelo obedecía a la directiva, con la tabla de
observaciones vacía. Nadie lo notó porque NADIE comparaba lo que la directiva
prometía con lo que el prompt emitía.

Cinco objetivos, cada uno fijando un fallo concreto:

1. COHERENCIA DIRECTIVA<->PROMPT: toda clave nombrada en el `expected_output` de las
   directivas de evaluación existe en el contrato de salida real. Esta es la aserción
   que habría atrapado el bug original.

2. EL CONTRATO TOP-LEVEL es el declarado: las claves que emite el script son
   exactamente las que el test considera públicas (y ni una más de la nada).

3. UN SOLO SCHEMA para los dos tipos de documento. El schema de salida NO se parte por
   tipo: solo cambia el vocabulario y el encuadre de la tarea. Si algún día alguien
   lo parte, esta aserción falla y obliga a explicar la decisión.

4. EL TIPO DE DOCUMENTO se elige por flag explícito (`--tipo`), no por adivinar el
   contenido del YAML: la decisión es función pura de la entrada, y un `--tipo`
   inválido se rechaza ANTES de gastar una llamada a la API.

5. LA RUBRICA se concatena literal (es texto crudo, no configuración estructurada) y
   una rúbrica inexistente falla ruidosamente. Además, el resultado es determinista.

Ejecutar: python3 execution/test_evaluar_rubrica.py
Salida:  0 si todas pasan, 1 si alguna falla.

Ningún test de este fichero llama a una API: se importan constantes y se compone el
prompt en local, que es exactamente la parte que hay que fijar.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "execution"))

FALLOS: list[str] = []
PRUEBAS = 0

SCRIPT = RAIZ / "execution" / "evaluar_examen.py"
INFORME = RAIZ / "execution" / "generar_informe.py"
DIRECTIVAS_EVALUACION = [
    RAIZ / "directives" / "evaluar_examen_estudiante.yaml",
    RAIZ / "directives" / "evaluar_practica_laboratorio.yaml",
]

# Claves publicas del nivel superior del JSON de salida. Es el CONTRATO declarado:
# el test 2 comprueba que el script emite exactamente estas y nada mas.
TOP_LEVEL = {
    "status", "api_backend", "estudiante", "archivo", "modelo",
    "dpi_renderizado", "paginas_procesadas", "evaluacion",
    "timestamp", "tokens_usados", "tipo",
}

# Palabras que aparecen en la prosa del `expected_output` pero no son claves.
STOPLIST_PROSA = {
    "json", "claves", "con", "para", "por", "una", "uno", "los", "las",
    "del", "este", "esta", "tipo", "documento", "salida",
}


def comprobar(nombre: str, condicion: bool, detalle: str = "") -> None:
    global PRUEBAS
    PRUEBAS += 1
    if condicion:
        print(f"  ok   {nombre}")
    else:
        print(f"  FALLA {nombre}" + (f" -- {detalle}" if detalle else ""))
        FALLOS.append(nombre)


def importar_evaluar_examen():
    """Importa el modulo sin ejecutar `main()` (esta guardado tras __main__)."""
    import evaluar_examen as mod
    return mod


# ── Extraccion del contrato de salida ──────────────────────────────────────────

def bloque_json_de_schema(mod) -> str:
    """
    Devuelve el bloque ```json del contrato de salida.

    Antes de partir el prompt vivia dentro de `SYSTEM_INSTRUCTION`; despues sera la
    constante `SCHEMA_SALIDA`. Se aceptan las dos formas para que este test pueda
    correr contra el codigo viejo (y demostrar el bug) y contra el nuevo.
    """
    # Tras partir el prompt, el schema vive en SCHEMA_SALIDA; antes estaba
    # incrustado en SYSTEM_INSTRUCTION. En ambos casos lo que se busca es el bloque
    # ```json, porque la constante tambien lleva la prosa que lo introduce.
    for constante in ("SCHEMA_SALIDA", "SYSTEM_INSTRUCTION"):
        texto = getattr(mod, constante, "")
        if not texto:
            continue
        m = re.search(r"```json\s*(\{.*?\})\s*```", texto, re.DOTALL)
        if m:
            return m.group(1)
    return ""


def claves_del_schema(mod) -> set[str] | None:
    """Claves de primer nivel del JSON de salida, o None si no se pudo leer."""
    crudo = bloque_json_de_schema(mod)
    if not crudo:
        return None
    try:
        return set(json.loads(crudo).keys())
    except json.JSONDecodeError:
        return None


def claves_mencionadas_en_directiva(path: Path) -> set[str]:
    """
    Extrae los identificadores snake_case que una directiva nombra tras "claves:".

    El `expected_output` de las directivas esta escrito en prosa
    ("JSON con las claves: status, estudiante, ... evaluacion (con
    observaciones_por_seccion, ...), tokens_usados, timestamp."), no como estructura.
    Por eso esto es un extractor heuristico y recortado al primer `expected_output`,
    no un parser de YAML: el objetivo es pillar la deriva, no validar la redaccion.
    """
    texto = path.read_text(encoding="utf-8")
    i = texto.find("claves:")
    if i < 0:
        return set()
    cuerpo = texto[i + len("claves:"):]
    # Recortar en el siguiente bloque de la directiva para no arrastrar edge_cases.
    cortes = [c for c in (cuerpo.find("\n  - step:"),
                          cuerpo.find("\nedge_cases:"),
                          cuerpo.find("\nexpected_outputs:")) if c >= 0]
    if cortes:
        cuerpo = cuerpo[:min(cortes)]
    return {t for t in re.findall(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)*\b", cuerpo)
            if len(t) >= 4 and t not in STOPLIST_PROSA}


# ── 1. Coherencia entre lo que promete la directiva y lo que emite el prompt ──

def test_coherencia_directiva_prompt() -> None:
    mod = importar_evaluar_examen()
    schema = claves_del_schema(mod)
    comprobar("el contrato de salida se puede leer como JSON", schema is not None,
              "no se encontro ningun bloque ```json en el prompt")
    if schema is None:
        return

    conocidas = schema | TOP_LEVEL
    for directiva in DIRECTIVAS_EVALUACION:
        if not directiva.exists():
            comprobar(f"{directiva.name} existe", False, "directiva no encontrada")
            continue
        declaradas = claves_mencionadas_en_directiva(directiva)
        comprobar(f"{directiva.name} nombra claves", bool(declaradas),
                  "no se encontro ninguna clave tras 'claves:'")
        huerfanas = declaradas - conocidas
        comprobar(f"{directiva.name} no promete claves inexistentes", not huerfanas,
                  "la directiva nombra claves que el prompt NO emite: "
                  + ", ".join(sorted(huerfanas)))


# ── 2. El contrato top-level es el declarado ───────────────────────────────────

def test_contrato_top_level() -> None:
    fuente = SCRIPT.read_text(encoding="utf-8")
    m = re.search(r"result\s*=\s*\{(.*?)\n    \}", fuente, re.DOTALL)
    comprobar("se encuentra el dict `result` en el script", m is not None)
    if m is None:
        return
    emitidas = set(re.findall(r'"([a-z_]+)"\s*:', m.group(1)))
    # `tokens_usados` se anade en bloque aparte (solo si hay tokens).
    emitidas.add("tokens_usados")
    comprobar("el script emite todas las claves top-level declaradas",
              not (TOP_LEVEL - emitidas),
              "faltan: " + ", ".join(sorted(TOP_LEVEL - emitidas)))
    comprobar("el script no emite claves top-level no declaradas",
              not (emitidas - TOP_LEVEL),
              "sobran: " + ", ".join(sorted(emitidas - TOP_LEVEL)))


# ── 3. Un solo schema para los dos tipos de documento ──────────────────────────

def test_schema_unico() -> None:
    mod = importar_evaluar_examen()
    componer = getattr(mod, "componer_system_instruction", None)
    comprobar("existe componer_system_instruction (composicion pura)",
              componer is not None,
              "aun no se partio el prompt por tipo de documento")
    if componer is None:
        return

    schema = getattr(mod, "SCHEMA_SALIDA", "")
    comprobar("existe la constante SCHEMA_SALIDA como fuente unica",
              bool(schema.strip()),
              "el schema debe vivir en una constante, no incrustado en el prompt")

    # `componer_system_instruction` normaliza con .strip(), asi que se compara igual.
    for tipo in ("examen", "laboratorio"):
        comprobar(f"{tipo}: incluye el schema canonico",
                  schema.strip() in componer(tipo, None),
                  "el schema no llego al prompt compuesto")

    # El vocabulario del encuadre SI debe cambiar: ese es el punto de partirlo.
    examen = componer("examen", None)
    laboratorio = componer("laboratorio", None)

    def _bloque_tarea(prompt: str) -> str:
        """El encuadre de la tarea de un prompt compuesto."""
        if "## Tu tarea" not in prompt:
            return prompt
        return prompt.split("## Tu tarea")[-1].split("\n## ")[0].lower()

    # El encuadre de 'laboratorio' dice "no una pregunta" para marcar la diferencia,
    # asi que la asercion mira que NO llame "pregunta" a la UNIDAD (los items), no que
    # la palabra no aparezca nunca.
    tarea_examen = _bloque_tarea(examen)
    tarea_lab = _bloque_tarea(laboratorio)
    comprobar("'examen' nombra la pregunta como unidad a evaluar",
              "identificar cada pregunta" in tarea_examen)
    comprobar("'laboratorio' nombra la sección como unidad a evaluar",
              "identificar cada secci" in tarea_lab)
    comprobar("'laboratorio' no pide identificar preguntas",
              "identificar cada pregunta" not in tarea_lab,
              "el encuadre de laboratorio debe pedir secciones, no preguntas")


# ── 4. El tipo se elige por flag explicito y se valida antes de la API ─────────

def test_flag_tipo() -> None:
    """
    El tipo debe distinguirse de "no existe el flag". Un test que solo comprueba
    `returncode != 0` pasa por los dos motivos posibles y no prueba NADA: hoy, sin
    `--tipo`, argparse rechaza `--tipo invalido` como argumento desconocido y el
    test sale verde sobre codigo roto. Por eso se mira el motivo del rechazo.
    """
    # 1) Un valor FUERA de choices se rechaza por ser choice invalida, no por
    #    ser un flag desconocido. La razon la dice argparse en stderr.
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--pdf", "/dev/null", "--tipo", "invalido"],
        cwd=RAIZ, capture_output=True, text=True, timeout=120,
    )
    combinado = proc.stdout + proc.stderr
    comprobar("un --tipo invalido se rechaza", proc.returncode != 0,
              f"codigo {proc.returncode}: deberia fallar")
    comprobar("el rechazo de --tipo es por choice, no por flag desconocido",
              "invalid choice" in combinado and "unrecognized arguments" not in combinado,
              "argparse no se quejaron de la choice: el flag quizas no existe")

    # 2) Un valor VALIDO debe pasar argparse y morir en la validacion del PDF, que
    #    ocurre ANTES de cualquier llamada a la API (asi que esto no gasta nada).
    for tipo in ("examen", "laboratorio"):
        ok = subprocess.run(
            [sys.executable, str(SCRIPT), "--pdf", "/no/existe.pdf", "--tipo", tipo],
            cwd=RAIZ, capture_output=True, text=True, timeout=120,
        )
        comprobar(f"--tipo {tipo} es una opcion valida",
                  ok.returncode == 1 and "PDF no encontrado" in ok.stdout,
                  f"codigo {ok.returncode}; deberia ser 1 por PDF ausente")

    # 3) El default (sin --tipo) debe seguir siendo 'examen'.
    ayuda = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=RAIZ, capture_output=True, text=True, timeout=120,
    )
    comprobar("--tipo aparece en la ayuda", "--tipo" in ayuda.stdout)
    comprobar("la ayuda declara examen como default",
              "default: examen" in ayuda.stdout.replace("\n", " ").replace("  ", " "))


# ── 5. La rubrica es texto crudo appended, y falla si no existe ───────────────

def test_rubrica_literal_y_ruidosa() -> None:
    mod = importar_evaluar_examen()
    componer = getattr(mod, "componer_system_instruction", None)
    comprobar("existe componer_system_instruction (para la rubrica)",
              componer is not None,
              "aun no se partio el prompt por tipo de documento")
    if componer is None:
        return

    rubrica = "criterios:\n  demo:\n    peso: 1.0\n"
    con_rubrica = componer("examen", rubrica)
    # `componer_system_instruction` normaliza la rubrica con .strip() al pegarla, asi
    # que el whitespace final no debe contar como alteracion del contenido.
    comprobar("la rubrica se concatena literal", rubrica.strip() in con_rubrica,
              "el texto de la rubrica no llego intacto al prompt")
    comprobar("sin rubrica el prompt es menor",
              len(con_rubrica) > len(componer("examen", None)))

    # Determinismo: misma entrada, mismo prompt. Sin esto, dos corridas del mismo
    # examen podrian dar notas distintas y el flujo deja de ser reproducible.
    comprobar("la composicion es determinista",
              componer("examen", rubrica) == con_rubrica)


def test_rubrica_inexistente_falla_ruidosamente() -> None:
    """
    La validacion de la RUTA vive en `leer_rubrica`, separada de la composicion
    (que es pura). Una rubrica mal escrita no es un caso de uso: es un error de
    operador, y tiene que exiting con codigo != 0 y no rendirse en silencio.
    """
    mod = importar_evaluar_examen()
    leer = getattr(mod, "leer_rubrica", None)
    comprobar("existe leer_rubrica(path)", leer is not None,
              "la lectura/validacion de la rubrica debe ser una funcion propia")
    if leer is None:
        return

    inexistente = RAIZ / "directives" / "rubricas" / "no_existe_esta_rubrica.yaml"
    comprobar("el fixture de prueba no existe de verdad", not inexistente.exists(),
              "no se puede probar el fallo si el fichero existe")
    lanzo = False
    try:
        leer(str(inexistente))
    except FileNotFoundError:
        lanzo = True
    comprobar("una rubrica inexistente lanza FileNotFoundError", lanzo,
              "se esperaba FileNotFoundError, no un silencio")

    real = RAIZ / "directives" / "rubricas" / "rubrica_practica_lab.yaml"
    comprobar("leer_rubrica devuelve el texto de la rubrica real",
              leer(str(real)).lstrip().startswith("#"),
              "no devolvio el contenido del YAML")


def test_informe_acepta_ambas_grafias() -> None:
    """
    `generar_informe.py` debe leer la clave nueva y la vieja (compat), para que un
    JSON ya generado en .tmp/ siga rindiendo informe.
    """
    fuente = INFORME.read_text(encoding="utf-8")
    for clave in ("observaciones_por_item", "observaciones_por_pregunta"):
        comprobar(f"generar_informe.py conoce {clave}", clave in fuente,
                  "el informe no menciona esa clave; un JSON con ella daria tabla vacia")
    # El texto de tabla vacia debe SEGUIR AL TIPO. La asercion no busca la frase
    # prohibida (que si aparece: es la rama del examen, y es correcta ahi), sino que
    # exista la rama de laboratorio Y que ambas esten elegidas por `tipo_doc`. Un
    # informe que dijera "no hay observaciones por pregunta" sobre una practica
    # seria la manifestacion visible de esta deriva.
    comprobar("el mensaje de vacio tiene rama de laboratorio",
              "observaciones por sección" in fuente,
              "falta el mensaje para tipo laboratorio")
    comprobar("el mensaje de vacio se elige por tipo de documento",
              re.search(r"tipo_doc\s*==\s*[\"']laboratorio[\"']", fuente) is not None,
              "el mensaje no depende de data['tipo']: quedaria cableado al examen")


def test_informe_rotulo_por_tipo() -> None:
    """
    El ENCABEZADO del PDF tambien debe seguir al tipo. "Informe de Evaluación" a
    secas era el rotulo original, pensado para exámenes: correcto entonces, pero
    es exactamente el texto que delata la deriva cuando lo que se evalúa es una
    práctica. Se comprueba sobre el TEXTO RENDERIZADO, no sobre el fuente: mirar
    el fuente exigiría adivinar cómo se concatena la variable, y un informe que
    dijera "Informe de Evaluación" sobre una práctica es la manifestación
    visible de esa deriva (es lo que se vio en la primera prueba real).
    """
    sys.path.insert(0, str(RAIZ / "execution"))
    import generar_informe as gi

    def encabezado(data: dict) -> str:
        return gi.generar_latex(data)

    comun = {"estudiante": "X", "modelo": "m", "paginas_procesadas": 1,
             "evaluacion": {"nivel_desempeno": "bueno"}}
    lab = encabezado({**comun, "tipo": "laboratorio"})
    exa = encabezado({**comun, "tipo": "examen"})

    # Se aísla la LÍNEA del encabezado de página. Comprobar `"Práctica" in lab`
    # sobre el informe entero daba verde por el motivo equivocado: el título de
    # portada ya decía "Informes de Práctica" y Bastaba para que la aserción
    # pasara aunque el encabezado de cada página siguiera diciendo
    # "Informe de Evaluación" — que es justo el texto que se quería cambiar.
    def rotulo_pagina(tex: str) -> str:
        # Se ancla en el FINAL del rotulo ("--- Electrónica}") y no en un cierre de
        # llave: el interior lleva \small\color{azulNoche}, que ya tiene llaves, así
        # que cualquier `[^}]*` trunca antes de tiempo.
        m = re.search(r"\\fancyhead\[L\]\{.*?--- Electrónica\}", tex, re.S)
        return m.group(0) if m else ""

    rot_lab, rot_exa = rotulo_pagina(lab), rotulo_pagina(exa)
    comprobar("se encuentra el encabezado de pagina en ambas ramas",
              bool(rot_lab) and bool(rot_exa),
              f"no se localizo \\fancyhead[L] (lab={rot_lab[:60]!r})")
    comprobar("el encabezado de pagina distingue practica",
              "Práctica" in rot_lab,
              f"el encabezado de pagina de una practica no se distingue: {rot_lab[:90]!r}")
    comprobar("el encabezado de pagina de examen no menciona practica",
              "Práctica" not in rot_exa,
              f"se coló el rotulo de practica en la rama de examen: {rot_exa[:90]!r}")
    comprobar("el encabezado de pagina de examen se mantiene",
              "Informe de Evaluación" in rot_exa,
              f"se rompió el rotulo que ya funcionaba para exámenes: {rot_exa[:90]!r}")
    comprobar("ambos encabezados comparten el sufijo de la asignatura",
              "Electrónica" in rot_lab and "Electrónica" in rot_exa,
              "el sufijo Electronica debe sobrevivir en las dos ramas")


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    print("Pruebas de rúbrica / tipo de documento (evaluar_examen.py)")
    print("=" * 62)
    test_coherencia_directiva_prompt()
    test_contrato_top_level()
    test_schema_unico()
    test_flag_tipo()
    test_rubrica_literal_y_ruidosa()
    test_rubrica_inexistente_falla_ruidosamente()
    test_informe_acepta_ambas_grafias()
    test_informe_rotulo_por_tipo()

    print()
    if FALLOS:
        print(f"FALLOS: {len(FALLOS)}/{PRUEBAS}")
        for f in FALLOS:
            print(f"  - {f}")
        return 1
    print(f"Aserciones OK: {PRUEBAS}   Fallos: 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())