# 2026-10-02 — nota_determinista_escala_rubrica

## Tema
Cierre de la nota determinista: normalización de escala (ajuste 1) y rúbrica como
fuente de verdad de los pesos (ajuste 2).

## Contexto
- La sesión anterior ya había hecho que el programa (no el LLM) calculara el total, y
  quedó demostrado que un JSON bien formado no garantiza aritmética correcta
  (`.agent/python.md` entrada 22: el modelo dio 5.5/10 con parciales que sumaban 5.0).
- Al revisar el código aparecieron dos defectos nuevos, ambos de la misma familia
  ("el campo agregado no cuadra con los campos que lo componen"):
  - **Escala ≠ 10.** Sumar parciales en crudo solo es correcto si la escala del
    instrumento es 10. Un examen de 3 preguntas a 1 punto suma 3: el alumno con el 50 %
    (`0.5/1, 0.7/1, 0.3/1`) salía 1.5/10 "Insuficiente". Y si el modelo omitía el
    denominador (`0.5, 0.7, 0.3`), el programa no detectaba nada y publicaba 1.5/10
    en silencio.
  - **La rúbrica se leía como texto y no se validaba.** Los pesos nunca llegaban a
    `calcular_nota`, así que el modelo decidía la escala. Una clave mal escrita
    (`pesos:` en vez de `peso:`) producía una evaluación creíble sobre una escala
    inexistente, indistinguible de una real.

## Decisiones (usuario)
1. Implementar los ajustes **1** (normalizar escala / no publicar nota sin base) y **2**
   (parsear y validar la rúbrica, y que sus pesos manden).
2. Mantener el tier flash: `google/gemini-2.5-flash` en OpenRouter y
   `gemini-2.5-flash` en Gemini directo.
3. **Ajuste 3 aprobado después** ("procede con el ajuste 3"): fixture y end-to-end de
   `--tipo examen`, que era el que faltaba por ser el camino sin rúbrica.

## Actividades
- `calcular_nota(items, pesos=None, nota_maxima=10.0)`:
  - normaliza contra la escala conocida (`10 · obtenido/Σ denominadores`) y avisa;
  - sin rúbrica y sin denominadores: `nota_fiable=false`, `puntaje_numerico=null`,
    `puntaje_sugerido="No publicable"`, `nivel_desempeno="No publicable"`, y el aviso
    lleva la suma observada;
  - **con rúbrica la escala la fija la rúbrica**, no los denominadores del modelo: un
    criterio ausente vale 0 sobre una escala de 10 y se lista en `items_ausentes`;
  - un peso que el modelo altere se recorta al de la rúbrica, con aviso; un ítem fuera
    de la rúbrica se avisa; los nombres se comparan sin tildes ni mayúsculas
    (`_normalizar_nombre`).
- `cargar_rubrica(path) -> (texto, pesos)`: parsea el YAML y valida criterios (mapa),
  pesos (numéricos, > 0) y suma cercana a 10; un error de mantenimiento **para** el flujo
  con `ValueError` que dice el motivo. `leer_rubrica()` queda como wrapper de texto.
- `evaluar_documento()` carga `(texto, pesos)` una sola vez y pasa los pesos al cálculo.
- E2E de laboratorio por OpenRouter: parciales suman 4.30, nota `4.3/10` "Deficiente",
  `escala_aplicada=10.0`, `items_ausentes=[]`, **cero avisos de cálculo** (el modelo
  respetó los pesos de la rúbrica).
- Caso "No publicable" verificado de punta a punta: JSON → `.tex` → PDF compila y la
  etiqueta cabe en una celda (`"No publicable (revisar a mano)"` la partía en dos líneas,
  así que el matiz vive en `nota_para_el_profesor`).
- Documentado en `.agent/python.md` (entrada 23) y en las dos directivas.
- `execution/generar_fixture_examen.py` (ajuste 3): genera un examen escrito FABRICADO de
  2 páginas (3 preguntas de 2 puntos) con `ERRORES_DELIBERADOS` documentados. Declara en el
  enunciado una escala de **6 puntos que no suma 10**, a propósito: es el caso donde sumar en
  crudo reprobaba a quien respondía bien.
  - Vive en `execution/` y no en `.tmp/` (como el de laboratorio) porque `.tmp/` es
    gitignored y lo purga `flujo_disco.py`: un fixture que solo existe hasta la próxima
    limpieza no es un fixture reproducible.
  - Antes de gastar créditos se comprobó que el fixture renderiza (2 imágenes a 250 dpi) y que
    `pdftotext` ve los fragmentos de error (`470/570`, `C/R`, `5/330`).
- E2E `--tipo examen` por OpenRouter (`gemini-2.5-flash`, 2876 tokens):
  - parciales `0.0/2`, `1.0/2`, `0.0/2` → escala declarada 6.0 → nota `1.67/10`
    `Insuficiente`, con el aviso de normalización dentro de `nota_para_el_profesor`;
  - recalculado desde los parciales a mano: `10·1.00/6.00 = 1.67` — **coincide**;
  - clave `observaciones_por_item` (no la de prefijo), informe PDF con encabezado de examen.
- **Hallazgo honesto sobre los límites del modelo:** de los 7 errores deliberados detectó 5,
  pero **no** el más grave: el diodo montado en polaridad inversa que el estudiante afirma
  como "la forma correcta". Lo reportó como "omisión de la caída de tensión". Es decir: la
  evaluación automática no tiene cobertura completa de los errores conceptuales que el
  estudiante sostiene con seguridad. NO se cambió el prompt por esto (sería ajustar
  comportamiento sin acuerdo); queda como decisión abierta.
- Test del fixture (`test_fixture_examen_es_verificable`): fija que el generador existe en
  `execution/`, que la escala NO suma 10, que hay respuestas de estudiante, que cada pregunta
  tiene un error **conceptual** documentado y que el PDF de `.tmp/` corresponde al
  generador. Mutado dos veces (escala 6→10, y borrar el conceptual de P3): **ambas
  detectadas**. La primera versión solo pedía "algún error por pregunta" y dejó pasar la
  segunda mutación; por eso ahora se exige cobertura conceptual por pregunta.
- `test_evaluar_rubrica.py`: 169 → **182 aserciones, 0 fallos**. Resto de suites en verde:
  barrera 103, auditar_repo 134, auditar_sistema 102, run_state 63, verificar_texto 22,
  sync_faq 7.
- `flujo_auditar_repo.py --rapido`: `VEREDICTO: con_avisos`, 0 dimensiones con fallo (el
  generador nuevo en `execution/` no genera aviso de capa ni de huérfano).

## Pendientes
- **Decisión del usuario (2026-10-02):** en vez de tocar el prompt a ciegas, mediré la
  cobertura real de detección con **PDFs de alumnos reales**. Sesión en pausa hasta que los
  consiga.
  - Dato relevante para esa medición: en el repo **no hay respuestas de alumnos**
    (`examenes/*/examen_estudiantes/` está vacío). Lo único en
    `examenes/mcp_test/` es un examen generado por el propio repo con su solución, que no
    sirve como respuesta de alumno. Sin PDFs nuevos no hay medición posible.
  - Lo que hará falta de cada PDF: dónde está el error en cada respuesta (aunque sea una
    frase) y, si existe, el veredicto/nota del profesor. Sin verdad etiquetada no hay tasa
    de detección, solo la autoinforme del modelo sobre sí mismo.
- **Corrección de un hallazgo propio:** el "no detectó la polaridad invertida del diodo" se admite sobre un fixture fabricado por mí. Es evidencia de **un** caso, no de una limitación
  general de la evaluación automática, que es como se redactó en el resumen de la sesión.
  No se generaliza hasta tener PDFs reales.
- **Prompt sin tocar:** `TAREA_POR_TIPO["examen"]` sigue sin pedir que se señale la
  afirmación que el estudiante sostiene con seguridad y que es falsa. Es lo que falló en el
  fixture, pero cambiarlo sin datos reales sería ajustar comportamiento a ciegas.
- El SDK Gemini directo sigue devolviendo `503 UNAVAILABLE`; OpenRouter funciona. Sin
  impacto en este trabajo.
- Cambios sin commit: `execution/evaluar_examen.py`, `execution/test_evaluar_rubrica.py`,
  `execution/generar_fixture_examen.py` (nuevo), `directives/evaluar_examen_estudiante.yaml`,
  `directives/evaluar_practica_laboratorio.yaml`, `.agent/python.md`, `AGENTS.md` y esta
  bitácora, más los cambios paralelos de tier que ya venían en el working tree.

