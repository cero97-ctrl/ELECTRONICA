# 2026-11-06 — curso laboratorio i fisica

## Tema
Curso completo LABORATORIO I DE FÍSICA: descriptor `curso.yaml` y material
generado con el flujo determinista de 3 capas.

## Contexto
- El repositorio ya tenía el curso LABORATORIO II DE FÍSICA resuelto con el
  generador `execution/generar_material_curso.py`; se reutiliza esa capa 3 en
  lugar de escribir documentos a mano.
- Los materiales fuente del nuevo curso estaban dispersos y se movieron a
  `cursos/LABORATORIO_I_FISICA/docs/`: temario escaneado, teoría de error,
  análisis del péndulo (con sus 21 pares de datos reales) y capturas de datos.
- El OCR del temario (26 páginas) se completó en una sesión previa y es la
  fuente de verdad de las seis prácticas. El OCR del escaneo
  `teoria_medicion_error_grafica.pdf` quedó bloqueado por cuota Gemini
  (`429 RESOURCE_EXHAUSTED`), sin páginas en caché.

## Decisiones (usuario)
1. Semanas 1 a 4: teoría de errores y análisis gráfico (talleres).
2. Semanas 5 a 10: una práctica experimental por semana (seis prácticas).
3. Evaluación sobre 10, nota mínima 5, pesos 60/20/20 (talleres y prácticas,
   controles, final).
4. El orden de las prácticas sigue el temario: volumen, densidad, centro de
   masa, ley de Hooke, péndulo simple y enfriamiento.
5. No editar los `.tex` generados: todo cambio de contenido va al YAML.

## Actividades
- Se extendió `execution/generar_material_curso.py` con `semana.tipo`:
  - `etiqueta_semana()` devuelve `Taller` para `tipo: teoria` y `Práctica` en
    el resto.
  - La banda y el título del documento, el plan semanal y el nombre del job
    (`taller_NN` / `practica_NN`) usan esa etiqueta.
  - El README del curso lista `Taller:` o `Práctica:` según el tipo.
  - `validar()` rechaza cualquier tipo fuera de `practica`/`teoria`.
- Se corrigieron dos defectos del generador detectados al reutilizarlo:
  - `evaluacion_final.condiciones` se imprimía como `str(lista)` (corchetes y
    comillas de Python en el PDF); ahora una lista se emite como `itemize`.
  - Las instrucciones del control decían «límites legales» (vocabulario de
    ciberseguridad); ahora se pueden sobrescribir con
    `textos.instrucciones_control`.
  - Se neutralizaron dos frases que decían «práctica» donde el curso puede
    tener talleres («revisado al finalizar cada semana», «la entrega se
    considera válida»).
- Se documentaron en `directives/disenar_curso.yaml` los campos
  `semana.tipo`, `textos.instrucciones_control` y el nuevo patrón de nombres
  de artefactos, con su caso límite.
- Se amplió `execution/test_generar_material_curso.py` con tres pruebas:
  condiciones del final como lista (sin `repr`), taller rotulado como Taller y
  tipo inválido rechazado. Total: 60 aserciones, 0 fallos.
- Se escribió `cursos/LABORATORIO_I_FISICA/curso.yaml` con 10 semanas, 3 fases,
  7 resultados de aprendizaje, 4 roles rotativos, rúbrica de 7 criterios,
  2 controles, evaluación final, 3 apéndices, bibliografía y políticas.
- Se generó el curso completo con
  `python3 flujo_disenar_curso.py --curso cursos/LABORATORIO_I_FISICA/curso.yaml`:
  16 documentos LaTeX, 16 PDF compilados sin errores, más
  `rubrica_practica.yaml`, README y `laboratorio/`.
- Se verificó el contenido generado: no queda vocabulario de ciberseguridad,
  `taller_01..04` y `practica_05..10` tienen el rótulo correcto, el plan
  semanal distingue Taller/Práctica y el final lista sus condiciones.
- Revisión visual página a página (render a PNG de las páginas con figuras y
  tablas) detectó y corrigió seis defectos del descriptor, no del generador:
  - taller_03 y taller_04: la recta "ajustada" no era el ajuste de sus propios
    puntos (todos quedaban por encima); se recalculó por mínimos cuadrados con
    NumPy y se dibujó la recta real, con residuales visibles en taller_04 y
    ejes con unidades (`L` cm, `T^2` s^2) en taller_03.
  - practica_05: línea suelta sin sentido dentro de la probeta; eliminada.
  - practica_06: el sólido y su rótulo quedaban tapados por el relleno del agua
    (orden de dibujo); se reordenó y la balanza pasó a ser una caja con su
    hilo hasta el sólido sumergido.
  - practica_07: el punto de apoyo estaba en el punto medio y no en el centro
    de masa de 100 g y 200 g; movido a x = 6,2 y bloques de alturas distintas.
  - practica_10: la figura mostraba agua y un termómetro fuera del recipiente;
    redibujada como dos cilindros sobre base aislante con la sonda dentro del
    cuerpo grande, que es el montaje real del enfriamiento.
- Defecto del generador encontrado en la revisión: la tabla "Distribución del
  puntaje" de los controles derivaba el tema de las primeras palabras del
  enunciado (`_tema_de`), produciendo etiquetas telegráficas como «reporta
  longitud Calcule error». Ahora cada pregunta acepta `tema:` editorial en el
  descriptor y `_tema_de` queda solo como respaldo; documentado en
  `directives/disenar_curso.yaml` y congelado en
  `test_tema_de_control_es_editorial`. Las ocho preguntas de los dos controles
  llevan su tema declarado.
- `textos.plan_entrega` decía que el docente revisa «al finalizar la semana
  siguiente», en contradicción con el sílabo («al finalizar cada semana»);
  unificado. También se quitaron los backticks de `semana_NN`: en LaTeX de modo
  texto el backtick compone como acento grave, no como comilla.
- Tras los cambios: 62 aserciones OK y regeneración completa (16 LaTeX,
  16 PDF sin errores).
- Limpieza de `docs/` a petición del usuario: los pares derivados
  `Teoria_de_Error_v3.0.tex/.pdf` y `Pendulo_Simple_Analisis.tex/.pdf` se
  movieron a `docs/_derivados/` con un README que explica su procedencia y cómo
  recompilarlos; en `docs/` quedan solo fuentes, datos crudos y el artefacto
  `guia_estudiante`. Ningún fichero del curso los referenciaba.
- Commit `c6eb8d0` con todo lo anterior y push a `origin/master`.
- Aclaración del README tras la revisión del usuario en GitHub: la sección
  «Estructura del portafolio» se confundía con la estructura del repo del
  curso; se renombró a «Estructura del repositorio del grupo» vía
  `textos.titulo_estructura` (afecta README y guía a la vez, porque ambos la
  leen del descriptor). Regenerado con `--solo guia,readme`, commit `43dc13a`
  y push.
- Bug reportado por el usuario al revisar `control_fase_1.pdf`: la sección
  Preguntas imprimía la matemática cruda (`$L = 2{,}45 \{}pm 0{,}03$`). Causa:
  `tex_control` escapaba los enunciados con `_t` (texto plano) en vez de `_tm`.
  Arreglo: la lista de preguntas se renderiza con `math=True`, y
  `_validar_matematica` ahora custodia cada `preguntas[].enunciado` para que un
  subíndice suelto falle antes de compilar en vez de romper el PDF. Congelado
  en `test_enunciado_de_control_con_matematica_no_se_escapa` (66 aserciones OK)
  y documentado en la directiva. Regenerado con `--solo controles`; verificado
  con pdftotext que los 16 PDF quedan sin fugas de LaTeX. Commit `950471d` y
  push.
- A petición del docente (sus estudiantes arrancan la semana próxima), las
  instrucciones de arranque de la semana 1 se vaciaron en un entregable propio:
  `cursos/LABORATORIO_I_FISICA/docs/semana_1.tex/.pdf` (2 páginas,
  PREAMBULO_INFOGRAFIA, compilado en `.tmp/latex_build/semana_1` y copiado el
  PDF). Es un documento redactado a mano, no un artefacto del flujo: se edita
  directamente el `.tex`. Se compactó el texto para evitar una página 3
  huérfana con solo la caja final. Commit `00d59db` y push.
- El docente informó que tiene **dos grupos, no cuatro**. Ajuste en
  `curso.yaml` (`meta.grupos`, `meta.modalidad`, `grupos.cantidad` y
  `grupos.asignacion`) y regeneración completa (16 PDF). El cambio destapó dos
  defectos del generador que solo existían porque 4 grupos coincidía con 4
  roles: el validador exigía `len(roles) == cantidad`, y la tabla de rotación
  traía fijas cuatro columnas «Grupo 1..4». Como los roles rotan DENTRO de cada
  grupo (el propio YAML dice «cada integrante haya ocupado los cuatro roles»),
  las columnas pasan a ser posiciones de integrante (dinámicas) y `cantidad`
  queda libre, con chequeo de entero positivo. Congelado en
  `test_roles_por_integrante_independientes_del_numero_de_grupos`
  (70 aserciones OK). Verificado: sílabo «2 grupos de trabajo», guía «El curso
  trabaja con 2 grupos» y tabla Integrante 1..4; sin restos de «4 grupos» ni
  «Grupo 4» en el árbol generado.

## Pendientes
- Commitear y pushear el arreglo de la matemática de los controles (quedó como
  cambio de trabajo: generador, test, directiva, los dos PDF de control y esta
  bitácora).
- OCR de `cursos/LABORATORIO_I_FISICA/docs/teoria_medicion_error_grafica.pdf`
  cuando se recupere la cuota Gemini; su contenido se cubrió con
  `Teoria_de_Error_v3.0.md` y física estándar, pero conviene contrastarlo.
- Revisión visual pendiente de las páginas sin figura: guía completa,
  apéndices, rúbrica y README del laboratorio (las páginas con figuras y
  tablas de los 16 documentos ya se revisaron y corrigieron).
- Decidir si la práctica 6 y la evaluación final comparten la semana 10; hoy
  están así por mandato de las diez semanas, pero concentra dos instrumentos.
- La prosa de rotación de roles promete que «en la fase 3 cada integrante haya
  ocupado los cuatro roles», pero con tres fases con roles cada integrante solo
  cubre tres; conviene corregir esa frase del descriptor (o añadir una cuarta
  rotación) cuando el docente lo apruebe.
