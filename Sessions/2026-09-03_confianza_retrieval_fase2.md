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
