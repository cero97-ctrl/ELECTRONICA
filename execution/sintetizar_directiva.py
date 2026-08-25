#!/usr/bin/env python3
"""
sintetizar_directiva.py — Síntesis determinista del borrador de directiva
generado a partir de una entrevista de requerimientos (Layer 3: Execution).

Flujo asociado: directives/entrevista_agente.yaml

Uso:
    python3 execution/sintetizar_directiva.py \
        --respuestas .tmp/entrevista_<nombre>.json \
        --output .tmp/borrador_directiva_<nombre>.yaml \
        [--nombre <id_agente>]

Entrada (--respuestas): JSON de la entrevista con la estructura:
    {
      "nombre_agente": "...",
      "objetivo_agente": "...",
      "bloques": {
        "<bloque_id>": {
          "estado": "confirmado" | "supuesto",
          "respuestas": {...} | [...],
          "supuestos": [...],
          "notas": "..."
        }, ...
      },
      "descriptor_enrutamiento": {
        "task": "...", "tokens_estimados": N,
        "critico": bool, "vision": bool
      }
    }

Salida (stdout, JSON):
    { "status": "ok", "borrador": "<ruta>", "bloques_sintetizados": [...],
      "supuestos_pendientes": [...], "descriptor_valido": bool }

Códigos de salida:
    0 — Borrador generado y validado
    1 — Error de argumentos o archivos ilegibles/inexistentes
    2 — Entrevista incompleta (bloques faltantes o sin responder)
    3 — JSON de respuestas malformado o esquema inválido
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml

BLOCK_IDS: tuple[str, ...] = (
    "objetivo_alcance",
    "herramientas_integraciones",
    "arquitectura_memoria",
    "flujo_ejecucion",
    "requisitos_no_funcionales",
    "fallos_reintentos_exito",
)

ESTADOS_VALIDOS: frozenset[str] = frozenset({"confirmado", "supuesto"})

_PALABRAS_FALLO = re.compile(r"fallo|falla|error|inv[áa]lid|corrupt|vaci", re.IGNORECASE)
_PALABRAS_EXITO = re.compile(r"[ée]xito|verific|prueba|validar|comprobar", re.IGNORECASE)


class _ArgParserExit1(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        print(json.dumps({"status": "error", "code": 1, "message": message}), file=sys.stderr)
        sys.exit(1)


def _slug(texto: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", texto.lower()).strip("_")
    return slug[:max_len] or "entrada"


def _a_texto(valor: Any) -> str:
    if isinstance(valor, dict):
        return "; ".join(f"{k}: {v}" for k, v in valor.items())
    if isinstance(valor, list):
        return "; ".join(str(v) for v in valor)
    return str(valor).strip()


def _pares_respuestas(bloque: dict[str, Any]) -> list[tuple[str, Any]]:
    respuestas = bloque.get("respuestas", {})
    if isinstance(respuestas, dict):
        return list(respuestas.items())
    if isinstance(respuestas, list):
        return [(str(i + 1), v) for i, v in enumerate(respuestas)]
    return []


def _validar_esquema(datos: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Retorna (errores_fatales, bloques_incompletos)."""
    errores: list[str] = []
    incompletos: list[str] = []

    for campo in ("nombre_agente", "objetivo_agente"):
        if not isinstance(datos.get(campo), str) or not datos.get(campo, "").strip():
            errores.append(f"campo_obligatorio_ausente:{campo}")

    bloques = datos.get("bloques")
    if not isinstance(bloques, dict):
        return errores + ["seccion_bloques_ausente"], list(BLOCK_IDS)

    for bid in BLOCK_IDS:
        bloque = bloques.get(bid)
        if not isinstance(bloque, dict):
            incompletos.append(bid)
            continue
        estado = bloque.get("estado")
        if estado not in ESTADOS_VALIDOS:
            incompletos.append(f"{bid}(estado_invalido:{estado!r})")
            continue
        if not _pares_respuestas(bloque):
            incompletos.append(f"{bid}(sin_respuestas)")

    return errores, incompletos


def _validar_descriptor(descriptor: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    if not isinstance(descriptor, dict) or not descriptor:
        return {}, False
    task = descriptor.get("task")
    valido = isinstance(task, str) and task.strip() != ""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from enrutador import FLASH_TASKS, KIMI_TASKS, OPUS_TASKS  # type: ignore

        valido = task in (FLASH_TASKS | KIMI_TASKS | OPUS_TASKS)
    except Exception:
        pass
    return descriptor, bool(valido)


def _construir_goal(datos: dict[str, Any]) -> str:
    alcance = datos["bloques"].get("objetivo_alcance", {})
    detalles = " ".join(_a_texto(v) for _, v in _pares_respuestas(alcance))
    partes = [datos["objetivo_agente"].strip()]
    if detalles:
        partes.append(detalles)
    return " ".join(partes)


def _construir_required_inputs(datos: dict[str, Any]) -> list[dict[str, Any]]:
    herramientas = datos["bloques"].get("herramientas_integraciones", {})
    entradas: list[dict[str, Any]] = [
        dict(
            name="nombre_agente",
            description=f"Identificador del agente: {datos['nombre_agente']}",
        )
    ]
    pares = _pares_respuestas(herramientas)
    if pares:
        for pregunta, respuesta in pares:
            base = pregunta if len(str(pregunta)) <= 60 else str(pregunta)[:57] + "..."
            entradas.append(
                dict(name=_slug(base), description=_a_texto(respuesta))
            )
    else:
        entradas.append(
            dict(
                name="por_definir", description="[BORRADOR] Completar según entrevista."
            )
        )
    return entradas


def _construir_steps(datos: dict[str, Any]) -> list[dict[str, Any]]:
    flujo = datos["bloques"].get("flujo_ejecucion", {})
    pasos: list[dict[str, Any]] = []
    for i, (pregunta, respuesta) in enumerate(_pares_respuestas(flujo), start=1):
        pasos.append(
            dict(
                step=i,
                description=f"{pregunta}: {_a_texto(respuesta)}",
                script=None,
                actor="orquestador",
            )
        )
    if not pasos:
        pasos.append(
            dict(
                step=1,
                description="[BORRADOR] Definir etapas del flujo según la entrevista.",
                script=None,
                actor="orquestador",
            )
        )
    pasos.append(
        dict(
            step=len(pasos) + 1,
            description="Emitir alerta audible de completado.",
            script="execution/alert_user.py",
            inputs={"status": "success"},
        )
    )
    return pasos


def _construir_expected_outputs(datos: dict[str, Any]) -> list[dict[str, Any]]:
    fallos = datos["bloques"].get("fallos_reintentos_exito", {})
    criterios = [
        _a_texto(resp)
        for preg, resp in _pares_respuestas(fallos)
        if _PALABRAS_EXITO.search(str(preg)) or _PALABRAS_EXITO.search(_a_texto(resp))
    ]
    salidas: list[dict[str, Any]] = [
        dict(name="salida_principal", description=criterio)
        for criterio in criterios[:3]
    ]
    if not salidas:
        salidas.append(
            dict(
                name="salida_principal",
                description="[BORRADOR] Definir salida verificable según criterios de éxito.",
            )
        )
    salidas.append(
        dict(
            name="resumen_impreso",
            description="Resumen en stdout JSON del resultado de la ejecución.",
        )
    )
    return salidas


def _construir_edge_cases(datos: dict[str, Any]) -> list[dict[str, Any]]:
    fallos = datos["bloques"].get("fallos_reintentos_exito", {})
    casos: list[dict[str, Any]] = []
    for pregunta, respuesta in _pares_respuestas(fallos):
        texto_preg = str(pregunta)
        if _PALABRAS_FALLO.search(texto_preg) or _PALABRAS_FALLO.search(_a_texto(respuesta)):
            casos.append(
                dict(case=texto_preg, recovery=_a_texto(respuesta))
            )
    if not casos:
        casos.append(
            dict(
                case="[BORRADOR] Edge cases no especificados en la entrevista",
                recovery="Definir protocolos de recuperación antes de operar el agente.",
            )
        )
    casos.append(
        dict(
            case="Fallo persistente de herramienta o API tras reintentos",
            recovery="Retry budget estándar del proyecto: máximo 3 intentos; luego detener y escalar al usuario.",
        )
    )
    return casos


def sintetizar(datos: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    supuestos: list[str] = []
    for bid, bloque in datos["bloques"].items():
        if not isinstance(bloque, dict):
            continue
        if bloque.get("estado") == "supuesto" and not bloque.get("supuestos"):
            supuestos.append(bid)
        else:
            supuestos.extend(bloque.get("supuestos", []))
        notas = bloque.get("notas")
        if notas:
            supuestos.append(f"nota[{bid}]: {notas}")

    descriptor, descriptor_valido = _validar_descriptor(
        datos.get("descriptor_enrutamiento", {})
    )

    borrador: dict[str, Any] = {}
    borrador["goal"] = _construir_goal(datos)
    borrador["required_inputs"] = _construir_required_inputs(datos)
    borrador["optional_inputs"] = [
        dict(
            name="por_definir",
            description="[BORRADOR] Ajustar parámetros opcionales durante el desarrollo.",
        )
    ]
    borrador["steps"] = _construir_steps(datos)
    borrador["expected_outputs"] = _construir_expected_outputs(datos)
    borrador["edge_cases"] = _construir_edge_cases(datos)
    borrador["descriptor_enrutamiento"] = dict(
        descriptor,
        validado_vocabulario=descriptor_valido,
        nota=(
            "Validar con: python3 execution/enrutador.py --task <task> ..."
            if descriptor_valido
            else "INVÁLIDO o ausente: corregir --task contra el vocabulario del enrutador"
        ),
    )
    borrador["metadata"] = dict(
        version="0.1-borrador",
        created=date.today().isoformat(),
        author="entrevista_agente",
        origen=f".tmp/entrevista_{datos['nombre_agente']}.json",
        supuestos_pendientes=supuestos,
        notas=(
            "Generado por execution/sintetizar_directiva.py. Revisar cada sección, "
            "completar las 3 capas (directiva + orquestador + script) y solo entonces "
            "mover a directives/."
        ),
    )
    return borrador, supuestos


def main() -> None:
    parser = _ArgParserExit1(description=__doc__)
    parser.add_argument("--respuestas", required=True, help="JSON de la entrevista.")
    parser.add_argument("--output", required=True, help="Ruta del borrador YAML.")
    parser.add_argument("--nombre", default="", help="ID del agente (verificación cruzada).")

    args = parser.parse_args()

    ruta_json = Path(args.respuestas)
    if not ruta_json.is_file():
        print(
            json.dumps(
                {
                    "status": "error",
                    "code": 1,
                    "message": f"No existe el archivo de respuestas: {ruta_json}",
                }
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        datos = json.loads(ruta_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(
            json.dumps({"status": "error", "code": 3, "message": f"JSON malformado: {exc}"}),
            file=sys.stderr,
        )
        sys.exit(3)

    if not isinstance(datos, dict):
        print(
            json.dumps(
                {"status": "error", "code": 3, "message": "El JSON raíz debe ser un objeto."}
            ),
            file=sys.stderr,
        )
        sys.exit(3)

    errores, incompletos = _validar_esquema(datos)
    if errores:
        print(
            json.dumps({"status": "error", "code": 3, "message": "; ".join(errores)}),
            file=sys.stderr,
        )
        sys.exit(3)

    if args.nombre and args.nombre != datos["nombre_agente"]:
        print(
            json.dumps(
                {
                    "status": "error",
                    "code": 1,
                    "message": (
                        f"--nombre ({args.nombre}) no coincide con "
                        f"nombre_agente del JSON ({datos['nombre_agente']})"
                    ),
                }
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    if incompletos:
        print(
            json.dumps(
                {
                    "status": "incompleto",
                    "code": 2,
                    "message": "Bloques faltantes o sin respuestas válidas.",
                    "faltantes": incompletos,
                }
            )
        )
        sys.exit(2)

    borrador, supuestos = sintetizar(datos)

    ruta_out = Path(args.output)
    ruta_out.parent.mkdir(parents=True, exist_ok=True)
    ruta_out.write_text(
        yaml.safe_dump(
            dict(borrador),
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
            width=100,
        ),
        encoding="utf-8",
    )

    if not ruta_out.is_file() or ruta_out.stat().st_size == 0:
        print(
            json.dumps(
                {"status": "error", "code": 1, "message": "No se pudo escribir el borrador."}
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        json.dumps(
            {
                "status": "ok",
                "borrador": str(ruta_out),
                "bloques_sintetizados": list(datos["bloques"].keys()),
                "supuestos_pendientes": supuestos,
                "descriptor_valido": borrador["descriptor_enrutamiento"][
                    "validado_vocabulario"
                ],
            },
            ensure_ascii=False,
        )
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
