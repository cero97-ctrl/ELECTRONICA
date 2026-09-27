"""Algebra de veredictos compartida por todos los flujos de auditoria.

Nace de una duplicacion: `flujo_auditar_repo.py` tenia el algebra de estados
definida dentro, y `flujo_auditar_sistema.py` necesitaba exactamente la misma.
Copiar el codigo habria producido dos verdades que divergen en silencio, que es
la forma mas cara de equivocarse en un modulo cuya unica razon de ser es la
consistencia.

Este modulo es CAPA 3 y es deliberadamente tonto: no lee ficheros, no invoca
procesos, no mira el sistema. Es una funcion PURA sobre diccionarios ya
medidos, y por eso se puede testear sola, sin raiz, sin git y sin /proc. Todo lo
que el flujo hace falta poner en la capa 2 (ordenar, medir, decidir que hacer
con cada dimension) queda fuera de aqui a proposito.

La regla que gobierna el diseno: el veredicto global es el PEOR estado
presente, nunca un promedio. Un promedio de RAM al 90% con disco al 30% sale
"todo bien" con media RAM y sin disco, y ese numero no describe ninguna
realidad. Ademas `no_verificado` tiene precedencia sobre `fallo` por una razon
concreta: si hay algo roto Y algo que no se pudo medir, hay que arreglar lo roto
primero, y el informe lo dice en `motivo`. Lo que nunca puede pasar es que un
hueco se disfrace de salud.
"""

from __future__ import annotations

from typing import Any

# De peor a mejor. `no_verificado` va por delante de todo porque no es un
# problema del sistema: es un limite de lo que sabemos, y un informe que no sabe
# algo no puede llamarse limpio.
PRIORIDAD: dict[str, int] = {"no_verificado": 3, "fallo": 2, "aviso": 1, "ok": 0}

VEREDICTO_POR_ESTADO: dict[str, str] = {
    "no_verificado": "no_verificado",
    "fallo": "con_fallos",
    "aviso": "con_avisos",
    "ok": "limpio",
}

CODIGO_POR_VEREDICTO: dict[str, int] = {
    "limpio": 0,
    "con_avisos": 0,
    "con_fallos": 1,
    "no_verificado": 2,
}

EXIT_USO_INCORRECTO: int = 3


def estado_valido(estado: str) -> bool:
    """True si `estado` pertenece al vocabulario cerrado."""
    return estado in PRIORIDAD


def clasificar_salud(dimensiones: list[dict[str, Any]]) -> dict[str, Any]:
    """Funcion PURA: lista de dimensiones -> veredicto global.

    Sin promedio, sin pesos, sin puntuacion. Gana el peor estado presente, y la
    precedencia entre `no_verificado` y `fallo` es explicita: si hay algo roto
    se dice primero, porque es lo que hay que arreglar, aunque ademas haya
    dimensiones que no se pudieron medir. El veredicto final tambien lo dice.

    Es una funcion pura a proposito: se testea sola, sin ficheros ni git.
    """
    if not dimensiones:
        return {
            "veredicto": "no_verificado",
            "exit_code": 2,
            "motivo": "no se evaluo ninguna dimension: un informe sin dimensiones no informa",
            "conteo": {},
        }

    conteo: dict[str, int] = {}
    desconocidos: list[str] = []
    for d in dimensiones:
        estado = d.get("estado", "no_verificado")
        conteo[estado] = conteo.get(estado, 0) + 1
        # Un estado que no existe en el vocabulario NO se cuenta como sano. Sin
        # esta comprobacion, una dimension con un `estado` mal escrito caia
        # fuera de todos los `if` siguientes y salia como "limpio": un verde
        # falsoproducido por una errata en una cadena.
        if estado not in PRIORIDAD:
            desconocidos.append(d.get("dimension", "?"))

    if not conteo:
        return {
            "veredicto": "no_verificado", "exit_code": 2,
            "motivo": "ninguna dimension devolvio estado", "conteo": conteo,
        }

    if desconocidos:
        return {
            "veredicto": "no_verificado", "exit_code": 2,
            "motivo": (
                f"{len(desconocidos)} dimension(es) devolvieron un estado fuera del "
                f"vocabulario {sorted(PRIORIDAD)}: {', '.join(desconocidos)}. "
                "Un estado no reconocido se trata como no comprobado, nunca como sano."
            ),
            "conteo": conteo,
            "dimensiones_afectadas": desconocidos,
            "cobertura": {"medidas": 0, "no_medidas": len(dimensiones)},
        }

    # Peor estado presente, con la precedencia explicita de arriba.
    if conteo.get("fallo"):
        veredicto = "con_fallos"
    elif conteo.get("no_verificado"):
        veredicto = "no_verificado"
    elif conteo.get("aviso"):
        veredicto = "con_avisos"
    else:
        veredicto = "limpio"
    exit_code = CODIGO_POR_VEREDICTO[veredicto]

    motivos = [d["dimension"] for d in dimensiones if d.get("estado") == "fallo"]
    if conteo.get("no_verificado"):
        motivos += [d["dimension"] for d in dimensiones
                    if d.get("estado") == "no_verificado"]

    return {
        "veredicto": veredicto,
        "exit_code": exit_code,
        "motivo": (
            f"{conteo.get('fallo', 0)} dimension(es) con fallo"
            + (f", {conteo.get('no_verificado', 0)} sin verificar" if conteo.get("no_verificado") else "")
            if veredicto != "limpio" else
            f"las {len(dimensiones)} dimensiones medidas no tienen fallos"
        ),
        "conteo": conteo,
        "dimensiones_afectadas": motivos,
        "cobertura": {
            "medidas": len(dimensiones) - conteo.get("no_verificado", 0),
            "no_medidas": conteo.get("no_verificado", 0),
        },
    }
