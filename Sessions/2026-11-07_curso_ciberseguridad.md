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
- De paso, corregido el punto doble de la caja "Recuerda" (`no se corrige..`): el
  corte se imprime sin duplicar el punto final.

## Pendientes
- Confirmar `nota_minima: 5` con la institución.
- Commit del trabajo (no se pidió explícitamente).
- Repetir el patrón `--semana N` para las semanas 2 a 10 cuando toque.
- Commit del registro de resultados: no se pidió; queda en el árbol de trabajo.
