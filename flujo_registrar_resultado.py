#!/usr/bin/env python3
"""
flujo_registrar_resultado.py — Orquestador del registro de entregas (Layer 2)

Ejecuta el pipeline definido en la directiva registrar_resultado_curso.yaml:
  1. execution/registrar_resultado.py → valida y escribe la fila del acta
  2. verificación de entrega → acta legible y fila presente
  3. execution/alert_user.py → alerta audible (opcional)

Este orquestador NO decide la nota ni la fiabilidad: eso lo trae quien corrigió
(la nota la calcula `execution/evaluar_examen.py`) y aquí solo se archiva y se anota.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
PYTHON = sys.executable
REGISTRADOR = SCRIPT_DIR / "execution" / "registrar_resultado.py"
ALERTAR = SCRIPT_DIR / "execution" / "alert_user.py"

sys.path.insert(0, str(SCRIPT_DIR / "execution"))
import run_state as RS  # noqa: E402

DIAGNOSTICO = {
    1: "argumentos inválidos",
    2: "descriptor ilegible o que no es YAML",
    3: "datos inválidos (semana, grupo o nota fuera de escala, o documento inexistente)",
    4: "la entrega ya estaba registrada (usar --reemplazar para corregir la nota)",
    5: "error de escritura en disco",
}


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def guardar(state: dict) -> None:
    RS.escribir_vista(RS.ruta_vista(state.get("run_id")), state)


def _verificar(acta: Path, semana: int, grupo: int) -> list[str]:
    """Comprueba que el acta existe y que la fila quedó escrita una sola vez."""
    if not acta.exists():
        return [f"no se escribió el acta ({acta})"]
    with acta.open(newline="", encoding="utf-8") as fh:
        filas = list(csv.DictReader(fh))
    coincidencias = [
        f for f in filas if f.get("semana") == f"{semana:02d}" and f.get("grupo") == str(grupo)
    ]
    problemas: list[str] = []
    if len(coincidencias) != 1:
        problemas.append(f"se esperaba 1 fila de semana {semana:02d}/grupo {grupo} y hay {len(coincidencias)}")
    if coincidencias and coincidencias[0].get("nota_sobre_10") in (None, ""):
        problemas.append("la fila no tiene nota")
    return problemas


def flujo_registrar_resultado(
    curso: Path,
    semana: int,
    grupo: int,
    nota: float,
    documento: str | None,
    no_fiable: bool,
    observaciones: str | None,
    fecha: str | None,
    reemplazar: bool,
    salida: Path | None,
    alert: bool,
    como_json: bool,
) -> int:
    run_id = RS.run_id_de_la_corrida("flujo-registrar-resultado")
    state = {
        "run_id": run_id,
        "directive": "registrar_resultado_curso.yaml",
        "started_at": ahora(),
        "last_updated": ahora(),
        "current_step": 0,
        "steps": [],
    }
    guardar(state)

    comando = [
        PYTHON,
        str(REGISTRADOR),
        "--curso",
        str(curso),
        "--semana",
        str(semana),
        "--grupo",
        str(grupo),
        "--nota",
        f"{nota}",
        "--json",
    ]
    if documento:
        comando += ["--documento", documento]
    if no_fiable:
        comando += ["--no-fiable"]
    if observaciones:
        comando += ["--observaciones", observaciones]
    if fecha:
        comando += ["--fecha", fecha]
    if reemplazar:
        comando += ["--reemplazar"]
    if salida:
        comando += ["--salida", str(salida)]

    if not como_json:
        print(f"[1/3] registro: semana {semana:02d}, grupo {grupo}, nota {nota:.2f}")
    proceso = subprocess.run(comando, text=True, capture_output=True)
    state["steps"].append(
        {"step": 1, "script": "execution/registrar_resultado.py", "exit_code": proceso.returncode}
    )
    state["current_step"] = 1
    state["last_updated"] = ahora()
    guardar(state)

    try:
        resultado = json.loads(proceso.stdout) if proceso.stdout.strip() else {}
    except json.JSONDecodeError:
        resultado = {"status": "error", "problemas": [proceso.stdout.strip()[:500]]}

    if proceso.returncode != 0:
        motivo = DIAGNOSTICO.get(proceso.returncode, "fallo no catalogado")
        problemas = resultado.get("problemas") or [proceso.stderr.strip()[:500]]
        if como_json:
            print(json.dumps(
                {"status": "error", "code": proceso.returncode, "motivo": motivo,
                 "problemas": problemas, "run_id": run_id},
                ensure_ascii=False, indent=2,
            ))
        else:
            print(f"[x] Registro falló (código {proceso.returncode}): {motivo}")
            for problema in problemas:
                print(f"    - {problema}")
        state["status"] = "error"
        state["code"] = proceso.returncode
        state["last_updated"] = ahora()
        guardar(state)
        return proceso.returncode

    acta = Path(resultado.get("acta", ""))
    if not como_json:
        print(f"[2/3] verificación: {acta}")
    problemas = _verificar(acta, semana, grupo)
    state["steps"].append({"step": 2, "script": "verificar_acta", "exit_code": 0 if not problemas else 3})
    state["current_step"] = 2
    state["last_updated"] = ahora()
    guardar(state)

    if problemas:
        if como_json:
            print(json.dumps(
                {"status": "error", "code": 3, "motivo": "el acta no quedó como se esperaba",
                 "problemas": problemas, "run_id": run_id},
                ensure_ascii=False, indent=2,
            ))
        else:
            print("[x] El acta no quedó como se esperaba:")
            for problema in problemas:
                print(f"    - {problema}")
        state["status"] = "error"
        state["code"] = 3
        state["last_updated"] = ahora()
        guardar(state)
        return 3

    if not como_json:
        print("[3/3] registro verificado")
    state["steps"].append({"step": 3, "script": "execution/alert_user.py", "exit_code": 0})
    state["current_step"] = 3
    state["status"] = "ok"
    state["code"] = 0
    state["last_updated"] = ahora()
    guardar(state)

    if alert:
        subprocess.run([PYTHON, str(ALERTAR), "success"], check=False)

    if como_json:
        print(json.dumps(
            {"status": "ok", "run_id": run_id, **{k: v for k, v in resultado.items() if k != "status"}},
            ensure_ascii=False, indent=2,
        ))
    else:
        fila = resultado.get("fila") or {}
        print(f"    acta: {resultado.get('acta')}")
        print(f"    fila: semana {fila.get('semana')} · grupo {fila.get('grupo')} · "
              f"rol {fila.get('rol')} · nota {fila.get('nota_sobre_10')}/10")
        if resultado.get("documento"):
            print(f"    informe: {resultado['documento']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Registra una entrega corregida en el acta local del curso."
    )
    parser.add_argument("--curso", required=True, help="Descriptor curso.yaml")
    parser.add_argument("--semana", required=True, type=int, help="Número de semana")
    parser.add_argument("--grupo", required=True, type=int, help="Número de grupo")
    parser.add_argument("--nota", required=True, type=float, help="Nota sobre 10")
    parser.add_argument("--documento", default=None, help="Informe corregido a archivar (PDF)")
    parser.add_argument("--no-fiable", action="store_true", help="Nota pendiente de revisión a mano")
    parser.add_argument("--observaciones", default=None, help="Nota breve para el acta")
    parser.add_argument("--fecha", default=None, help="Fecha ISO del registro (por defecto, hoy)")
    parser.add_argument("--reemplazar", action="store_true", help="Reemplaza la fila existente")
    parser.add_argument("--salida", default=None, help="Carpeta resultados/ alternativa")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    parser.add_argument("--no-alert", action="store_true", help="Sin alerta audible")
    args = parser.parse_args()

    return flujo_registrar_resultado(
        curso=Path(args.curso).expanduser().resolve(),
        semana=args.semana,
        grupo=args.grupo,
        nota=args.nota,
        documento=args.documento,
        no_fiable=args.no_fiable,
        observaciones=args.observaciones,
        fecha=args.fecha,
        reemplazar=args.reemplazar,
        salida=Path(args.salida).expanduser().resolve() if args.salida else None,
        alert=not args.no_alert,
        como_json=args.json,
    )


if __name__ == "__main__":
    sys.exit(main())
