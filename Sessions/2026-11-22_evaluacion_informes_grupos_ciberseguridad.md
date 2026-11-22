# 2026-11-22 — evaluacion_informes_grupos_ciberseguridad

## Tema
Evaluación de los informes de semana 01 de los 4 grupos de Ciberseguridad, previa al commit del cierre de la Evaluación 1.

## Contexto
- El acta del examen (16-nov) ya estaba definitiva: 11 notas, `a_revisar: 0`; el promedio vive solo en el acta local. El usuario pidió evaluar los informes **antes** de hacer commit.
- La recuperación del 17-nov se verificó inexistente: no aplica, no se fusiona acta.
- Los informes viven en 4 repositorios privados (`cero97-ctrl` como colaborador). Se fijó el SHA de commit de cada uno para que la evaluación sea reproducible.
- G2 sube el informe como `Informe.md` (mayúscula); G4 no trae `hashes.sha256` ni `scripts/`; G3 incluía cédulas en el texto.

## Decisiones (usuario)
1. **No evaluar la fecha de entrega en esta corrida.** Texto literal: «esta vez no tomes en cuenta la fecha de entrega. Para las siguientes semanas si.» → `evaluar_corte: false` queda como excepción documentada **solo** para semana 01; el default del descriptor sigue siendo `true`.
2. **Backend Gemini free**, sin consumo de `OPENROUTER_API_KEY`.
3. **Acta privada separada** para los informes, sin tocar el acta de 11 filas del examen.
4. **Sin commit** hasta autorización explícita del usuario tras revisar resultados.
5. Alerta de determinismo ya comunicada y aceptada: el modelo lo fija `execution/enrutador.py`, no el razonamiento del chat. Se respetó `--modelo-explicito google/gemini-2.5-flash` → SDK directo `gemini-2.5-flash`.
6. No se pidieron los links de los repos: ya estaban localizados y fijados por SHA en el descriptor privado.

## Actividades
- Capa 1: `directives/evaluar_informes_grupos.yaml` (SOP con 6 pasos, 9 casos límite, `retry_budget: 3`, excepción de plazo y recuperación sin LLM).
- Capa 2: `flujo_evaluar_informes_grupos.py` (run_state + traza, exige cobertura 4/4, compila aislado en `.tmp/latex_build/`, verifica con `verificar_pdf.py`, copia al acta privada).
- Capa 3: `execution/evaluar_informes_grupos.py` (descarga por SHA con `gh`, `resolver_informe()` case-insensitive, rutas citadas, hashes, secretos, anonimización, reutiliza `cargar_rubrica()` y `calcular_nota()`, modo `--desde-json`).
- Pruebas puras: `execution/test_evaluar_informes_grupos.py` → **22/22 OK**, sin red ni API.
- Corrección de entorno: `evaluar_examen.py` carga `.env` y `gh` prefería ese `GITHUB_TOKEN` (401) sobre el keyring; `_gh()` retira esas variables del subproceso sin imprimirlas.
- Corrección de fechas: GitHub devuelve `...Z`, que `datetime.fromisoformat` no aceptaba en esta Python; se normaliza a `+00:00`.
- Corrección de rutas Windows (`\` y `./`) y resolución por sufijo único para las capturas de G3.
- Chequeos deterministas (`--check`): 4/4 informes, **43/43 hashes verificados**, 0 fallidos, 0 sin archivo, 0 secretos. G4: 0 hashes (sin evidencia).
- Evaluación con Gemini free: 4 llamadas, 4 informes calificados con la rúbrica. Las notas y el promedio se guardan solo en `resultados/` y `.tmp/` (repo público); no se reproducen en esta bitácora. El modelo NO emitió nota total; `calcular_nota()` la calculó con los 5 pesos de la rúbrica.
- Recuperación del acta: las copias en `resultados/` (gitignored) desaparecieron tras el primer flujo; se añadió `--desde-json` para regenerar desde el JSON **sin repetir Gemini**, preservando las notas exactas. Se recompiló y reverificó.
- PDF final: `{"status":"ok","paginas":1,"errores":[],"overfull":[],"solapes":[],"solapes_total":0}`.
- Integridad del acta del examen intacta: `.tex` `b4788744…`, `.pdf` `0e4fcc77…`.
- Hashes del acta de informes: `.tex` `3e1fda6b…`, `.pdf` `c7180811…`.

## Privacidad y cierre del repositorio (autorizado por el usuario)
- El usuario decidió que **solo él** vea los resultados y que, si lo considera oportuno, los publique por WhatsApp. El repo es público, así que `resultados/**` sigue ignorado y no se subió ningún PDF, CSV ni JSON de notas.
- Antes del commit se sanitizaron las dos bitácoras nuevas (nombres, cédulas y cifras → descripciones genéricas). El inventario mostró además PII real en `Sessions/2026-11-16_…md` y en fixtures de `execution/*.py` (incluido `test_fusionar_actas.py`, preexistente): se sustituyeron por identificadores ficticios (`V-9xxxxxxx`, `ALUMNO-N`, `AUSENTE-N`) con un mapping determinista de 52 reglas. Se revirtieron 5 `.tex` de INT_ELECTRONICA donde el apellido del profesor coincidía con un apellido de alumno.
- Commit `f6def6a` (16 archivos) y reescritura de historia con `git filter-repo --replace-text` sobre los 360 commits. La versión instalada falló al grabar metadatos (`AssertionError`) **después** de escribir la historia nueva; se verificó con `git fsck`, escaneo de los 360 commits (0 con PII) y tests, y se eliminó el ref `refs/remotes/old/master`. Se purgaron objetos inalcanzables con `git gc --prune=now` y se borró el backup temporal externo.
- `git push --force origin master`: el remoto quedó alineado con el local. Verificación por `raw.githubusercontent.com` (cache-buster): las tres bitácoras del 16 y 22-nov no contienen identificadores ni notas en el remoto. `git ls-tree` confirma que solo viajan los dos `resultados/README.md`, nunca resultados.
- Tests tras la reescritura: calificaciones_inasistencia 31/31 · acta_semana 76/76 · descargar_resultados sin fallos · evaluar_informes OK · fusionar_actas 23/23 · `bitacoras.py check` → `veredicto_global: ok`. Las cuatro actas locales conservan sus hashes.

## Pendientes
- Semanas posteriores: aplicar `evaluar_corte: true` por defecto (la fecha sí cuenta).
- Publicar notas solo de forma manual desde los PDF locales, si el usuario lo decide.
