# 2026-11-08 — curso_ciberseguridad

## Tema
curso_ciberseguridad

## Contexto
- Continuación de la sesión del 2026-11-07 (semana 1 con ejemplos por grupo ya
  entregados en el commit `47b77c8`).
- Quedaba abierto del backlog: "replicar el patrón `--semana N` para las semanas
  2–10 y escribir sus ejemplos". Se aclaró al usuario que son dos tareas
  distintas: emitir el documento semanal (mecánico) y redactar los `ejemplos:`
  por grupo (autoría de contenido, semana a semana).
- Verificación previa: las semanas 2–10 ya tenían datos completos para emitir su
  documento (objetivo, contenidos, herramientas, práctica con 5 pasos y criterios
  que suman 10,0), pero **ninguna declaraba glosario**.

## Decisiones (usuario)
1. Alcance de esta sesión: **solo los documentos de las semanas 2–10**; los
   ejemplos por grupo se redactan semana a semana cuando toque.
2. **Sí añadir glosario por semana**, manteniendo el patrón de la semana 1.
3. Plan y lista de términos aprobados por el usuario antes de ejecutar.
4. Las infografías **no se versionan** en git: se quedan en local (MEGA las
   sincroniza) porque pesan ~28 MB y no aportan al clon. Misma pauta que
   `docs/REFERENCIA/` y `evaluaciones/resultados/`: se ignora todo salvo el README.

## Actividades
- `cursos/CYBERSEGURIDAD/curso.yaml`: glosario global de 18 → **77 términos**
  (+59 definiciones) y lista `glosario:` declarada en cada semana:
  - 02 criptografía: 8 · 03 legal: 7 · 04 OSINT: 8 · 05 web: 6 · 06 hardening: 8
  - 07 DevSec: 6 · 08 forense: 7 · 09 IR/malware: 7 · 10 final: 2
- Validación previa con `validar_semana()` y `_glosario()`: las 9 semanas sin
  problemas y cada término resuelve contra el glosario global (sin orfanatos).
- Emisión con `flujo_instrucciones_semana.py --curso ... --semana N` para N=2..10:
  9 documentos nuevos `docs/semana_02..10.{tex,pdf}`, 5 páginas cada uno
  (4 de contenido + 1 de glosario).
- Verificación por documento: 0 líneas `!` en el log, 0 `Overfull \hbox`,
  `verificar_pdf.py` → `ok`, 0 solapes, 5 páginas.
- Determinismo: segunda corrida de las 9 semanas y `diff` de sha256 → idénticos.
- Coste: 0 créditos OpenRouter (no intervino ningún LLM).
- El usuario revisó visualmente los 9 PDF: "todo perfecto".
- El usuario añadió `docs/INFOGRAFIAS/SEM_1/` con 4 infografías PNG (rol rojo,
  rol azul, rol púrpura y flujo legal y reporte), en formato divulgativo para sus
  estudiantes.
- Bitácora creada con `bitacoras.py nueva --tema curso_ciberseguridad`.
- `.gitignore`: nueva regla `cursos/*/docs/INFOGRAFIAS/**` con excepción del
  `README.md`; `git rm --cached` de los 4 PNG (siguen en disco).
- `cursos/CYBERSEGURIDAD/docs/INFOGRAFIAS/README.md`: documenta la convención
  (una carpeta `SEM_NN` por semana, nombres en español, nunca `git add -f`).
- **Reescritura de historia** (autorizada por el usuario) para sacar los PNG del
  historial: `git filter-repo --invert-paths --path-glob
  'cursos/CYBERSEGURIDAD/docs/INFOGRAFIAS/SEM_1/*.png'` sobre 321 commits (2,13 s
  de reescritura, 141 s de repack). Resultado: 0 PNG en toda la historia,
  `.git` 848 MB → 779 MB. Los 4 PNG siguen en disco (ignorados).
- Respaldo previo en `/tmp`: `electronica_pre_rewrite.bundle` (805 MB, todas las
  refs) y copia de los 4 PNG en `/tmp/infografias_sem1_backup/`.
- `filter-repo` elimina el remoto `origin`: se volvió a añadir y se empujó con
  `git push --force origin master` (`c20a92b` → `a6a579a`), upstream restaurado.
- Consecuencia: los commits de esta sesión cambiaron de SHA —
  `d6493c5` → `11b7288`, `c51c53e` → `34730e5`, `c20a92b` → `a6a579a`. Todo lo
  anterior a `2a87e31` conserva su SHA.

## Pendientes
- `master` remoto en `a6a579a`; árbol limpio y sin PNG en la historia.
- GitHub puede conservar objetos inalcanzables en caché un tiempo: el tamaño del
  repositorio en la web puede tardar en reflejar los ~28 MB liberados.
- Redactar los `ejemplos:` por grupo de las semanas 2–10 (36 bloques), semana a
  semana; la semana 2 (criptografía) es la siguiente natural.
- `nota_minima: 5` confirmada por el usuario el 2026-11-08 y ya consta en el
  descriptor; nada que cambiar.
- Revisar visualmente los PDF nuevos (no se abrieron uno a uno en esta sesión,
  solo validación determinista y extracción de texto de la página de glosario).
