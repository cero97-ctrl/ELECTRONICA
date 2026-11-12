# 2026-11-12 — exámenes web HTML: Púrpura y Legal

## Tema
Publicar los cuestionarios de los grupos Púrpura y Legal y Reporte Técnico, cerrando
los cuatro roles del curso en GitHub Pages con recolección por Worker.

## Contexto
- Continuación de `Sessions/2026-11-11_examenes_web_html.md` (Rojo y Azul ya
  publicados). El usuario sustituyó por la mañana el markdown de Púrpura por una
  versión reformulada y pidió proceder con los dos grupos restantes.
- El archivo anterior de Púrpura traía dos defectos que impedían la publicación: las
  opciones de la pregunta 10 en formato `* **A)**` (el parser leía 0 opciones) y la
  negrita partida en el enunciado. La versión reformulada los corrigió, así que no
  hizo falta extender `OPCION`.
- Legal llegó con 6 `;` de ancho completo (U+FF1B) en el pie y Púrpura con 5: el mismo defecto que ya
  había aparecido en Rojo y Azul y que hace fallar `verificar_texto.py`.

## Decisiones (usuario)
1. Sustituir el markdown de Púrpura en lugar de que el agente lo normalizara.
2. Proceder con Púrpura y Legal sin esperar respuesta a las preguntas planteadas
   sobre el formato de opciones (resuelto por el archivo nuevo) ni sobre el commit.
   Lo único que se asumió sin confirmación explícita: **no** barajar las respuestas
   de Legal. Se dejó documentado el riesgo (contestar «A» en todo da 10/10) y se
   publicó tal cual; el usuario había tenido ocasión de redistribuir la clave al
   reformular Púrpura y no lo hizo.

## Actividades
- `execution/dividir_cuestionario.py` endurecido: normaliza U+FF1B → `; ` al escribir
  (única excepción a «el canónico se conserva tal cual»), informa cuántos cambió y
  reporta `normalizaciones` en el JSON. Tests 43 → **50/50**. Trampa: la propia
  documentación del script no puede llevar el carácter literal o el verificador la
  marca a ella.
- Divididos ambos canónicos (Púrpura 5 normalizaciones, Legal 6) y verificada la ida
  y vuelta con `cargar_clave()`.
- `wrangler.jsonc`: `env.purpura` (`cuestionarios-worker-purpura`) y `env.legal`
  (`cuestionarios-worker-legal`), con vars repetidos. Desplegados con `--env` y
  `--actualizar-fuente`; la guarda de `CUESTIONARIO_ID` aceptó el slug de 38
  caracteres de Legal sin cambios.
- HTML generados (alumno 25 930 B / 26 376 B, 0 `const CLAVE`, `entrega_url` al
  Worker correcto) y publicados con `--push`: el índice pasó a 4 cuestionarios.
- E2E de ambos Workers: entrega falsa 10/10, archivada sin la clave y borrada
  después. Acta en seco por fuente: 0 entregas. `/salud` 200 en los cuatro Workers.
- En vivo: 4 `_alumno.html` 200 con sha256 idéntico al local (`c7b236f0…` Púrpura,
  `b08ab406…` Legal) y 0 `const CLAVE`; 4 `_docente.html` 404.
- `AGENTS.md` actualizado (test del divisor 50 aserciones y los entornos
  `purpura`/`legal`). `verificar_texto.py` sin hallazgos.

## Pendientes
- **Commit sin autorizar**: ~26 archivos (4 flujos, 5 scripts de `execution/` y sus
  tests, 4 directivas, `Proyectos/cuestionarios-worker/`, `.gitignore`, `AGENTS.md`
  y las dos bitácoras). Comprobar divergencia con `origin/master` antes de usar
  `update_repo.sh` (hace `pull --rebase` antes del commit y falla con árbol sucio).
- **Claves degeneradas**: Púrpura `A B A A A A A A A A` y Legal
  `A A A A A A A A A A`. Si se usan en clase, repartir las respuestas antes.
