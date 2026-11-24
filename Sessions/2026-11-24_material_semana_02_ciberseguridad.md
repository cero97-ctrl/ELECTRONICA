# 2026-11-24 — material_semana_02_ciberseguridad

## Tema
material_semana_02_ciberseguridad

## Contexto
- Tras el saneamiento de estado de esta misma fecha, el usuario pidió que los
  estudiantes trabajen ya los temas de la semana 02 de Ciberseguridad y que se
  prepare ese material.
- El material ya existía y estaba versionado, pero el commit `6c84838`
  (`fix(latex): forzar texto claro en bloques lstlisting del estilo infografia`)
  cambió la plantilla compartida y los PDF nunca se habían regenerado: los
  bloques de código quedaban con texto oscuro sobre fondo oscuro.
- Se mantuvo la política de privacidad del repo público: esta bitácora no
  contiene nombres, cédulas ni calificaciones.

## Decisiones (usuario)
1. Alcance confirmado en una sola respuesta: regenerar y verificar, armar un
   paquete para estudiantes, redactar una guía teórica nueva y crear las
   infografías SEM_2.
2. Las cuatro infografías fallaron primero con el modelo de imagen por defecto
   (`Model is unavailable`). El usuario autorizó explícitamente
   `opencode/gemini-nano-banana-2.1`; con ese modelo se generaron las cuatro.
3. La guía teórica se construyó como flujo nuevo con sus 3 capas (directiva,
   orquestador, script de ejecución) más pruebas, para no romper la arquitectura
   determinista del proyecto. El contenido vive en `curso.yaml`, fuente de verdad.
4. Sin commit: todo queda en el árbol de trabajo hasta nueva autorización.
5. Se respeta `evaluar_corte: true` desde la semana 02: la fecha de entrega sí
   cuenta. La excepción de la semana 01 no se replica.

## Actividades
- `flujo_instrucciones_semana.py --semana 2` y `--semana 2 --grupo 1..4` →
  regenerados `docs/semana_02.{tex,pdf}` y `docs/grupo_{1..4}_02.{tex,pdf}`.
  Verificación: 0 líneas `!`, 0 `Overfull \hbox`, `verificar_pdf.py` en `ok`
  (5/5/5/4/4 páginas) y sha256 idéntico en una segunda corrida aislada.
- `flujo_disenar_curso.py --solo practicas` en `.tmp/` → se copiaron solo
  `practica_02.{tex,pdf}` al curso (mismo parche de estilo, sin tocar las demás
  semanas). `.tex` byte-idéntico al de la réplica.
- Paquete `docs/PAQUETE_SEMANA_02/`: 7 PDF con nombres `01_` a `07_` más un
  `README.md` con contenido, corte, estructura de entrega, reglas de privacidad
  y comandos de regeneración. Cada PDF es copia byte-idéntica de su canónico.
- Cuatro infografías en `docs/INFOGRAFIAS/SEM_2/` (rojo, azul, púrpura, legal y
  reporte), 1376×768 JPG, verificadas con PIL. Se actualizó
  `docs/INFOGRAFIAS/README.md` con la convención de la carpeta SEM_2. No se
  versionan: `.gitignore` ya excluye `cursos/*/docs/INFOGRAFIAS/**`.
- Flujo nuevo de guía teórica: `directives/guia_teorica.yaml`,
  `flujo_guia_teorica.py`, `execution/generar_guia_teorica.py` y
  `execution/test_guia_teorica.py` (65 aserciones, 0 fallos). `curso.yaml`
  recibió únicamente la clave `teoria:` de la semana 02 (5 temas, tabla de
  primitivas, checklist y cierre).
- `docs/teoria_02.{tex,pdf}` generado: 8 páginas, 0 líneas `!`, 0 overfull,
  `verificar_pdf.py` en `ok`, sha256 idéntico entre el entregable y una réplica
  en `.tmp/`. Copiado al paquete como `07_guia_teorica_02.pdf`.
- `cursos/CYBERSEGURIDAD/README.md`: documenta los flujos por semana y el
  paquete del estudiante.
- Incidencias del subagente resueltas: `list-check` no existe en FontAwesome 5
  (→ `clipboard-list`), `cajaContenido` es un `.style` y no un entorno, y una
  aserción del test buscaba el nombre en la definición del preámbulo.

## Pendientes
- No hacer `git add` ni `git commit` sin autorización explícita del usuario.
- Revisión visual de los 7 PDF del paquete y de las 4 infografías SEM_2 por
  parte del usuario (el agente no puede ver imágenes).
- Los 2 archivos sin seguimiento de Laboratorio I quedaron fuera de alcance.
- Del backlog, NO abordado aquí: evaluar los informes de la semana 02 con
  `evaluar_corte: true` cuando lleguen las entregas, y la publicación manual de
  notas solo si el usuario lo decide.
