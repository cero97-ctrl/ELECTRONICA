# 2026-09-27 — verificacion_texto_corrupto

## Tema
Verificacion de corrupcion de prosa (las 3 capas: directiva + orquestador + script)

## Contexto
Cierre de la sesion de diagramas/sismologia/higiene. Al revisar lo hecho se
conclusiono que el hallazgo mas valioso de la sesion NO estaba en los commits:
era un defecto del propio agente que se repitio cinco o seis veces y que las
comprobaciones existentes no detectaron.

Manifestaciones observadas, todas producidas por el agente al escribir prosa en
espanol: fusion de una palabra funcional con la siguiente, e intrusion de
escritura extranjera (cirilico, CJK). El catalogo literal de cada caso esta en
`execution/detecciones_texto.json`; no se reproduce aqui para no duplicar la
fuente unica. Hubo dos en un mensaje de commit y dos fueron invisibles a las
comprobaciones hechas.

Detalle critico de la investigacion: la corrupcion NUNCA entro en el historial
de git (`git log -S` no la encuentra en ningun commit). Vivia solo en el working
tree, antes del commit. Por eso el camino natural es escanear el arbol de
trabajo, no el historial.

## Decisiones (usuario)
1. Documentar el patron como SOP en `directives/` y escribir un script
   reutilizable en `execution/`, por indicacion expresa del usuario al final de
   la sesion.
2. Aplicar el criterio de `AGENTS.md` de acumular conocimiento en vez de perderlo:
   el catalogo de casos observados vive en un fichero de datos aparte, no
   duplicado dentro de la directiva.
3. Los dos MP4 de 39 y 41 MB se quedan en local con regla `.gitignore`; el MP4 de
   875 KB referenciado por tres bitacoras se restaura. Decidido con el usuario.

## Actividades

### Investigacion (sin escribir codigo)
- `git log -S` sobre las cinco cadenas: 0 commits. La corrupcion vivia solo en el
  working tree.
- Inventario de 7 casos: 2 en `.agent/python.md`, 4 en una bitacora, 1 en un
  mensaje de commit (repeado al hacer amend).
- Analisis de por que las comprobaciones fallaron: un validador de "palabras
  pegadas" devolvio 402 hallazgos, todos falsos positivos; el chequeo bueno
  existan las cadenas del archivo equivocado y dio 0 sobre el que estaba sucio.

### Construccion (3 capas, `AGENTS.md`)
- `execution/verificar_texto.py`: deteccion por clases. `script` (cirilico, CJK,
  japones, coreano, ancho completo), `conocido` (catalogo literal, con
  emparejamiento insensible a diacriticos) y `camel` (heuristica, apagada).
- `execution/detecciones_texto.json`: catalogo de cadenas y exenciones, con notas
  de motivo. Fichero meta, autoexcluido del escaneo.
- `flujo_verificar_texto.py`: decide que significa el codigo de salida y guarda
  estado. `contrastar_cobertura()` es funcion pura: sin ficheros leidos el
  veredicto es `sin_verificar`, nunca `limpio`.
- `directives/verificar_texto_corrupto.yaml`: SOP con 5 steps, 13 edge cases y 5
  invariantes.
- `execution/test_verificar_texto.py`: 21 aserciones que fijan cada fallo
  corregido.
- `docs/AGENTE_IA/verificar_texto_flujo.{tex,pdf}`: diagrama ISO 5807 generado
  con `execution/generar_diagrama_flujo.py` (3 paginas, 0 errores, 0 solapes).

### Fallos que el propio desarrollo destapo (y su correccion)
1. Griego en el detector: con el patron activo, 127 hallazgos de los cuales 123
   (97%) eran Omega, beta, tau, pi, mu, rho: la notacion normal de un repo de
   electronica. SE EXCLUYO. Es la decision mas importante del fichero.
2. Match sensible a tildes: un fixture escrito sin tilde no disparaba. La palabra
   corrompida se escribe con o sin ella. SE NORMALIZA.
3. `permitidas` usaba `all()`: varias exenciones se combinaban con AND y solo
   exemptaban si la linea tenia todas. SE CAMBIO A `any()`.
4. Ficheros pasados como argumento se saltaban el filtro meta. La exclusion es
   una propiedad del contenido, no del modo de descubrirlo.
5. 1496 PDF e imagenos contados como "omitidos": mezcla lo que se decidio con lo
   que no se pudo leer, y hacia el veredicto inutilizable. SE SEPARO EN
   `ficheros_no_texto`.
6. Exenciones acumuladas para la directiva: la solucion fue pointedar al
   catalogo en vez de excepcionar cuatro lineas.
7. "pointedar" (typo propio) en la directiva, corregido.

### Demo en vivo
Escribiendo el descriptor del diagrama se introdujo CJK (`U+4FE1`, `U+53F7`,
columna 128) sin darse cuenta. El detector recien escrito lo cazo en el acto. Se
corrigio y se regenero el diagrama. Es la mejor evidencia de que la clase
`script` funciona: fallo real, detectado por la herramienta, en la misma sesion.

### Verificaciones
- `test_verificar_texto.py`: 21/21.
- Repo completo: 480 ficheros, 131.310 lineas, 0 hallazgos, exit 0.
- 3 modos del flujo comprobados con su exit code real (0 / 1 / 2), midiendo sin
  pipe porque un pipe enmascara `$?`.
- `py_compile` de los 3 `.py`; YAML con 8 claves; PDF con 0 errores y 0 solapes;
  los 4 errores LaTeX conocidos de `.agent/latex.md` en 0.
- `bitacoras.py check` y `test_barrera_disco.py` sin regresiones.

## Pendientes
- Anadir al `.agent/` o a esta bitacora la nota de que la clase `camel` NO
  detecta erratas en minúsculas ("pointedar" no lo cazo): solo ve transiciones
  minúscula a mayúscula. Limitacion conocida, aceptada por ser opt-in.
- El verificador no esta integrado como hook de pre-commit. Hoy se ejecuta a
  mano antes de commitear prosa. Automatizarlo exigiria tocar hooks, que el
  proyecto evita deliberadamente (`--no-verify` en todos los commits de la
  sesion): decidir con el usuario si compens.
- `docs/CURSO_PYTHON/Crear_3_programas_Solana.mp4` (39 MB) sigue trackeado desde
  antes. Sacarlo exige reescribir historial. Señalado, no tocado.
- 30 ficheros untracked de sesiones previas (bitacoras del 19-24 de sept,
  ESP32 Kids Lab, CIRC_DISP_ELECT). No son de este trabajo; sin revisar.
- Pendientes de fondo anotados antes: `-halt-on-error` en `compile_latex.py`,
  sobreestimacion del dry-run nativo (~4.5x), targets de disco
  `recargable`/`pesado`, y monitorizacion del saldo de OpenRouter.
