# 2026-11-08 — examenes_privados

## Tema
Hacer privados por construcción los exámenes de los tres cursos: banco de preguntas
local ignorado por git + selección determinista de variante (`--variante N`).

## Contexto
En la sesión anterior se sacaron del repo los `.tex`/`.pdf` de los controles y se
reescribió el historial, pero los **enunciados seguían en `curso.yaml`**, que está
versionado. `git grep` lo confirmó: 12 enunciados en `CYBERSEGURIDAD`, 8 en
`LABORATORIO_I_FISICA` y 8 en `LABORATORIO_II_FISICA`, todos en `controles:`.
Mientras el descriptor los lleve, cualquier alumno con el enlace lee el examen.
Ocultar el PDF no servía: el texto estaba en el YAML.

## Decisiones (usuario)
1. Ocultar los exámenes en los **tres** cursos, no solo en ciberseguridad.
2. Reescribir el historial (`filter-repo` + `push --force`) para borrar los exámenes
   ya publicados (hecho en la sesión anterior).
3. La **rúbrica** se queda pública (es criterio de corrección, no la prueba).
   `evaluacion_final` sigue pública: solo declara secciones y puntajes, sin enunciados.
4. Banco de preguntas **local** en `cursos/*/evaluaciones/banco_preguntas.yaml`,
   ignorado por git, con variantes y `--variante N` determinista.
5. Los enunciados actuales se marcan **`comprometida`**: ya se publicaron, así que
   no se aplican nunca sin confirmación explícita. No se reescribe el historial una
   segunda vez.
6. La dimensión de auditoría `examen_filtrado` queda **aplazada** para otra sesión.

## Actividades

### Capa 3 — banco en `execution/generar_material_curso.py`
- Constantes `BANCO_PREGUNTAS`, `ESTADOS_BANCO` (`utilizable|borrador|comprometida`).
- `cargar_banco()`, `variantes_del_banco()`, `seleccionar_variante()` (sin número solo
  acepta exactamente una `utilizable`; ambigüedad = error, nunca "la primera"),
  `componer_controles()` (empareja por fase y orden; el banco aporta texto, el
  descriptor el puntaje y el tema), `validar_preguntas()` (matemática de los
  enunciados ya compuestos).
- `validar()` ahora **rechaza** `enunciado` en el descriptor (código 3), exige
  `puntaje` numérico > 0 y `tema` de texto.
- `cargar_banco()` y la composición viven en `main`: `--banco`, `--variante`,
  `--permitir-comprometida`; nuevo **código 6** (banco ausente/ilegible/incompatible
  o variante no aplicable). `--solo controles` sin banco falla a propósito.

### Capa 3 — migrador `execution/migrar_preguntas_a_banco.py`
- Cirugía **textual**, no round-trip YAML (los descriptores tienen 18/8/10 comentarios
  y `ruamel` no está instalado).
- Maneja las dos formas de item: `- enunciado:` (el guion se transfiere a la primera
  clave hermana; borrar la línea entera fusionaba mapas y hacía perder preguntas en
  silencio) y `enunciado:` dentro de un `- tema:`.
- Soporta escalares en línea y plegados (`>-`, LAB II).
- Verificación fuerte antes de escribir: recomponer el descriptor migrado con la
  variante creada debe devolver **exactamente** los controles originales.
- Idempotente (`ya_migrado`), no sobrescribe un banco existente sin `--forzar`.

### Migración ejecutada
- 12 + 8 + 8 enunciados movidos; `estado: comprometida`, `creada: 2026-11-08`.
- `.gitignore` línea 74: `cursos/*/evaluaciones/banco_preguntas.yaml`;
  `git check-ignore -v` apunta a ella en los tres cursos.
- Puerta de equivalencia: descriptor pre-migración (HEAD) vs. migrado + `--variante 1`
  → **10 de 10 `.tex` idénticos byte a byte** (`control_fase_*` y `evaluacion_final`).
  Los `.tex`/`.pdf` locales de LAB I/II estaban obsoletos (les faltaba
  `\usepackage{needspace}` del preámbulo actual, ajeno a esta migración); se
  regeneraron y los 10 PDF dan `ok`, 0 errores, 0 overfull.
- `git grep` de una frase del banco → 0 coincidencias en ficheros versionados;
  0 líneas `- enunciado:` en los tres `curso.yaml`.

### Capa 2 — `flujo_disenar_curso.py`
- Reenvía `--banco`, `--variante`, `--permitir-comprometida`; los registra en el
  `run_state` y en la salida (consola y JSON); `DIAGNOSTICO[6]` documenta el nuevo
  código de salida.

### Capa 1 — `directives/disenar_curso.yaml` v1.2
- Nuevos inputs `banco`, `variante`, `permitir_comprometida`.
- `controles[].preguntas[].enunciado` pasa de "campo opcional" a **prohibido**.
- Sección `banco_preguntas:` con esquema, reglas y protecciones.
- Cinco casos límite nuevos (banco ausente, variante ambigua, comprometida/borrador,
  conteo o puntaje desajustado, reincidencia de fuga, migración repetida).

### Pruebas
`execution/test_generar_material_curso.py`: 72 → **103 aserciones, 0 fallos**. Nuevas:
descriptor público rechaza enunciado, elección determinista de variante, ambigüedad,
estructura inválida, composición por orden (conteo/fase/puntaje), y
`test_descriptores_reales_sin_enunciados` que vigila los tres `curso.yaml` de git.

## Pendientes
- Crear la **variante 2 `utilizable`** de cada curso: hoy los tres bancos solo tienen
  la 1 `comprometida`, así que `--solo controles` sin `--variante` falla (correcto,
  pero hay que escribir los exámenes nuevos antes de usar el flujo con alumnos).
- Dimensión `examen_filtrado` en `flujo_auditar_repo.py` (aplazada por decisión del
  usuario): detectaría enunciados en cualquier fichero versionado, no solo en el
  descriptor.
