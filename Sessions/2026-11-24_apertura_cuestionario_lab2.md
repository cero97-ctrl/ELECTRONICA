# 2026-11-24 — apertura_cuestionario_lab2

## Tema
Apertura y cierre del cuestionario web de Laboratorio II de Física (24-nov-2026).

## Contexto
- El usuario indicó: «Hoy a las 8:00 am hay que abrir el cuestionario del
  "Laboratorio II de Física"».
- Las bitácoras del 21-nov (`repo_semilla_estudiantes_lab2`,
  `reemplazo_cuestionario_lab2_nuevas_preguntas`,
  `reanudacion_cuestionario_laboratorio_ii_fisica`) dejaron registrado el
  recordatorio: flip a `public` el 24-nov antes de las 08:00 VET y volver a
  `private` al cierre.
- Verificación en vivo a las 05:41 y 06:30 VET (antes de cualquier cambio):
  repo `cero97-ctrl/cuestionarios-lab2` en `private`, `updated_at` 18-nov,
  URL `https://cero97-ctrl.github.io/cuestionarios-lab2/` en **404**;
  Worker `cuestionarios-worker-lab2/salud` → `ok:true`, `abierta:false`
  («todavía no empieza»), `inscritas:3`; ventana `12:00Z–13:05Z` =
  08:00–09:05 VET.
- Hallazgo que cambia el comando previsto: el HTML subido está desactualizado
  (blob SHA `7f55ff7e85552a653a179c6a22766abef0c6bcfd`, 36 011 bytes, versión
  del 18-nov) frente al local (`a75d1b80384675e30265badf05306922101d07e2`,
  33 617 bytes, 10 preguntas nuevas del 21-nov). Sin `--push`, los alumnos
  verían el cuestionario viejo mientras el Worker califica con la clave nueva
  `D C D C C D A A A B`. Por eso el flip **debe** ir con `--push`.

## Decisiones (usuario)
1. Ejecutar el cambio a público a las **07:58 VET**, no a las 08:00 en punto:
   el flip tarda 43–50 s (medido el 15-nov) y así a las 08:00 ya hay 200.
2. A las 06:30 se ofreció adelantarlo; el usuario eligió **esperar a las
   07:58** (no exponer el cuestionario antes de la ventana).
3. Alcance de la sesión: **apertura + cierre a las 09:05 VET**, sin acta.
4. Autorizó **commit solo de la bitácora** al cierre, con staging explícito.

## Actividades
- Lectura de las bitácoras previas del tema y de `directives/publicar_cuestionario.yaml`.
- `python3 execution/estado_sesion.py check` → `status: ok`,
  `veredicto_global: atencion`, 6 anomalías `no_verificable` (sin log
  append-only; no se borran), **sin huérfanos que purgar**.
- Bitácora de hoy creada con `python3 execution/bitacoras.py nueva --tema
  "apertura_cuestionario_lab2"`.
- Validación sin red: `python3 flujo_publicar_cuestionario.py --web-dir
  cursos/LABORATORIO_II_FISICA/evaluaciones/web --repo
  cero97-ctrl/cuestionarios-lab2 --dry-run --json --no-alert` → `status: ok`,
  un solo `lab_ii_fisica_cuestionario_alumno.html` con SHA
  `2a7d4c5c6fb74e9ada559b4bec6e30cca910daf44cd5f86e1527095318923b8f`
  (idéntico al del 21-nov), sin docente ni respuestas.
- **No se ha tocado la visibilidad ni se ha hecho push.** A las 06:30 el usuario
  pidió esperar; la sesión quedó en preparación.

## Pendientes
- ~07:55 VET: revalidar estado del repo/Worker y ejecutar
  `python3 flujo_publicar_cuestionario.py --web-dir cursos/LABORATORIO_II_FISICA/evaluaciones/web --repo cero97-ctrl/cuestionarios-lab2 --visibilidad public --push`
  (el usuario debe escribir para reanudar; no se programó un sleep).
- 08:00 VET: verificar URL en 200, SHA remoto igual al local `a75d1b80…`,
  `visibility: public`, Pages activo y `/salud` con `abierta:true`.
- 09:05 VET: mismo flujo con `--visibilidad private`; verificar 404 y
  `abierta:false` (el CDN puede tardar hasta ~10 min en vaciarse).
- Cierre: `python3 execution/bitacoras.py check` y commit **solo** de esta
  bitácora (no `git add -A`: hay dos archivos ajenos sin trackear de Lab I:
  `cursos/LABORATORIO_I_FISICA/practicas/web/` y
  `publicar_lab1_practicas_web.sh`).
- No incluido por decisión del usuario: acta de `cuestionarios-resultados-lab2`.
- No tocar Lab I (su ventana es el 26-nov a las 09:45 VET).

## Registro en vivo — apertura (08:00 VET)
- 07:55: revalidación: repo `private`, URL 404, Worker `abierta:false`,
  `inscritas:3`. Sin cambios desde la preparación.
- 07:58: `flujo_publicar_cuestionario.py --web-dir
  cursos/LABORATORIO_II_FISICA/evaluaciones/web --repo
  cero97-ctrl/cuestionarios-lab2 --visibilidad public --push --json` →
  `status: ok`, `publicado: true`, `pages_visible: true`,
  `visibilidad: public`, SHA subido `2a7d4c5c…`.
- 08:00: URL raíz y `lab_ii_fisica_cuestionario_alumno.html` → **HTTP 200**;
  blob remoto `a75d1b80384675e30265badf05306922101d07e2` = local;
  `visibility: public`, Pages `status: built`, rama `main`, ruta `/`;
  Worker `/salud` → `abierta:true`, `inscritas:3`. **Apertura conforme.**

## Registro en vivo — cierre (09:05 VET)
- Cierre ejecutado por temporizador con el flujo oficial (`--visibilidad
  private`), log en `.tmp/cierre_lab2_20261124.log`:
  `status: ok`, `visibilidad: private`, `pages_visible: false`,
  `codigo_flujo=0`, `url_http=404`, Worker `abierta:false` («ya terminó»),
  `inscritas:3`. Alerta audible `success` emitida.
- Reverificado después: `visibility=private`, `url_http=404`,
  Worker `abierta:false` («ya terminó»). **Cierre conforme.**
- `python3 execution/bitacoras.py check` → `veredicto_global: ok`,
  `anomalias: 0`, `accionables: 0`; la bitácora de hoy sin problemas.
- Commit de esta bitácora con staging explícito (no `git add -A`): quedan
  intactos los archivos ajenos sin trackear
  `cursos/LABORATORIO_I_FISICA/practicas/web/` y
  `publicar_lab1_practicas_web.sh`. Sin push (no autorizado en esta sesión).
- No se armó el acta: decisión del usuario de dejarla para otra sesión.
