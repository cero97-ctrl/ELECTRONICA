# 2026-10-05 — corrupciones_prosa_cjk

## Tema
corrupciones_prosa_cjk

## Contexto
Sesión de arranque: el usuario pidió recuperar el contexto (bitácoras previas, estado de
sesión, higiene del repo) antes de traer un tema nuevo. Ningún trabajo de fondo; solo
lectura más una corrección puntual.

Lo que salió de esa revisión:
- **Estado de sesión** (`python3 execution/estado_sesion.py check`): `veredicto_global: ok`,
  **0 huérfanos confirmados** → no hay nada que purgar. Los 8 `run_state` de flows legacy
  salen como `no_verificable`, no `fallo`: son de flujos anteriores a `sesion_log.py`.
- **Auditoría de higiene** (`python3 flujo_auditar_repo.py`, pasada completa 194 s):
  `con_fallos` (exit 1) con **un único fallo**, la dimensión `texto`: 7 corrupciones de
  prosa. Eran **3 palabras**, no 7, y todas de la misma familia: caracteres CJK intrusos
  pegados dentro de texto español.

  | Fichero | Corrupto | Legible |
  |---|---|---|
  | `Sessions/2026-10-02_nota_determinista_escala_rubrica.md:98` | `No se«CJK»generaliza` | No se generaliza |
  | `directives/inspeccionar_entrega.yaml:27` | `la «CJK» es si` | la pregunta es si |
  | `execution/test_evaluar_rubrica.py:480` | `debe«CJK» la aritmética` | debe limitar la aritmética |

  (Los caracteres intrusos van aquí como `«CJK»` y no copiados literalmente: esta bitácora
  pasa también por `verificar_texto.py`, y reproducir los tokens devolvería el repo a
  verde falso. Los originales se leen en el commit `fix(texto)`.)

  Origen: sesiones del 2026-10-02/10-03. Son tres ficheros de un mismo lote de trabajo, lo
  que apunta a una única tarea de redacción asistida que coló caracteres CJK, no a tres
  fallos independientes. El detector no distingue «una corrupción» de «varias» en el
  recuento: cuenta **caracteres**, así que 7 hallazgos ≠ 7 problemas.
- Avisos (no bloquean): disco al **85.6 %** (33.55 GB libres), 252 MB trackeados con 8
  ficheros ≥5 MB, 3 de 177 pares `.tex/.pdf` con el PDF más viejo que el fuente, y 11
  capacidades declaradas sin implementar en 9 directivas `Status: planificado`.

## Decisiones (usuario)
1. **Corregir las corrupciones sin más análisis**: son inequívocas (cada palabra tiene una
   sola lectura en español) y el usuario pidió expresamente el arreglo en vez de una
   investigación sobre el origen.
2. **No tocar el disco** (85.6 %): quedó a la vista, sin accionarse en esta sesión.
3. Se commitea también `docs/AGENTE_IA/resumen-xiaomi-deepseek.md`, que estaba untracked
   desde antes de esta sesión y es un resumen de estudio (HighSpars 2 / KV cache de
   Xiaomi), sin relación con las correcciones. Se commiteó **en su propio commit**, no
   mezclado con el fix.
4. **El estudio de detección de errores conceptuales sigue en la nevera.** Confirmado
   expresamente el 2026-10-05: no se retoma hasta que el profesor haga **una ronda de
   corrección en papel**. La condición de desbloqueo es **una acción suya, no del
   orquestador**: no hay forma de que el agente la dispare, así que «esperar a tenerla»
   significa esperar a que el usuario la complete. No es un pendiente que el agente pueda
   recordar por cuenta propia.

## Actividades
- Lectura de las 3 últimas bitácoras y del estado de git (`master`, `4b58eee`).
- `estado_sesion.py check` y `flujo_auditar_repo.py` (ambos solo lectura).
- Corrección de las 3 palabras.
- Verificación: `execution/verificar_texto.py` → **0 hallazgos** (exit 0);
  `execution/test_evaluar_rubrica.py` → **182 aserciones, 0 fallos**; el YAML de
  `directives/inspeccionar_entrega.yaml` sigue parseando y con la descripción íntegra.

## Pendientes
- **Disco al 85.6 %**: 177.5 MB recuperables solo dentro de la whitelist del proyecto. El
  resto del disco no lo mide este flujo (`/var/lib/docker`, `/var/lib/waydroid`,
  `/var/lib/containerd` quedan fuera a propósito). No se ha purgeado nada.
- **8 ficheros ≥5 MB trackeados**: `git rm --cached` ahorra espacio futuro pero no reduce
  el histórico; reducirlo exige reescritura, que hay que decidir con cuidado.
- **3 PDF desfasados**: recompilar antes de entregar.
- **Estudio de detección de errores conceptuales** (decisión del profesor el 2026-10-03,
  **reconfirmada el 2026-10-05**): aparcado hasta que el profesor haga **una ronda de
  corrección en papel**. El prompt de `TAREA_POR_TIPO["examen"]` **no se toca** hasta
  tener verdad etiquetada.
  Procedimiento de reanudación (del detalhe en la bitácora del 2026-10-03, sección
  «Cómo se retoma»): reunir muestra → evaluar por lote con `flujo_evaluar_examen.py
  --tipo examen` **inspeccionando antes cada PDF** con `inspeccionar_entrega.py` → escribir
  la verdad del profesor sobre el papel ítem a ítem en un archivo sin nada del modelo →
  solo entonces contrastar. No reusar `resultados_modelo.md`.
- **El motor de opencode de esta sesión no acepta imágenes ni PDF**: cualquier revisión
  visual de informes tiene que hacerla el LLM del script o el usuario.