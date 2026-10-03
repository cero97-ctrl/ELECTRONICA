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

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - el entorno del repo trae PyYAML
    yaml = None

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
    "json", "claves", "clave", "con", "para", "por", "una", "uno", "los", "las",
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
    # Recortar en el siguiente bloque de la directiva para no arrastrar edge_cases, y
    # en la frase que explica los campos CALCULADOS por el script: esos no los emite el
    # prompt (es el punto del test 7), asi que enumerarlos aqui solo produciria ruido.
    cortes = [c for c in (cuerpo.find("\n  - step:"),
                          cuerpo.find("\nedge_cases:"),
                          cuerpo.find("\nexpected_outputs:"),
                          cuerpo.find("`evaluacion` incorpora")) if c >= 0]
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


# ── 6. La escala de la rúbrica es 0-10 y los pesos CUADRAN ─────────────────────
#
# Por qué existe: la rúbrica de práctica declaraba pesos que sumaban 11.5 mientras
# el contrato de salida exigía `puntaje_sugerido: "X.X/10"`. El modelo recibía una
# escala que no cerraba y la normalizaba como podía: en una corrida real devolvió
# 5.5/10 cuando sus propios parciales sumaban 5.0, es decir se inventó una escala
# intermedia. Ninguna aserción lo detectaba porque nadie comparaba la suma de los
# pesos con la base declarada.
#
# Este test fija la INVARIANTE, no un númeroSnapshot: mientras la suma sea 10.0 el
# reparto exacto entre criterios puede seguir ajustándose.

RUBRICA_LAB = RAIZ / "directives" / "rubricas" / "rubrica_practica_lab.yaml"
BASE_NOTA = 10.0


def test_escala_rubrica_cuadra() -> None:
    import yaml

    comprobar("la rúbrica de práctica existe", RUBRICA_LAB.exists(),
              f"no se encuentra {RUBRICA_LAB}")
    if not RUBRICA_LAB.exists():
        return

    doc = yaml.safe_load(RUBRICA_LAB.read_text(encoding="utf-8"))
    criterios = doc.get("criterios") or {}
    comprobar("la rúbrica declara criterios", bool(criterios),
              "no hay clave 'criterios' o está vacía")
    if not criterios:
        return

    pesos = {}
    for nombre, cuerpo in criterios.items():
        peso = cuerpo.get("peso") if isinstance(cuerpo, dict) else None
        comprobar(f"'{nombre}' declara un peso numerico",
                  isinstance(peso, (int, float)),
                  f"peso ausente o no numerico: {cuerpo!r}")
        if isinstance(peso, (int, float)):
            pesos[nombre] = float(peso)

    # LA asercion que cxaptaria el bug original.
    suma = round(sum(pesos.values()), 6)
    comprobar(f"los pesos suman {BASE_NOTA} (la base que declara el contrato)",
              suma == BASE_NOTA,
              f"suman {suma}, no {BASE_NOTA}: el modelo no puede cerrar la cuenta. "
              f"pesos={pesos}")

    # Un peso 0 o negativo hace que un criterio no puntúe o reste.
    for nombre, peso in pesos.items():
        comprobar(f"'{nombre}' tiene peso positivo",
                  peso > 0,
                  f"peso {peso}: el criterio no podria puntuarse")

    # Los niveles deben describir RANGOS del total, no una escala 0-N por criterio.
    niveles = doc.get("niveles") or {}
    comprobar("la rúbrica declara niveles", bool(niveles))
    comprobar("los niveles se expresan como rangos 'X.Y-Z.W' del total",
              all(re.fullmatch(r"\d+\.\d+-\d+\.\d+", str(k)) for k in niveles),
              f"se esperaba un rango por clave (p. ej. '5.0-6.9'), hay: {list(niveles)}")

    # Y el prompt debe限额 la aritmética al programa: el prompt NO calcula el total,
    # lo hace calcular_nota() (ver test_nota_la_calcula_el_programa). Aquí lo que se
    # vigila es que no queden restos de la regla vieja ("el total es la suma") que
    # el script ya no cumple, porque el total se ignora.
    mod = importar_evaluar_examen()
    comun = getattr(mod, "PERFIL_COMUN", "")
    comprobar("el prompt NO le pide al modelo que sea el total la suma",
              "suma aritmética" not in comun,
              "quedo la regla vieja: si el modelo calcula un total, se ignora y mislead")
    comprobar("el prompt declara el maximo de la nota",
              f"{BASE_NOTA:.0f}" in comun,
              "el prompt debe decir explicitamente que 10 es el maximo")

    # El schema no debe invitar a inventar el denominador.
    schema = getattr(mod, "SCHEMA_SALIDA", "")
    comprobar("el schema no ofrece un denominador de ejemplo fijo",
              "/2.0" not in schema,
              "un denominador fijo en el schema invita a puntuar sobre una escala inventada")
    comprobar("el schema remite al peso de la rubrica",
              "peso EXACTO del criterio" in schema,
              "el schema debe decir que el denominador es el peso, no un numero inventado")


# ── 7. La nota la calcula el programa, no el modelo ────────────────────────────
#
# Por qué existe: la rúbrica pedía una escala que no cerraba (pesos 11.5 sobre una
# base declarada de 10) y el modelo "normalizaba" como podía. El síntoma era un JSON
# bien formado con un total que no cuadraba con la suma de sus propios ítems: una
# corrida real dio 5.5/10 con parciales que sumaban 5.0. Ni un test ni el informe lo
# veían, porque nadie comparaba la suma contra el total.
#
# La causa no era la prosa del prompt (pedirle mejor aritmética ya se probó y falló:
# los denominadores pasaron a ser correctos y el total siguió sin cuadrar), sino
# delegar la suma. Estos tests fijan que la suma la hace `calcular_nota()`.

def _items(*parciales: str) -> list[dict]:
    return [{"item": f"ítem {i}", "puntaje_parcial": p}
            for i, p in enumerate(parciales, start=1)]


def test_nota_la_calcula_el_programa() -> None:
    mod = importar_evaluar_examen()
    calcular = getattr(mod, "calcular_nota", None)
    comprobar("existe calcular_nota() (la suma es del programa)",
              callable(calcular),
              "sin esta funcion el total lo decide el modelo, que ya se vio fallar")
    if not callable(calcular):
        return

    # El total ES la suma. Con los parciales de una corrida real (8 ítems, base 10).
    d, avisos = calcular(_items("1.0/1.0", "0.5/1.3", "1.3/1.3", "0.0/1.3",
                                "0.5/1.7", "0.7/1.7", "0.7/1.3", "0.3/0.4"))
    comprobar("el total es la suma exacta de los parciales",
              d["puntaje_numerico"] == 5.0,
              f"esperado 5.0, obtenido {d['puntaje_numerico']}")
    comprobar("el total se expresa sobre 10",
              d["puntaje_sugerido"].endswith("/10"),
              f"formato inesperado: {d['puntaje_sugerido']!r}")
    comprobar("una nota coherente no genera avisos", avisos == [],
              f"avisos inesperados: {avisos}")

    # Y el nivel sale de la nota, no al revés.
    for nota, nivel in ((0.0, "Insuficiente"), (2.9, "Insuficiente"),
                        (3.0, "Deficiente"), (5.0, "Suficiente"),
                        (7.0, "Bueno"), (9.0, "Excelente"), (10.0, "Excelente")):
        comprobar(f"nivel_para_nota({nota}) = {nivel}",
                  mod.nivel_para_nota(nota) == nivel,
                  f"obtenido {mod.nivel_para_nota(nota)}")

    # INVARIANTE DE LA UNIVERSIDAD: la nota NUNCA pasa de 10. Este es el requisito
    # explícito del usuario y el que ningún test vigilaba antes.
    rebasables = {
        "todos perfectos": _items("1.0/1.0", "1.3/1.3", "1.3/1.3", "1.3/1.3",
                                  "1.7/1.7", "1.7/1.7", "1.3/1.3", "0.4/0.4"),
        "el modelo se pasa de generoso": _items("5.0/5.0", "9.0/9.0"),
        "parcial por encima de su peso": _items("3.0/1.0", "0.5/1.0"),
        "denominadores que no cierran": _items("10/20", "8/20"),
        "numeros crudos": [{"puntaje_parcial": 99}],
        "lista vacia": [],
    }
    for nombre, items in rebasables.items():
        d, _ = calcular(items)
        # La invariante es "si hay nota, está en [0,10]". Un `None` no es una nota fuera
        # de rango: es la marca de "no publicable" (sin escala se puede deducir), y por
        # eso se comprueba como tal, no como un número.
        if d["puntaje_numerico"] is None:
            comprobar(f"sin nota numérica se marca como no publicable ('{nombre}')",
                      d["nota_fiable"] is False
                      and d["puntaje_sugerido"].startswith("No publicable"),
                      f"hay None pero la nota se presenta como publicable: {d}")
            continue
        comprobar(f"la nota no rebasa 10 con '{nombre}'",
                  0.0 <= d["puntaje_numerico"] <= 10.0,
                  f"obtenido {d['puntaje_numerico']}")
        comprobar(f"hay nota numérica si y solo si es fiable ('{nombre}')",
                  d["nota_fiable"] is True,
                  f"nota_fiable={d['nota_fiable']} con numero {d['puntaje_numerico']!r}")

    # Recortar por encima del peso debe quedar dicho, no pasar desapercibido.
    _, avisos_exceso = calcular(_items("3.0/1.0", "0.5/1.0"))
    comprobar("un parcial por encima del peso deja aviso",
              any("encima de su propio peso" in a for a in avisos_exceso),
              f"el recorte fue silencioso: {avisos_exceso}")

    # Ítems ilegibles: se cuentan y se avisa, nunca se inventan como cero en silencio.
    _, avisos_ilegible = calcular([{"puntaje_parcial": "N/A"}, {"puntaje_parcial": "0.5/1.0"}])
    comprobar("un parcial ilegible deja aviso",
              any("legible" in a for a in avisos_ilegible),
              f"un item no puntuado paso inadvertido: {avisos_ilegible}")
    comprobar("sin items se avisa en vez de fingir un 0 legitimo",
              any("no devolvió ítems" in a for a in calcular([])[1]))

    # Determinismo: la función es pura.
    misma = _items("0.5/1.0", "0.7/1.0")
    comprobar("calcular_nota es pura (mismo input, misma nota)",
              calcular(misma)[0] == calcular(misma)[0])

    # El parser de parciales: un numero suelto NO tiene denominador (si lo tuviera,
    # "0.5" parecería el tope de un criterio y saltaría el recorte sin motivo).
    comprobar("un numero suelto no inventa denominador",
              mod._parsear_parcial("0.5") == (0.5, None),
              f"obtenido {mod._parsear_parcial('0.5')}")
    for forma in ("0.5/1.7", "0.5 / 1.7", "1,3/1,3", "0.7 de 1.7", "8 out of 20"):
        Numerico, denom = mod._parsear_parcial(forma)
        comprobar(f"parsea '{forma}'",
                  denom is not None and denom > 0,
                  f"no se pudo leer el denominador de {forma!r}")
    comprobar("texto sin numero es ilegible, no cero",
              mod._parsear_parcial("N/A") == (None, None),
              "un N/A no puede contamparte como 0 en silencio")


def test_el_prompt_no_pide_la_nota() -> None:
    """
    El prompt ya NO debe pedir `puntaje_sugerido` ni `nivel_desempeno`: si los pide,
    el modelo los emite y el script los sobrescribe, lo cual es trabajo tirado Y hace
    que el JSON guardado tenga un campo que miente sobre quién decidió la nota.
    """
    mod = importar_evaluar_examen()
    schema = getattr(mod, "SCHEMA_SALIDA", "")
    bloque = bloque_json_de_schema(mod)

    comprobar("el schema JSON ya no declara puntaje_sugerido",
              '"puntaje_sugerido"' not in bloque,
              "el schema sigue pidiendo el total al modelo; calcular_nota lo sobrescribe")
    comprobar("el schema JSON ya no declara nivel_desempeno",
              '"nivel_desempeno"' not in bloque,
              "el schema sigue pidiendo el nivel al modelo")
    comprobar("el schema explica que el programa calcula la nota",
              "no emitas" in schema.lower() or "No emitas" in schema,
              "sin esta nota el modelo emitirá los campos igual, por reflejo")

    # El prompt debe—instruir solo la parte que el modelo sí hace: puntuar ítems.
    mod2 = importar_evaluar_examen()
    comun = getattr(mod2, "PERFIL_COMUN", "")
    comprobar("el prompt dice que el programa calcula total y nivel",
              "calcula el programa" in comun,
              "el prompt debe transferir la aritmetica al programa de forma explicita")
    comprobar("el prompt ya no promete escalar el total",
              "escalado a base 10" not in comun,
              "quedo una promesa del prompt viejo que el script ya no cumple")


def test_niveles_yaml_y_codigo_no_divergen() -> None:
    """
    La escala de niveles está en DOS sitios por diseño (código = política institucional
    que aplica a todo; YAML = para que quien lee la rúbrica la vea). Dos copias de la
    misma tabla divergen en silencio: el YAML dice "Bueno" donde el código dice "Suficiente"
    y nada falla, salvo un alumno mal calificado. Este test es el que evita eso.
    """
    mod = importar_evaluar_examen()
    niveles = getattr(mod, "NIVELES", None)
    comprobar("NIVELES es una tabla en el código", isinstance(niveles, (list, tuple)),
              f"no se pudo leer NIVELES del módulo: {niveles!r}")
    if not isinstance(niveles, (list, tuple)) or not niveles:
        return

    # Los topes del código deben ser monótonos y el último debe ser la nota máxima.
    topes = [float(t) for t, _ in niveles]
    comprobar("los topes de nivel crecen de forma monótona",
              all(a < b for a, b in zip(topes, topes[1:])),
              f"topes desordenados: {topes}")
    comprobar("el último tope es la nota máxima",
              abs(topes[-1] - mod.NOTA_MAXIMA) < 1e-9,
              f"el techo {topes[-1]} no coincide con NOTA_MAXIMA {mod.NOTA_MAXIMA}")
    # Cobertura total: recorrer la escala en pasos de 0.05 y exigir un nivel en cada
    # punto. Un hueco (p. ej. un tope de 4.9 seguido de uno de 5.1) dejaría notas sin etiqueta.
    sin_nivel = [round(x / 20, 2) for x in range(0, 201)
                 if not mod.nivel_para_nota(x / 20)]
    comprobar("toda nota de 0 a 10 recibe nivel (sin huecos)",
              not sin_nivel,
              f"notas sin nivel: {sin_nivel[:6]}")
    # Los límites: los niveles son BANDAS ([0.0-2.9], [3.0-4.9], ...), así que un tope
    # pertenece a su propia banda y el salto ocurre justo por ENCIMA del tope anterior.
    # Esto es lo que hace que 2.9 sea Insuficiente y 3.0 ya sea Deficiente.
    for i, (techo, nombre) in enumerate(niveles):
        comprobar(f"en el tope {techo:g} el nivel es {nombre}",
                  mod.nivel_para_nota(techo) == nombre,
                  f"obtenido {mod.nivel_para_nota(techo)}")
        comprobar(f"justo bajo {techo:g} el nivel todavía es {nombre} (misma banda)",
                  mod.nivel_para_nota(techo - 0.1) == nombre,
                  f"obtenido {mod.nivel_para_nota(techo - 0.1)}")
        if i > 0:
            comprobar(f"justo sobre el tope anterior ya es {nombre}",
                      mod.nivel_para_nota(topes[i - 1] + 0.1) == nombre,
                      f"{topes[i - 1] + 0.1:g} quedó como "
                      f"{mod.nivel_para_nota(topes[i - 1] + 0.1)}")

    # Y el YAML, si replica la tabla, debe coincidir con el código.
    if yaml is None:
        comprobar("PyYAML disponible para comparar niveles", False,
                  "sin yaml no se puede verificar la divergencia YAML/código")
        return
    yml = yaml.safe_load((RAIZ / "directives/rubricas/rubrica_practica_lab.yaml").read_text(encoding="utf-8"))
    niveles_yaml = yml.get("niveles")
    # El YAML los declara como MAPA ("3.0-4.9": "Deficiente — errores conceptuales..."),
    # no como lista; y la etiqueta lleva texto descriptivo tras un separador. Comparar
    # solo el nombre del código es lo que importa: la prosa de la rúbrica es del
    # profesor, no parte de la escala institucional.
    if isinstance(niveles_yaml, dict):
        items_yaml = list(niveles_yaml.items())
    elif isinstance(niveles_yaml, list):
        items_yaml = []
        for n in niveles_yaml:
            clave = n.get("rango") or n.get("clave") or n if isinstance(n, dict) else n
            etiqueta = n.get("nivel") or n.get("etiqueta") or "" if isinstance(n, dict) else ""
            items_yaml.append((clave, etiqueta))
    else:
        comprobar("los niveles del YAML tienen una forma reconocible",
                  False, f"tipo inesperado: {type(niveles_yaml).__name__}")
        return
    comprobar("el YAML replica la escala de niveles", bool(items_yaml),
              "no se encontró la tabla de niveles en la rúbrica")
    if not items_yaml:
        return

    comprobar("el YAML declara la misma cantidad de niveles que el código",
              len(items_yaml) == len(niveles),
              f"YAML {len(items_yaml)} niveles, código {len(niveles)}")
    for (clave, etiqueta), (techo, nombre) in zip(items_yaml, niveles):
        clave = str(clave)
        etiqueta = str(etiqueta)
        lo, _, hi = clave.partition("-")
        try:
            lo_f, hi_f = float(lo), float(hi)
        except ValueError:
            comprobar(f"el nivel YAML '{clave}' usa el formato 'lo-hi'", False, clave)
            continue
        # El corte superior debe ser exactamente el tope del código.
        comprobar(f"el corte superior de '{clave}' es el tope del código ({nombre})",
                  abs(hi_f - techo) < 1e-9,
                  f"YAML '{clave}' vs código {techo:g}")
        # El corte inferior debe ser el del código: el primero desde 0, el resto un
        # punto por encima del tope previo (los niveles son bandas contiguas).
        lo_esperado = 0.0 if techo == topes[0] else topes[[t for t, _ in niveles].index(techo) - 1] + 0.1
        comprobar(f"el corte inferior de '{clave}' lo respeta el código",
                  abs(lo_f - lo_esperado) < 1e-9,
                  f"YAML empieza en {lo_f}, el código en {lo_esperado:g}")
        # La etiqueta del YAML debe empezar por el mismo nombre que usa el código.
        comprobar(f"'{clave}' en el YAML se llama {nombre}",
                  etiqueta.split("—")[0].split(" - ")[0].strip() == nombre,
                  f"YAML dice {etiqueta.split(chr(8212))[0]!r}, código dice {nombre!r}")


def test_escala_se_normaliza_no_se_suma_en_crudo() -> None:
    """
    Un examen sin rúbrica se puntúa como el modelo indique — y lo habitual NO es sobre 10.
    Con 3 preguntas a 1 punto cada una, sumar en crudo daba 1.5/10 a un alumno que
   Dynaprende el 50 %: reprobado con nota inventada. Y si el modelo además olvidaba el
    denominador ("0.5", "0.7", "0.3"), el chequeo de escala ni siquiera se disparaba
    (0 avisos) y la nota se publicaba igual. Este test fija las dos cosas.
    """
    mod = importar_evaluar_examen()
    calcular = mod.calcular_nota

    # Escala declarada de 3 puntos: la nota es la PROPORCIÓN sobre 10, no la suma.
    d, avisos = calcular(_items("0.5/1", "0.7/1", "0.3/1"))
    comprobar("una escala de 3 puntos se normaliza a 10",
              d["puntaje_numerico"] == 5.0,
              f"esperado 5.0 (el 50 % de 3 es 5 de 10), obtenido {d['puntaje_numerico']}")
    comprobar("se declara qué escala se aplicó", d["escala_aplicada"] == 3.0,
              f"escala reportada {d['escala_aplicada']}")
    comprobar("normalizar deja aviso explícito",
              any("normalizó" in a for a in avisos),
              "una nota normalizada sin aviso parece una nota directa")

    # Escala 20 preguntas de 0.5 = 10 puntos: no se normaliza (ya es 10) y no hay aviso.
    d20, avisos20 = calcular(_items(*["0.25/0.5"] * 20))
    comprobar("una escala que ya es 10 no se toca",
              d20["puntaje_numerico"] == 5.0 and not any("normalizó" in a for a in avisos20),
              f"{d20['puntaje_numerico']}, avisos={avisos20}")

    # Sin denominadores ni rúbrica: la escala es INDESCIFRABLE. No se publica una nota
    #yreuta; se dice que no es publicable. Antes esto devolvía 1.5/10 en silencio.
    d, avisos = calcular(_items("0.5", "0.7", "0.3"))
    comprobar("sin escala la nota no se publica", d["nota_fiable"] is False,
              f"una nota sin base se publicó como {d['puntaje_sugerido']}")
    comprobar("sin escala el nivel tampoco se publica",
              d["nivel_desempeno"] == "No publicable",
              f"nivel publicado: {d['nivel_desempeno']}")
    comprobar("sin escala no se inventa un número",
              d["puntaje_numerico"] is None,
              f"puntaje_numerico={d['puntaje_numerico']!r} sobre una escala desconocida")
    comprobar("sin escala se dice por qué y cuánto era la suma",
              any("SIN ESCALA FIABLE" in a and "1.50" in a for a in avisos),
              f"el aviso debe Bring la suma observada: {avisos}")

    # Con rúbrica los pesos son conocidos, así que la escala es fiable aunque el modelo
    # se olvide del denominador: es la rúbrica la que dice cuánto vale cada criterio.
    _, pesos = mod.cargar_rubrica(str(RAIZ / "directives/rubricas/rubrica_practica_lab.yaml"))
    d, avisos = calcular([{"item": "presentacion", "puntaje_parcial": "1.0"},
                          {"item": "gramatica", "puntaje_parcial": "0.4"}],
                         pesos=pesos)
    comprobar("con rúbrica la escala es fiable aunque falten denominadores",
              d["nota_fiable"] is True and d["puntaje_numerico"] == 1.4,
              f"obtenido {d['puntaje_numerico']}")
    comprobar("los criterios no puntuados se listan como ausentes",
              len(d["items_ausentes"]) == 6,
              f"ausentes={d['items_ausentes']}")
    comprobar("omitir un criterio NO sube la nota (vale 0 sobre la escala de la rúbrica)",
              d["puntaje_numerico"] == 1.4,
              f"un criterio omitido bonificaba al alumno: {d['puntaje_numerico']}")


def test_la_rubrica_manda_en_los_pesos() -> None:
    """
    El peso lo escribió el profesor en la rúbrica; el modelo solo aporta el cuánto sacó.
    Antes el modelo podía cambiar un peso (y mantener la suma en 10, para que no saltara
    ningún aviso) y la nota salía distinta sin que nadie se enterara.
    """
    mod = importar_evaluar_examen()
    _, pesos = mod.cargar_rubrica(str(RAIZ / "directives/rubricas/rubrica_practica_lab.yaml"))
    honesto = [{"item": n, "puntaje_parcial": f"{v}/{pesos[n]}"} for n, v in
               (("presentacion", 1.0), ("marco_teorico", 1.3), ("diagramas", 1.3),
                ("montaje", 1.3), ("mediciones", 1.7), ("analisis", 1.7),
                ("conclusiones", 1.3), ("gramatica", 0.4))]
    d_ref, avisos_ref = mod.calcular_nota(honesto, pesos=pesos)
    comprobar("una rúbrica respetada no produce avisos",
              avisos_ref == [], f"avisos inesperados: {avisos_ref}")

    # El modelo infla el peso de gramatica (0.4 -> 0.5) y compensa en otro criterio.
    inflado = [dict(it) for it in honesto]
    inflado[-1] = {"item": "gramatica", "puntaje_parcial": "0.5/0.5"}
    inflado[1] = {"item": "marco_teorico", "puntaje_parcial": "1.3/1.2"}
    d, avisos = mod.calcular_nota(inflado, pesos=pesos)
    comprobar("cambiar el peso de un criterio deja aviso",
              any("cambió el peso" in a for a in avisos),
              f"el cambio de peso pasó inadvertido: {avisos}")
    comprobar("se usa el peso de la rúbrica, no el del modelo",
              d["puntaje_numerico"] == d_ref["puntaje_numerico"],
              f"con pesos alterados la nota cambió de {d_ref['puntaje_numerico']} "
              f"a {d['puntaje_numerico']}")

    # Un criterio que el modelo inventa se avisa (aunque la rúbrica sea la que fije la escala).
    extra = honesto + [{"item": "criterio_inventado", "puntaje_parcial": "0.5/0.5"}]
    _, avisos_extra = mod.calcular_nota(extra, pesos=pesos)
    comprobar("un ítem fuera de la rúbrica se avisa",
              any("NO están en la rúbrica" in a for a in avisos_extra),
              f"sin aviso: {avisos_extra}")

    # La rúbrica manda aunque el nombre no coincida exactamente (tildes, mayúsculas).
    _, avisos_renombre = mod.calcular_nota(
        [dict(it, item=it["item"].capitalize() if it["item"] == "analisis" else it["item"])
         for it in honesto], pesos=pesos)
    comprobar("los nombres se comparan sin tildes ni mayúsculas",
              not any("cambió el peso" in a for a in avisos_renombre),
              "un criterio con tilde se dio por desconocido: "
              f"{[a for a in avisos_renombre if 'cambio' in a]}")


def test_rubrica_invalida_falla_ruidosamente() -> None:
    """
    Una rúbrica es configuración. Si se entrega al modelo sin validarse, sus claves no
    existen para nadie: el modelo no ve `pesos:` (porque la clave se llama `peso:`) y se
    inventa una escala. Estos casos son errores de mantenimiento y tienen que PARAR el
    flujo, no producir una evaluación creíble sobre una escala inexistente.
    """
    mod = importar_evaluar_examen()
    cargar = getattr(mod, "cargar_rubrica", None)
    comprobar("existe cargar_rubrica(path) -> (texto, pesos)", callable(cargar),
              "sin parsear la rubrica el codigo no puede contrastar los pesos")
    if not callable(cargar):
        return

    import tempfile
    casos = {
        "pesos que no cierran a 10": (
            "criterios:\n  a:\n    peso: 6.0\n  b:\n    peso: 6.0\n", "suman 12.00"),
        "clave de peso mal escrita": (
            "criterios:\n  a:\n    pesos: 5.0\n  b:\n    peso: 5.0\n", "sin peso"),
        "peso no numérico": (
            "criterios:\n  a:\n    peso: 'mucho'\n  b:\n    peso: 5\n", "no numérico"),
        "peso cero o negativo": (
            "criterios:\n  a:\n    peso: 0\n  b:\n    peso: 10\n", "debe ser > 0"),
        "criterios que no es un mapa": (
            "criterios:\n  - a\n  - b\n", "no es un mapa"),
        "criterio sin mapa": (
            "criterios:\n  a: 5.0\n  b: 5.0\n", "no es un mapa"),
        "YAML roto": ("criterios: [\n  peso: 1\n", "ilegible como YAML"),
    }
    for nombre, (cuerpo, esperado) in casos.items():
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(cuerpo)
            ruta = fh.name
        lanzo = ""
        try:
            cargar(ruta)
        except Exception as exc:  # noqa: BLE001 - queremos ver CUAL fallo
            lanzo = f"{type(exc).__name__}: {exc}"
        finally:
            Path(ruta).unlink(missing_ok=True)
        comprobar(f"'{nombre}' falla en vez de pasar",
                  bool(lanzo), "una rubrica invalida se acepto en silencio")
        if lanzo:
            comprobar(f"el fallo de '{nombre}' dice por qué",
                      esperado.lower() in lanzo.lower(),
                      f"mensaje poco util: {lanzo}")

    # Y una rúbrica válida devuelve pesos utilizables (y el texto intacto para el prompt).
    texto, pesos = cargar(str(RAIZ / "directives/rubricas/rubrica_practica_lab.yaml"))
    comprobar("una rubrica valida devuelve el texto crudo",
              isinstance(texto, str) and texto.strip().startswith("#"),
              "el texto de la rubrica debe llegar al prompt tal cual")
    comprobar("una rubrica valida devuelve el mapa de pesos",
              isinstance(pesos, dict) and abs(sum(pesos.values()) - 10.0) < 1e-9,
              f"pesos={pesos}")
    # Sin rúbrica de pesos (examen), no es un error: se entrega el texto y pesos=None.
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False,
                                     encoding="utf-8") as fh:
        fh.write("# rúbrica sin pesos, solo texto\nalgo: que sea\n")
        ruta = fh.name
    try:
        _, pesos_vacios = cargar(ruta)
    finally:
        Path(ruta).unlink(missing_ok=True)
    comprobar("una rubrica sin pesos no es un error (examen)",
              pesos_vacios is None, f"pesos={pesos_vacios!r}")


def test_fixture_examen_es_verificable() -> None:
    """
    El fixture del examen es un documento FABRICADO con errores deliberados y
    documentados: sin esa verdad sabida, la prueba end-to-end no prueba nada. Dos
    formas de perderla sin que nada se rompa:

    - alguien edita el enunciado y cambia la escala (de 6 puntos a 10), y la prueba
      sigue dando verde mientras deja de ejercitar la normalización;
    - el generador se pierde con una limpieza de `.tmp/` y ya no se puede repetir.

    Por eso el generador vive en `execution/` (no en `.tmp/`, que es gitignored y lo
    purga `flujo_disco.py`) y estas aserciones fijan lo que la prueba comprueba.
    """
    gen = RAIZ / "execution" / "generar_fixture_examen.py"
    comprobar("el generador del fixture vive en execution/ (no en .tmp/)",
              gen.exists(),
              "sin generador el fixture no es reproducible: una limpieza de disco lo borra")
    if not gen.exists():
        return

    spec = importlib.util.spec_from_file_location("generar_fixture_examen", gen)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:  # noqa: BLE001
        comprobar("el generador del fixture se puede importar", False, f"falla al importar: {exc}")
        return
    comprobar("el generador del fixture se puede importar", True)

    enunciado = " ".join(getattr(mod, "ENUNCIADO", "").split())
    errores = getattr(mod, "ERRORES_DELIBERADOS", None)

    # La escala declarada es 6 (3 preguntas de 2): NO suma 10 a proposito.
    comprobar("el fixture declara una escala que NO suma 10",
              "2 puntos" in enunciado and "6 puntos" in enunciado,
              "si la escala.sumara 10, la prueba dejaría de ejercitar la normalización")
    comprobar("el fixture tiene 3 preguntas de 2 puntos",
              enunciado.count("Pregunta 1") >= 1 and enunciado.count("Pregunta 2") >= 1
              and enunciado.count("Pregunta 3") >= 1,
              "faltan preguntas: la prueba no evaluaria 3 ítems")
    comprobar("las respuestas del estudiante están en el fixture (no solo el enunciado)",
              "Respuestas del estudiante" in enunciado,
              "sin respuestas no hay nada que corregir: la evaluación sería de un examen en blanco")

    comprobar("los errores deliberados están documentados",
              isinstance(errores, list) and len(errores) >= 5,
              f"ERRORES_DELIBERADOS={errores!r}")
    if isinstance(errores, list) and errores:
        for etiqueta in ("P1", "P2", "P3"):
            comprobar(f"hay errores deliberados documentados en {etiqueta}",
                      any(etiqueta in e for e in errores),
                      "una pregunta sin error documentado no verifica nada")
        # Se exige un error CONCEPTUAL por pregunta, no "cualquier error": el
        # conceptual es el grave (el diodo invertido que el estudiante cree correcto)
        # y es el que el evaluador puede omitir en silencio. Exigir solo "alguno"
        # dejaba pasar que se borrara el conceptual de una pregunta mientras otro
        # procedimental de la misma pregunta mantenía verde el test.
        for etiqueta in ("P1", "P2", "P3"):
            comprobar(f"hay un error conceptual deliberado en {etiqueta}",
                      any(etiqueta in e and "conceptual" in e for e in errores),
                      f"sin error conceptual en {etiqueta} no se verifica el error grave")

    # Si el PDF ya fue generado, su texto debe seguir siendo el que el generador
    # declara: si divergen, el .tmp/ es viejo y la prueba se midió sobre otro documento.
    pdf = RAIZ / ".tmp" / "fixture_examen.pdf"
    if not pdf.exists():
        return
    try:
        txt = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True,
                             text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return
    marcas = ["470/570", "C/R", "5/330"]
    comprobar("el PDF del fixture se corresponde con el generador",
              all(m in " ".join(txt.split()) for m in marcas),
              "el PDF de .tmp/ no corresponde al generador actual: regenerarlo con "
              "python3 execution/generar_fixture_examen.py")


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    print("Pruebas de rúbrica / tipo de documento (evaluar_examen.py)")
    print("=" * 62)
    test_nota_la_calcula_el_programa()
    test_el_prompt_no_pide_la_nota()
    test_escala_se_normaliza_no_se_suma_en_crudo()
    test_la_rubrica_manda_en_los_pesos()
    test_rubrica_invalida_falla_ruidosamente()
    test_fixture_examen_es_verificable()
    test_niveles_yaml_y_codigo_no_divergen()
    test_escala_rubrica_cuadra()
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