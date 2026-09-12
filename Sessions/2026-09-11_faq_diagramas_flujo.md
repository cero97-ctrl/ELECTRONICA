# 2026-09-11 — faq_diagramas_flujo

## Tema
Traducir `docs/AGENTE_IA/faq_higiene_estado_sesion.md` a diagramas de flujo en
simbología ANSI/ISO (ISO 5807 / ANSI X3.5), formato LaTeX + TikZ → PDF.

## Contexto
- El usuario preguntó por la simbología ANSI/ISO de diagramas de flujo y luego
  solicitó traducir el FAQ de higiene de estado de sesión (continuidad de las
  sesiones `2026-09-11_estado_sesion_higiene` y `2026-09-11_refuerzo_bitacoras_alto_nivel`)
  a un diagrama de flujo.
- El FAQ documenta la arquitectura de higiene de estado (commits `80ff0ec`,
  `3446db4`, `7dab0bb`): cadena de integridad del log append-only, guardia MCP por
  mtime, veredictos de `estado_sesion.py` y eslabón semántico de `bitacoras.py`.
- Se validó previamente el estado de sesión: `estado_sesion.py check` →
  `veredicto_global: ok`, sin huérfanos (solo un registro con `estado: fin`).

## Decisiones (usuario)
1. Formato: **LaTeX + TikZ → PDF** (nuevo documento infográfico en `docs/AGENTE_IA/`,
   compilado con `pdflatex`), no Mermaid ni imagen standalone.
2. Alcance: **todos los flujos por sección** del FAQ (cadena de integridad, guardia
   MCP, check/clean, bitacoras nueva/check, cierre de sesión), no un solo diagrama
   maestro.
3. Se usó simbología ISO 5807 (terminador/proceso/decisión/E-S/almacenamiento/
   documento/nota) con estilos TikZ propios y una leyenda al inicio del documento.
4. Asumido (no consultado): el estilo de preámbulo replica el patrón de
   `higiene_estado_sesion.tex` (sourcesanspro + banda título + paleta azulNoche/
   cyanNeon + tcolorbox), sin importar `estilo_infografia.py` porque es un .tex
   manuscrito, no un generador.

## Actividades
- `estado_sesion.py check` → ok, sin huérfanos. Bitácora creada con
  `bitacoras.py nueva --tema "faq_diagramas_flujo"`.
- Lectura previa de estilo: `higiene_estado_sesion.tex` (preámbulo, tarjetas,
  secciones infográficas) y verificación de que no había patrón de flowchart previo
  reutilizable en `docs/AGENTE_IA/` (nada con `shapes.geometric` para flujo).
- Creado `docs/AGENTE_IA/faq_higiene_estado_sesion_flujo.tex` con:
  1. Leyenda de símbolos ISO 5807 en caja `cajaContenido`.
  2. Diagrama 1 (Sección 1): cadena de integridad hash-chain + decisión `integrity`
     + nota "no es blockchain".
  3. Diagrama 2 (Sección 2): guardia MCP — mtime_before → run → ¿existe ahora? →
     ¿mtime_before=None? → ¿mtime_ahora>mtime_before? con nota del porqué flujo/fin
     no sirve de guardia.
  4. Diagrama 3 (Sección 3): veredictos `no_verificable`/`corrupto`/`vigente`/
     `huerfano` con ramas Sí/No y reglas de clean + nota `modelo_obsoleto`.
  5. Diagrama 4 (Sección 4): dos columnas `nueva` (ya_existia / crea 5 secciones) y
     `check` (legado vs hoy/reciente, anomalías, hay_bitacora → "atencion").
  6. Diagrama 5 (Sección 5): cierre de sesión edge case directiva:137 con bucle de
     revalidación y nota de legado exento.
  + caja `cajaConcepto` con "información que reside EXCLUSIVAMENTE en Sessions/".
- **Pitfall resuelto (LaTeX):** `cajaConcepto` se declaró primero como `.style` de
  `\tcbset`; `\begin{cajaConcepto}` falló con `Environment undefined`. Corregido
  declarándolo como `\newtcolorbox` (coherente con todos los docs AGENTE_IA).
- Compilación en `.tmp/latex_build/` con `pdflatex` (2 pasadas): exit 0, sin
  errores `!`, 5 páginas. Se pulieron 7 de 9 `Overfull` (rombo `FECHA_PLANTILLA`
  ensanchado a text width 3.1cm, token `session_log_<run>.jsonl` con salto, rombos
  con texto más largo ensanchados). Quedan 2 Overfull < 7 pt dentro de nodos TikZ
  (cosméticos).
- PDF copiado a `docs/AGENTE_IA/faq_higiene_estado_sesion_flujo.pdf`; aux limpiado
  (solo .tex + .pdf en docs/).
- Verificación: `pdfinfo` (5 páginas) y `pdftotext` confirma presencia de todos los
  veredictos/nodos clave. Nota: el modelo de turno no soporta visión, así que la
  inspección visual del render quedó pendiente para el usuario.
- **Calibración de tamaños (diagrama 1, primera iteración):** reducción local de
  fuentes (nodos `\footnotesize`) y anchos de caja; solape real detectado por
  `pdftotext -bbox` entre el rombo `integrity` y la nota inferior → rombo
  compactado a `¿integrity OK?` (criterio trasladado a la nota), nota movida a
  (4.6,-5.6). Segunda iteración (petición "un poco más"): escala `scale=0.82,
  transform shape` → extent figura 248 pt, 0 solapes de texto.
- **Calibración de diagramas 2–5 (COMPLETADA):** mismo bloque de opciones que en el
  diagrama 1 (`scale=0.82, transform shape`, fuentes `\footnotesize` en
  terminador/proceso/E-S/decisión, `\scriptsize` en notas, anchos reducidos;
  `entradasalida` text width 2.4cm). Correcciones de colisión resultantes:
  - Diagrama 3 (`check/clean`): nota `cor2` movida a (7.8,-6.9) (chocaba con
    `vigente` en la misma columna x=4.6; flecha dashed ahora from corrupto.east);
    tronco principal re-espaciado (integ -5.2, integral -6.9, ffin -8.6,
    huerfano -10.2, hue2 -11.6, fin -13.0) con columnas derechas alineadas
    (corrupto/cor2/vigente/vig2) para dar aire al rombo `existe` y la etiqueta `Sí`.
  - Diagrama 4 (`bitacoras`): columna B re-espaciada (c3 → 3 líneas, c5 -5.3,
    c6/c7 -6.8, c8 -8.6, nleg -10.6); columna A con n4 `font=\scriptsize`,
    `text width=2.9cm` en (0,-5.6) y n5 en (0,-7.4) (la línea "Actividades ·
    Pendientes" causaba doble wrap y la altura rompía el gap con el terminador).
  - Diagrama 2/5 sin ajustes necesarios (0 solapes desde el inicio).
  - Overfull residuales: pasan de 7 → 4, todos ≤ 6.8 pt dentro de nodos (cosméticos).
- **Verificación final por bbox (pdftotext -bbox páginas 1–5):** 0 solapes entre
  cajas de texto en los 5 diagramas; compilación exit=0, 5 páginas. PDF regenerado
  y aux limpiado (solo .tex + .pdf en docs/; build en `.tmp/latex_build` también
  limpiado).
- **Estrategia de etiquetas + tablas (COMPLETADA, confirmada por el usuario):**
  cada símbolo quedó con solo su etiqueta (`T/P/D/E/A/N` + número por tipo, por
  diagrama) y todo el texto explicativo se movió a una tabla `Leyenda de etiquetas`
  (tcolorbox `cajaContenido` + `tabularx` + booktabs) pegada bajo cada figura.
  - Dims globales del `tikzset` reducidas: terminador/proceso 1.6 cm, E-S 1.8 cm,
    decisión 1.5 cm (aspect 1.6), almacenamiento 1.7 cm, nota 1.8 cm, fuentes
    `\footnotesize` (nodo) / `\scriptsize` (nota, etiquetas de rama). Se eliminaron
    los 5 bloques locales de `/append style` y los overrides puntuales (`mt`, `c2`,
    `n1`, `n4`) que ya no aplican. Escala global 0.72 mantenida.
  - Leyenda inicial de símbolos ahora avisa: "cada símbolo lleva una etiqueta; su
    significado se expande en la tabla bajo cada diagrama".
  - Ramas Sí/No y "revalidar" se conservaron (anotaciones de arista).
  - Documento pasa de 5 a 6 páginas; compilación exit=0, único Overfull = 6.79 pt
    (cosmético pre-existente); 0 solapes de texto verificado por bbox en las 6
    páginas. Las tablas son `breakable` y rompen con normalidad (su primera fila
    queda pegada a la figura).

## Pendientes
- Revisión visual humana del PDF (el modelo no tiene visión) para validar el render
  final de los 5 diagramas con etiquetas T/P/D/E/A/N + tablas `Leyenda de etiquetas`
  (6 páginas), verificado con 0 solapes de texto por bbox.
- Opcional: si se quiere embeber estos diagramas en `higiene_estado_sesion.md`,
  añadir enlaces al PDF generado.
- Commit pendiente del trabajo de la sesión (bitácora + `.tex` + `.pdf`) — no se
  commitó porque el usuario no lo pidió.

---

## Anexo 2026-09-12 — Sincronización automática FAQ → diagrama (`flujo_sync_faq_flujo.py`)

### Tema
Automatizar la actualización de `docs/AGENTE_IA/faq_higiene_estado_sesion_flujo.{tex,pdf}`
cuando se edita el FAQ fuente `faq_higiene_estado_sesion.md`, respetando la
arquitectura de 3 capas (directiva + orquestador + execution).

### Decisiones (usuario)
1. Disparo: **comando con detección por hash** (`flujo_sync_faq_flujo.py`, opcional
   `--watch` con polling `--interval`) — se descartó el hook de `inotify`/watcher del
   RAG como disparador.
2. Regeneración: **híbrido** — campos conocidos inyectados deterministamente por el
   script; re-traducción semántica vía enrutador determinista + LLM (OpenRouter,
   consume créditos; el flujo avisa antes). El `.tex` vigente es la plantilla.
3. Nunca se regenera el `.tex` desde cero (falta de plantilla = código de error 4).

### Actividades (arquitectura 3 capas)
- **L1 — `directives/sync_faq_a_flujo.yaml`:** SOP con steps y edge cases (primer
  arranque sin snapshot = baseline sin LLM; metadatos/`Referencias cruzadas` ignorados;
  `--no-llm` con cambio estructural aborta intacto; fallo LLM nunca deja `.tex` a medias).
- **L2 — `flujo_sync_faq_flujo.py`:** sha256 del `.md` vs `.tmp/faq_flujo_sync.json`
  (si coincide → "Sin cambios"); si cambió → plan (aviso de créditos si
  `llm_necesario`), `regenerar`, compilar (`compile_latex_code`, 2 pasadas,)
  copy PDF → `docs/AGENTE_IA/`, verificar, escribir estado+snapshot `.tmp/faq_flujo_md_snapshot.md`,
  alerta `alert_user.py`. Efectivamente probado con `--watch` en foreground.
  Flags: `--watch --interval N`, `--force`, `--no-llm`, `--critico`, `--dry-run`, `--md/--tex/--pdf` (testeo).
- **L3 — `execution/regenerar_faq_flujo.py`:** (1) inyecta campos conocidos
  (FECHA_PLANTILLA ISO + header DD/MM/YYYY, modelo `deepseek-[\w.-]+`, `N antiguas`);
  (2) clasifica cambios con `difflib.SequenceMatcher` contra el snapshot de la sección
  md §1–§4 → bloques tex (marcadores `% ══ Sección N:`, U+2550; bloque 4 = hasta
  `\end{document}`): solo-campos → determinista; otro → semántico; (3) LLM quirúrgico
  devuelve `{"edits":[{"old","new"}]}`: valida `old` único en bloque, token estructural
  prohibido (`\begin{tikzpicture}`, `\section`, …) e invariante nº de `\node[` por
  bloque; escritura atómica. Códigos 0/2/3/4/5.
- **L3 — `execution/verificar_pdf.py`:** guardrail post-compilación — 0 errores `!`
  en `.log`, Overfull reportados (no bloquean), solapes de texto por
  `pdftotext -bbox` (SOLAPE_FRACCIÓN=0.35).
- **Ajuste aditivo `execution/compile_latex.py`:** nuevo parámetro `clean=False` en
  `compile_latex_code` para conservar el `.log` hasta que el orquestador verifique
  (compatible con `mcp_latex_server.py`, que usa el default `clean=True`).

### Verificación
- `py_compile` OK en los 3 scripts nuevos (fix de f-string con backslash en
  `count('\\node[')`).
- Pruebas unitarias de `_edits_validos`/`_aplicar_edits`: edit válido preserva
  invariante de nodos; `old` no-único rechazado; token estructural rechazado;
  `aplicar_campos_conocidos` inyecta fecha/modelo/N correctos.
- Baseline real establecido y restaurado tras pruebas (estado+snapshot respaldados).
- E2E en copias `/tmp` (sin tocar el entregable): cambio semántico en §2 →
  clasificación `llm` → 1 edit quirúrgico real aplicado (amplió nota `N1` con la
  resolución temporal de `time`, LaTeX válido, invariante OK) → compilación exit=0 →
  verificación `6 páginas, 0 errores, 1 Overfull (6.79 pt cosmético), 0 solapes`.
- Línea base: primera corrida crea snapshot/estado/log; corridas posteriores con
  md intacto reportan "Sin cambios en el markdown (hash idéntico)".

### Pendientes (anexo)
- Commit del trabajo de la sesión (bitácora + flujos/scripts/directiva + AGENTS.md)
  — no commitado porque el usuario no lo pidió.
- Inspección visual humana del PDF (el modelo no tiene visión) sigue pendiente.