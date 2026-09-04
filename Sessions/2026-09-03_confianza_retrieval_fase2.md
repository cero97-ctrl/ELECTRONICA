# Sesión: Confianza del Retrieval en la Fase 2 (Fundamento Débil)

Fecha: 2026-09-03
Tema: Reportar score/nivel de confianza del retrieval en `resolver_skill.py` y avisar/abortar ante fundamento débil.

## Actividades

1. **Análisis del problema:** Un problema de ingeniería puede no estar reseñado en el PDF.
   Antes (solo `--min-score`) el sistema abortaba si **ninguna** sección superaba el umbral,
   pero con fundamento débil (score bajo pero ≥ umbral) procedía a gastar créditos y
   formular con fundamento parcial sin avisar.

2. **Implementación (Layer 3) — `execution/resolver_skill.py`:**
   - Nuevo helper determinista `_nivel_confianza(secciones, alerta_score)` → clasifica el
     mejor score coseno en `alta`/`media`/`baja`.
   - Nuevos args `--alerta-score` (default 0.35) y `--abortar-debil`.
   - Campos nuevos en la salida: `confianza_retrieval {nivel, mejor_score, alerta, alerta_score}`.
   - `--solo-retrieval` también reporta `confianza_retrieval` (0 créditos).
   - `_mensaje_usuario`: inyecta aviso de "FUNDAMENTO DÉBIL" al formulador cuando es baja,
     para que el LLM indique "no cubierto por el libro" en vez de forzar fórmulas.

3. **Implementación (Layer 2) — `flujo_resolver_skill.py`:**
   - Nuevos args `--alerta-score`/`--abortar-debil`, pasados al resolver.
   - Aviso visible en consola (`⚠ Confianza del retrieval BAJA/MEDIA`) y persistido en el JSON.

4. **Documentación:**
   - `directives/resolver_skill.yaml`: nuevos optional_inputs, edge case "fundamento débil",
     y `confianza_retrieval` en expected_outputs.
   - `docs/AGENTE_IA/fase2_resolver_skill.md`: sección 3.1 y Salida actualizadas.
   - Nuevo test `test_resolver_confianza.py` (19 casos, 0 créditos): niveles, umbral
     configurable, bordes exactos, y aviso de fundamento al formulador.

## Hallazgo empírico y recalibración de umbrales

Se midió el mejor score coseno real con `paraphrase-multilingual-MiniLM-L12-v2` sobre el
skill `circuitos_dispositivos_electronicos`:

| Tipo de problema | mejor_score medido |
| :--- | :--- |
| En alcance (BJT, Ley de Ohm, Thévenin, Kirchhoff) | **0.45 – 0.75** |
| Fuera de alcance (química, poesía griega) | **~0.25** |

Con los defaults iniciales (`alerta_score=0.20`, `alta=0.45`) la confianza `baja` **jamás
se disparaba en la práctica** (hasta la poesía griega daba 0.25 → media). El umbral de
"fundamento débil" quedaba muerto. **Decisión (confirmada por el usuario): recalibrar con
la separación medida** → `alerta_score = 0.35` y `CONFIANZA_ALTA = 0.55`.

Verificación en vivo (0 créditos) tras recalibrar:
- Fuera de alcance (química): `baja` (0.2648) ✅
- Dentro de alcance (BJT): `alta` (0.7092) ✅
- `--abortar-debil` con problema fuera de alcance → exit 3 **sin** llamar al LLM (0 créditos) ✅

## Decisiones

- Recalibrar los umbrales con evidencia (no a ojo), conforme al espíritu determinista del
  proyecto: la calibración se basó en mediciones reales de separación en/out-of-scope.
- Comportamiento por defecto ante confianza baja: **avisar** (no bloquea); endurecer con
  `--abortar-debil` cuando se quiera hipótesis rígida.

## Pendientes

- ~~El `.tex`/`.pdf` universitario (ya enviado) no refleja esta mejora; actualizarlo solo si
  se quiere una versión revisada.~~ → **HECHO (2026-09-03):** versión revisada de
  `skill_fases_1_y_2.tex/.pdf` (13 págs) con la sección §10.2 "Validación de Confianza del
  Retrieval" (calibración empírica, detección de fundamento débil) y los comandos nuevos.
- Considerar telemetría de scores reales (`.tmp/routing_log.jsonl`-style) para afinar aún
  más los umbrales por skill concreto.

---

# Ampliación: Multi-Skill (Opción C) — el resolver consulta varios skills del dominio

Fecha: 2026-09-03 (misma sesión)
Decisión del usuario: usar **varios skills separados** que el resolver consulte (no fusionar
en uno solo), porque **la dificultad/confianza del problema señala si faltan PDFs**. Los PDFs
adicionales deben ser del mismo dominio o afines (electrónica, física), ~≤5 MB, y el documento
universitario debe reflejarlo.

## Actividades

1. **`execution/resolver_skill.py`:**
   - `--skill` pasa a `nargs="+"` (acepta varios).
   - Nueva función pura `_combinar_retrievals(retrievals, top_k)` (testable sin embeddings):
     etiqueta `fuente`, ordena por score, corta al `top-k` GLOBAL, reporta `por_skill`.
   - `_retrieval_multi` ensambla por-skill y delega en `_combinar_retrievals`.
   - `confianza` sobre el **mejor score combinado** + `skills_consultados`,
     `skills_sin_secciones`, `mejor_skill`, `por_skill[{skill,ruta,secc,mejor_score}]`.
   - Salida: `skills` (lista) y `secciones_usadas[{fuente,...}]`.
   - `--abortar-debil` sugiere "añadir más PDFs/skills del dominio".
2. **`flujo_resolver_skill.py`:** valida todos los skills, pasa la lista, y en consola muestra
   el mejor score por skill + sugiere añadir PDFs si confianza baja.
3. **`directives/resolver_skill.yaml`:** skill plural, step 1/3 actualizados, expected_outputs
   multi-skill, edge case "skill sin secciones en modo multi (se omite)" y señal
   dificultad→añadir PDFs.
4. **`docs/AGENTE_IA/fase2_resolver_skill.md`:** multi-skill en 3.1, Salida, §4, comandos.
5. **`test_resolver_confianza.py`:** +9 casos multi-skill de `_combinar_retrievals` y aviso
   plural (28 total, 0 créditos). Todos pasan.
6. **Documento universitario `skill_fases_1_y_2.tex/.pdf`:** flujo multi-skill, §9.1
   "Retrieval Multi-Skill", tabla 3 capas, comandos 6/7, §10.2 con filas de multi-skill y
   señal dificultad→añadir PDFs. PDF regenerado (13 págs).

## Verificación multi-skill (0 créditos)

- `--skill circuitos ... computacion_cientifica` (problema RLC, dentro de alcance electrónica):
  `confianza: alta` (0.6836 combinado), `mejor_skill: circuitos_dispositivos_electronicos`,
  `por_skill`: circuitos 0.6836 / computación 0.3457. `secciones_usadas` con `fuente` ✅
- Problema fuera de alcance (poesía griega): `confianza: baja` (0.2264) con `por_skill` y mensaje ✅

## Decisiones

- Opción C confirmada por el usuario: skills separados + retrieval agregado en consulta.
- El determinismo se preserva: `_combinar_retrievals` es función pura del conjunto de
  scores; mismo descriptor → misma salida. La decisión de "ampliar con más PDFs" queda como
  aviso (heurística) al usuario, no como bloqueo automático (salvo `--abortar-debil`).

---

## Cierre de sesión (pausa)

**Confirmación final del usuario (idea rectora):** la ampliación de conocimiento debe estar
orientada a la señal de **confianza del retrieval**. Cuando un problema requiera más de lo que
los skills actuales cubren (confianza `baja` en un problema difícil), debe existir la
posibilidad de **agregar más PDFs** para obtener una respuesta confiable. Este circuito ya
está operativo:

```
Problema difícil + confianza baja  →  aviso (por_skill)  →  añadir PDF del dominio
    →  Fase 1: flujo_libro_a_skill.py  →  nuevo skill  →  resolver con --skill <todos los skills>
```

**Estado:** pausa. Nada pendiente de implementar para esta idea (la mecánica está commiteada).
Cuando se retome, se probará el ciclo completo con un caso real (problema que deje confianza
`baja` + PDF faltante del dominio).

**Próximos pasos sugeridos (al reanudar):**
1. Proponer un problema que hoy quede con confianza `baja` con los skills actuales; confirmar
   el aviso y ver por `por_skill` qué skill/área aporta.
2. Si ya existe un PDF del dominio que cubra la laguna (≤5 MB), generar su skill con la Fase 1
   y re-resolver pasando todos los skills.
3. (Opcional) telemetría de scores reales para afinar umbrales por skill.

---

## Idea registrada (pendiente de evaluar): librerías Python adicionales en el sandbox

Fecha: 2026-09-03 (cierre de sesión)
Contexto: ante un problema con respuesta poco confiable por falta de *método* (p. ej. resolver
una determinada ecuación diferencial), el usuario plantea que, **en lugar de cargar más PDFs**,
tal vez la solución sea **usar librerías Python adicionales** ya instaladas en el sandbox del
oráculo. La teoría del libro aporta el *qué* (planteo); el ecosistema Python aporta el *cómo*
numérico (ej. `scipy.integrate.solve_ivp` para EDOs).

**Disponibilidad confirmada en `elect_env` (2026-09-03):**
- ✅ `numpy` 2.2.6, `scipy` 1.15.3, `sympy` 1.14.0, `mpmath` 1.3.0, `networkx` 3.4.2
- ❌ `pandas`, `matplotlib`, `control` (no instaladas)

**Consideraciones técnicas (para cuando se evalúe):**
- El sandbox (`resolver_skill.py` → `_oraculo`) ya ejecuta `sys.executable -c <src>` y, en
  principio, admite cualquier librería de `elect_env`; la limitación real es qué libs están
  instaladas y que el prompt del formulador hoy prohíbe "import de módulos no estándar".
- Habría que: (a) decantar/declarar el set de librerías permitidas disponible al sandbox;
  (b) ajustar el prompt del formulador para usarlas cuando el skill no da método numérico
  directo; (c) plantear si marcar la respuesta como "usó librería externa" en el JSON.
- Esto toca las 3 capas (directiva + orquestador + ejecución) y es una mejora distinta de la
  ampliación multi-skill por PDFs.

**Decisión del usuario:** por ahora **dejarlo como aviso** (sin implementar). Queda registrado
para retomarlo tras la pausa, si se quiere explorar el diseño concreto.




---

## Hallazgo al resolver un caso real (2026-09-04): dilución del mejor skill en multi-skill

**Problema resuelto (éxito):** Equivalente Thévenin con fuente 12V, R1=2k en serie, R2=3k y R3=6k
en paralelo. Skills: `circuitos_dispositivos_electronicos` + `computacion_cientifica`.
Resultado verificado por el oráculo: **Vth = 6.0 V, Rth = 1 kΩ** (0 reflexiones, ~1982 tokens,
flag flash).

**Hallazgo (robustez del retrieval multi-skill):**
- Con skills SOLO de circuitos, `--solo-retrieval` da confianza `alta` (0.6192) y recupera la
  sección "Cálculo del Equivalente Thévenin".
- En modo multi-skill, el `top-k` GLOBAL (6) se llenó con las 6 mejores secciones de
  `computacion_cientifica` (mejores ~0.35), y **las secciones de Thévenin del skill relevante
  (0.62-0.67) quedaron desplazadas fuera del contexto del LLM**. Confianza reportada: `media`
  (0.3519), porque computación tenía el mayor mejor-score de las realmente entregadas.
- El problema igual se resolvió correctamente (el formulador dedujo el Thévenin del enunciado),
  pero se perdió la evidencia más fuerte del skill de dominio.

**Causa raíz:** `_combinar_retrievals` corta al `top-k` global por score puro; un skill lateral
con muchos chunks de score medio puede desplazar al skill más afín con scores más altos.

**Mejora propuesta (pendiente de aprobación):** estrategia de cuotas por skill (p. ej. reservar
la mejor sección de cada skill consultado + completar con el resto por score global), de modo
que el contexto del LLM nunca pierda por completo la evidencia del skill más afín.
```

---

## Implementación: cuotas por skill (no-dilución) + bug de multi-skill en el flujo (2026-09-04)

**Estado:** la "Mejora propuesta" anterior quedó **implementada y verificado en vivo** (commit único).

### 1. Cuotas por skill en `execution/resolver_skill.py` (`_combinar_retrievals`)
- **Reserva obligatoria:** se incluye siempre la mejor sección de cada skill.
- **Cuotas equitativas:** el resto del top-k se completa por round-robin por score desc
  (reparto lo más parejo posible), sin que un skill lateral sature el contexto.
- **Deduplicación** por texto entre skills (se conserva el de mayor score).
- `secciones_recuperadas` = aporte real al contexto; `mejor_score` = mejor de TODAS las
  secciones del skill (no solo las del contexto), para no penalizar la confianza por la cuota.
- Orden final por score desc (misma forma de salida).

### 2. Bug descubierto y corregido en `flujo_resolver_skill.py` (línea 154)
- El flujo construía el subproceso como `--skill A --skill B`, y como `resolver_skill.py`
  define `--skill nargs="+"`, argparse **conservaba solo el último** skill
  (`skills_consultados` contenía únicamente `computacion_cientifica`). Por eso los runs del
  flujo con 2 skills reportaban siempre confianza `media` (0.3519), solo con computación.
- Corregido a `--skill A B` (un solo flag, todos los valores). Ahora ambos skills llegan al
  resolver. **El multi-skill del flujo estaba efectivamente roto**; la verificación en vivo del
  fix de cuotas lo expuso.

### 3. Verificación (0 créditos + 1 run de ~2k tokens flash)
- `--solo-retrieval` con ambos skills, problema Thévenin extendido → confianza `alta` (0.6192),
  `mejor_skill: circuitos`, contexto repartido 3/3 (circuitos: Thévenin 0.619, divisor 0.613 +
  diodo; computación: 3 secciones ~0.35).
- Flujo E2E con ambos skills → confianza alta, por_skill 3/3, **resultado Vth=6.0 V, Rth=1000 Ω**
  validado por el oráculo SymPy (0 reflexiones, flash).

### 4. Tests
- `test_resolver_confianza.py`: 28 → **36 tests** (0 créditos), todos pasan. Añadidos:
  `test_cuotas_no_diluciona`, `test_cuotas_topk_menor_que_skills`, `test_cuotas_llenan_exacto`,
  `test_cuotas_dedup_por_texto`. El test previo de `secciones_recuperadas` se ajustó al nuevo
  comportamiento de reserva (top_k=2, 2 skills → 1 sección cada uno).

### 5. Documentación actualizada (3 capas)
- `directives/resolver_skill.yaml` (paso 3a: cuotas).
- `docs/AGENTE_IA/fase2_resolver_skill.md` (§3.1 multi-skill: cuotas/dedup/mejor_score sobre todas).
- `docs/AGENTE_IA/skill_fases_1_y_2.tex` (§9.1 ampliada) + `.pdf` recompilado (exit 0, aux limpios).
