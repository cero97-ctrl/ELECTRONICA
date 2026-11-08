# 2026-11-08 — curso_ciberseguridad

## Tema
curso_ciberseguridad

## Contexto
- Continuación de la sesión del 2026-11-07 (semana 1 con ejemplos por grupo ya
  entregados en el commit `47b77c8`).
- Quedaba abierto del backlog: "replicar el patrón `--semana N` para las semanas
  2–10 y escribir sus ejemplos". Se aclaró al usuario que son dos tareas
  distintas: emitir el documento semanal (mecánico) y redactar los `ejemplos:`
  por grupo (autoría de contenido, semana a semana).
- Verificación previa: las semanas 2–10 ya tenían datos completos para emitir su
  documento (objetivo, contenidos, herramientas, práctica con 5 pasos y criterios
  que suman 10,0), pero **ninguna declaraba glosario**.

## Decisiones (usuario)
1. Alcance de esta sesión: **solo los documentos de las semanas 2–10**; los
   ejemplos por grupo se redactan semana a semana cuando toque.
2. **Sí añadir glosario por semana**, manteniendo el patrón de la semana 1.
3. Plan y lista de términos aprobados por el usuario antes de ejecutar.

## Actividades
- `cursos/CYBERSEGURIDAD/curso.yaml`: glosario global de 18 → **77 términos**
  (+59 definiciones) y lista `glosario:` declarada en cada semana:
  - 02 criptografía: 8 · 03 legal: 7 · 04 OSINT: 8 · 05 web: 6 · 06 hardening: 8
  - 07 DevSec: 6 · 08 forense: 7 · 09 IR/malware: 7 · 10 final: 2
- Validación previa con `validar_semana()` y `_glosario()`: las 9 semanas sin
  problemas y cada término resuelve contra el glosario global (sin orfanatos).
- Emisión con `flujo_instrucciones_semana.py --curso ... --semana N` para N=2..10:
  9 documentos nuevos `docs/semana_02..10.{tex,pdf}`, 5 páginas cada uno
  (4 de contenido + 1 de glosario).
- Verificación por documento: 0 líneas `!` en el log, 0 `Overfull \hbox`,
  `verificar_pdf.py` → `ok`, 0 solapes, 5 páginas.
- Determinismo: segunda corrida de las 9 semanas y `diff` de sha256 → idénticos.
- Coste: 0 créditos OpenRouter (no intervino ningún LLM).
- El usuario revisó visualmente los 9 PDF: "todo perfecto".
- El usuario añadió `docs/INFOGRAFIAS/SEM_1/` con 4 infografías PNG (rol rojo,
  rol azul, rol púrpura y flujo legal y reporte), en formato divulgativo para sus
  estudiantes.
- Bitácora creada con `bitacoras.py nueva --tema curso_ciberseguridad`.

## Pendientes
- Commit + push de esta sesión: `d6493c5` (descriptor, 9 documentos semanales,
  infografías y esta bitácora), empujado a `master`; árbol limpio.
- Infografías de la semana 1 en `docs/INFOGRAFIAS/SEM_1/` (4 PNG, ~28 MB),
  aportadas y revisadas por el usuario como material para estudiantes. No las
  genera ningún script: si el repositorio crece demasiado, valorar almacenarlas
  fuera de git.
- Redactar los `ejemplos:` por grupo de las semanas 2–10 (36 bloques), semana a
  semana; la semana 2 (criptografía) es la siguiente natural.
- `nota_minima: 5` confirmada por el usuario el 2026-11-08 y ya consta en el
  descriptor; nada que cambiar.
- Revisar visualmente los PDF nuevos (no se abrieron uno a uno en esta sesión,
  solo validación determinista y extracción de texto de la página de glosario).
