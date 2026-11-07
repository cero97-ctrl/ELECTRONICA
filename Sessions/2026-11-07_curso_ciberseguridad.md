# Sesión 2026-11-07 — Curso de ciberseguridad

## Tema
Instrucciones paso a paso de la semana 1 para los cuatro grupos del curso.

## Contexto
Los estudiantes inician actividades la semana siguiente y ya están conformados en
cuatro grupos. El usuario pidió un documento único (no por grupo) con lo que deben
hacer esta primera semana, guardado como `docs/semana_01.{tex,pdf}`.

## Decisiones (usuario)
- Un solo documento para todo el curso, en `docs/`, no uno por grupo.
- Nombre exacto del fichero: `semana_01`.

## Actividades
- Nuevo flujo de 3 capas: `directives/instrucciones_semana_curso.yaml`,
  `flujo_instrucciones_semana.py` y `execution/generar_instrucciones_semana.py`.
- Emitido `cursos/CYBERSEGURIDAD/docs/semana_01.{tex,pdf}` (4 páginas): tareas antes
  de la sesión (crear repositorio privado, añadir al docente, README, Docker y nmap,
  clonar y verificar los tres contenedores), objetivo, contenidos, escenario, los
  cinco pasos, herramientas, tabla grupo-rol de la semana 1, estructura y reglas de
  entrega, rúbrica de la semana y lista de verificación.
- Verificado: `verificar_pdf` ok (4 páginas, 0 solapes, 0 overfull) y segunda corrida
  idéntica byte a byte (sha256 `c0441b47…`).
- **Defectos de datos corregidos en `curso.yaml`** (los imprimía el material nuevo):
  tres ítems de `entregas.reglas` con `:` sin comillas se habían parseado como mapas
  y salían como `{'clave': 'valor'}`; y dos `contenidos` de las semanas 1 y 9 eran
  reprs de dict colados como texto. Se entrecomillaron/reescribieron y se añadió
  validación que rechaza ítems que no son texto en `entregas.estructura/reglas` y en
  `contenidos`.
- Regenerado todo el material (17 `.tex`/17 PDF, 0 problemas) y las tareas de la
  fase 1 para que práctica, guía, tarea y semana cuenten lo mismo.
- Añadido el flujo a `AGENTS.md`.
- **Registro de entregas corregidas** (petición del usuario): creada
  `cursos/CYBERSEGURIDAD/evaluaciones/resultados/` con `actas.csv` (cabecera fija) y
  README que documenta la convención local — misma pauta que Laboratorio II, que ya
  ignoraba `cursos/*/evaluaciones/resultados/**` salvo el README (el repo es público).
- Nuevo flujo de 3 capas para anotar cada entrega: `directives/registrar_resultado_curso.yaml`,
  `flujo_registrar_resultado.py` y `execution/registrar_resultado.py`. Copia el informe
  a `semana_NN/grupo_N/`, deriva el rol de la rotación del descriptor, valida la nota
  0..10 y rechaza semana+grupo duplicado (código 4) salvo `--reemplazar`; el acta se
  escribe de forma atómica. Probado en `.tmp/`: 0 fuera de rango → 3, válido → 0,
  duplicado → 4, `--reemplazar` sustituye la fila y conserva el documento archivado,
  semana 10 sale `individual` y semana 11 → 3.
- Registrado en `AGENTS.md`.
- **Glosario en `semana_01`** (petición del usuario): añadido `glosario` al
  descriptor (18 términos con definición) y `semana 1 → glosario: [18 nombres]`; el
  generador resuelve los nombres contra el catálogo, valida que existan y emite la
  sección "Glosario de la semana" en una página propia (`\clearpage`, `longtable`
  `\small`, cabecera repetida). Un término desconocido es código 3, no un texto
  inventado. PDF: 5 páginas, 0 solapes, 0 errores, idéntico entre corridas.
- Aclarado en la sección de roles que el trabajo es **independiente** (cada grupo en su
  propio repositorio y laboratorio) y que la comparación es en clase, al final; el
  texto vive en el generador, así que aplica a todas las semanas.
- De paso, corregido el punto doble de la caja "Recuerda" (`no se corrige..`): el
  corte se imprime sin duplicar el punto final.

- **Ejemplo de trabajo por grupo** (petición del usuario: "guarda un ejemplo del grupo
  1, semana 1"): se extendió el flujo semanal existente en vez de escribir un `.tex` a
  mano. `semana.ejemplos` es dato del descriptor (`grupo`, `titulo`, `intro`, `bloques`,
  `tabla` con `anchos` en cm, `entregable`, `estructura`, `comprobaciones`, `avisos`);
  `execution/generar_instrucciones_semana.py` gana `--grupo` y emite
  `docs/grupo_N_NN.{tex,pdf}`; el orquestador `flujo_instrucciones_semana.py` lo pasa
  tal cual. Grupo sin ejemplo declarado → código 3 (probado con grupo 2).
- Tres defectos vistos en el PDF y corregidos en el generador, no en el `.tex`:
  los títulos numerados a mano duplicaban la numeración de `\subsection`; un título al
  pie de página quedaba separado de su tabla (se añadió `needspace` al preámbulo
  compartido y un helper `_seccion_ejemplo`); la tabla de 7 columnas se salía 126 pt del
  margen (ahora `anchos` en cm + `\footnotesize`, y la validación exige `anchos` cuando
  hay más de 4 columnas).
- De paso corregido el defecto del rol: el ítem `en_la_practica` del rol Rojo estaba
  entrecomillado en YAML (se imprimía como mapa con comillas); ahora es texto y la
  validación de `en_la_practica` lo detecta en material y tareas.
- Resultado: `docs/grupo_1_01.pdf` de 4 páginas, 0 solapes, 0 `Overfull \hbox`,
  0 errores y bytes idénticos entre corridas; `semana_01` sigue en 5 páginas.

- **Ejemplos de los grupos 2, 3 y 4** (petición del usuario): mismos esquema y flujo que
  el del grupo 1, con el ángulo de cada rol: Azul mide línea base, aplica el control más
  barato y entrega el diff antes/después; Púrpura escribe la regla de detección antes de
  ejecutar y entrega la tabla de lo ejecutado frente a lo detectado; Legal comprueba
  alcance, anonimiza con sustitución explícita, sella la cadena de custodia e integra
  técnico y ejecutivo. Los tres salen en `docs/grupo_{2,3,4}_01.{tex,pdf}`, 4 páginas
  cada uno, 0 errores, 0 solapes, 0 overfull y bytes idénticos entre corridas.
- Trampa YAML nueva encontrada y congelada en la directiva: una celda `No` sin comillas
  es el booleano `False` y el PDF imprimía "False" en la tabla. Toda celda que sea
  palabra reservada de YAML va entrecomillada; la validación no puede distinguirla de un
  booleano legítimo.
- Mejora del generador: el ancho por defecto de las tablas de ejemplo ahora descuenta los
  `\tabcolsep` (antes una tabla de 4 columnas sin `anchos` se salía del margen), y la
  validación rechaza `anchos` cuya suma no quepa en 16,6 cm.

## Pendientes
- `nota_minima: 5` confirmada y ya consta en `curso.yaml` (bloque `evaluacion`, escala 10).
- Commit del trabajo (no se pidió explícitamente): incluye el fix del rol Rojo, el
  preámbulo con `needspace`, el flujo `--grupo` y sus artefactos.
- Repetir el patrón `--semana N` para las semanas 2 a 10 y escribir sus `ejemplos`
  cuando toque.
- Commiteado y empujado todo el trabajo del día como `47b77c8` (43 archivos): ejemplos
  por grupo, flujo `--grupo`, fixes del generador y rol Azul corregido.
- Corregida la contradicción del rol Azul (decisión del usuario): `descripcion` y el
  primer ítem de `en_la_practica` ya no dicen "parte de la evidencia del Rojo" sino "de
  su propia captura cruda" / "su propia evidencia cruda". Regenerado todo lo que imprime
  el rol: material completo (20 artefactos), tareas de la fase 1, `semana_01` y los cuatro
  ejemplos; 0 errores y 0 overfull en todos los logs, y `semana_01`/`grupo_2_01`
  idénticos entre corridas.
