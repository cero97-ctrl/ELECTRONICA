# Fase 2 — Resolver problemas con un skill estructurado (patrón neuro-simbólico)

> Documento de estudio. Archivo de referencia: `docs/AGENTE_IA/conversacion_agentes_skills.md`
> (sección 4, "Integración Neuro-Simbólica SymPy/Z3") y su arquitectura de 3 capas.
> Implementado el 2026-09-01. Coste de la sesión completa: ~$0.75.

---

## 1. Qué resuelve

Un skill destilado de un libro guarda teoría, metodologías, límites y prerrequisitos
(estructura enriquecida, Fase 1). La **Fase 2** usa ese skill para **resolver problemas**
con fundamento, no para "responder preguntas sobre el libro".

El problema clave que aborda: el LLM no debe calcular *a ciegas* ni inventar fórmulas.
La arquitectura separa **razonamiento cualitativo** (LLM) de **verificación simbólica**
(oráculo SymPy determinista).

```
[Problema + Skill] ──> [Retrieval (embeddings)] ──> [LLM: Formulador] ──> [Oráculo SymPy]
                                                          │  (análisis +        │
                                                          │   bloque sympy)     │
                                                          └──── error ─────────┘
                                                                  │
                                                         [Reflexión ≤3]
```

---

## 2. La arquitectura de 3 capas (obligatoria)

| Capa | Archivo | Rol |
| :--- | :--- | :--- |
| **Directiva** | `directives/resolver_skill.yaml` | SOP: entradas, pasos, salidas, 8 edge cases, retry budget |
| **Orquestación** | `flujo_resolver_skill.py` | Valida, enruta modelo (determinista), invoca y reporta |
| **Ejecución** | `execution/resolver_skill.py` | Motor: retrieval, formulación, oráculo, reflexión |

El **LLM nunca decide ni valida**: formula. La decisión de quién es el modelo la toma
`execution/enrutador.py`; el criterio de éxito lo toma el oráculo. Siempre.

---

## 3. `execution/resolver_skill.py` — el motor (determinista)

### 3.1 Retrielleval por embeddings (0 créditos)
- Divide `SKILL.md` + `references/*.md` en **secciones** partiendo por cabeceras markdown `#...###`.
- Convierte a embeddings con `paraphrase-multilingual-MiniLM-L12-v2` y hace **cosine similarity**
  entre el problema y cada sección.
- Devuelve `top-k` secciones con `score > min-score` (default k=6, score=0.05).
- **Caché determinista** en `.tmp/resolver_skill/<skill>/`:
  - `secciones.json` con hash del texto (invalida si cambia el skill).
  - `embeddings.npz` con hash del contenido (invalida si cambia).
  - Re-hit ~instantáneo; el modelo de embeddings se carga **una sola vez** (singleton).

### 3.2 Formulador LLM (créditos)
- Prompt de sistema: instruye a razonar paso a paso citando la **metodología del skill**
  y verificar **prerrequisitos/límites** ANTES de usar cada fórmula.
- Exige un JSON con exactamente 3 claves:
  ```json
  {"analisis": "razonamiento paso a paso",
   "codigo_sympy": "código SymPy AUTOCONTENIDO",
   "resultado_esperado": "valor que el código DEBE imprimir (predicción)"}
  ```
- El código debe ser autocontenido: `from sympy import *` + definir TODAS las variables,
  terminar con un único `print()` del resultado legible.
- **Manejo de JSON robusto**: extrae bloque ```json/fenced```, quita trailing commas,
  y usa `_find_balanced_json` (escaneo por llaves balanceadas, ver `.agent/python.md`) — nunca
  regex non-greedy.

### 3.3 Oráculo SymPy (0 créditos)
- Ejecuta el bloque en un **sandbox aislado** (`subprocess.run([sys.executable, -c, src])`, timeout).
- Antes, **seguridad por AST**: `_escaneo_seguridad` (reutiliza `validar_skill_formulas.py`)
  veta `os`, `subprocess`, `eval`, `exec`, dunders.
- Resultado: `{exit_code, stdout, stderr, timeout, inseguro}`. `exit_code 0` = éxito.

### 3.4 Bucle de reflexión (créditos, ≤3)
- Si el oráculo falla (sintaxis, NameError, inseguro, timeout, JSON inválido) se inyecta el
  error **real** (stderr del sandbox) como feedback y el LLM re-formula.
- El prompt de reflexión pide corregir "solo el error sin cambiar la estrategia".

### Salida
JSON con: `status, code, problema, skill, modelo, secciones_usadas[{archivo,titulo,score}],
analisis, codigo_sympy, resultado_esperado, resultado_oraculo, resultado_final,
reflexiones_usadas, tokens`.
Exit: `0` ok / `1` args / `2` skill inválido / `3` no resuelto / `5` error LLM.

---

## 4. `flujo_resolver_skill.py` — orquestador

```
Paso 1  Validación de entradas (problema no vacío, skill tiene SKILL.md)
Paso 2  Enrutamiento determinista → execution/enrutador.py (task, tokens, crítico)
Paso 3  resolver_skill.py + guardar resultado en .tmp/resolucion_<ts>.json + alerta
```

- **Default task = `calculo_formal`** → enrutador decide **opus** (riguroso).
- `--modelo <id>` = override explícito (salta el enrutador). Útil para **tests baratos**: ej.
  `--modelo google/gemini-3.7-flash` (flash ≈ centavos).
- Guarda `.tmp/resolucion_<ts>.json`, registra `.tmp/run_state.json`, alerta audible
  (`success`/`error`), código `3` si no se resolvió.

---

## 5. Rendimiento y coste (datos reales, 2026-09-01)

Skill: `circuitos_dispositivos_electronicos` (33 bloques SymPy validados, 0 inválidos).

| Problema | Tier/modelo | Sección top recuperada | Resultado oráculo | Reflexión | Coste |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Punto Q BJT (divisor base) | flash (test) | "Metodología 7: Análisis BJT en DC" (0.680) | ICQ=2.4566 mA, VCEQ=4.6057 V | 0 | ~$0.005 |

Observaciones:
- El LLM citó **explícitamente la metodología del skill** ("Se aplica la Metodología 7"),
  que era exactamente el objetivo de la Fase 2: ilustra el patrón.
- El resultado numérico coincide con el cálculo manual → el oráculo validó la deducción.
- El grueso del pipeline (retrieval, oráculo, seguridad) es **0 créditos**.

---

## 6. Limitaciones y pendientes

- **Fidelidad al libro**: el oráculo verifica que el código *se ejecute* y dé un valor
  **coherente**, pero no que la metodología sea *literalmente la del texto*. Pendiente
  **Fase 2b**: capa de contraste que relacione cada claim de los references con su chunk
  de origen.
- **Calidad del skill aguas arriba**: si la Fase 1 destiló mal (ruido de PDF), el resolver
  heredará el error. La validación neuro-simbólica (33/33) reduce el riesgo pero no lo anula.
- **Timeout del sandbox (default 30s)**: bloques numéricos pesados podrían dar falsos
  positivos de timeout; ajustar con `--timeout-s`.
- `--usar-corpus`: reutiliza la destilación persistida — adecuado para re-ensamblar sin
  re-distilar (ahorra ~$0.7 y ~30 min en el libro de 452 págs).

---

## 7. Comandos útiles

```bash
# Resolver un problema con el skill instalado (producción: calculo_formal → opus)
python3 flujo_resolver_skill.py --problema "..." --skill ~/.config/opencode/skills/circuitos_dispositivos_electronicos

# Test barato con modelo flash (override, salta enrutador)
python3 flujo_resolver_skill.py --problema "..." --skill ~/.config/opencode/skills/circuitos_dispositivos_electronicos --modelo google/gemini-3.7-flash --max-reflexion 1

# Solo ver qué secciones recupera (0 créditos)
python3 execution/resolver_skill.py --skill ~/.config/opencode/skills/circuitos_dispositivos_electronicos --problema "..." --solo-retrieval
```

---

## 8. Archivos relacionados

- `execution/resolver_skill.py` — motor (retrieval/formulador/oráculo/reflexión)
- `flujo_resolver_skill.py` — orquestador
- `directives/resolver_skill.yaml` — SOP
- `execution/sintetizar_skill.py` — Fase 1 (generación del skill)
- `execution/validar_skill_formulas.py` — validador neuro-simbólico (comparte `_escaneo_seguridad`)
- `execution/enrutador.py` — decisión determinista del modelo
- `execution/llm_client.py` — `openrouter_chat`
- `Sessions/2026-09-01_e2e_libro_fase2_resolver.md` — log de la sesión
