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

### Segunda parte — ejemplos por grupo y cierre individual (37 PDF)

- Aclarado al usuario que los 32 ejemplos de las semanas 2–9 **no** son el mismo
  trabajo repetido: mismo molde, contenido distinto por semana y por rol; la
  semana 10 no se reparte por roles (fase de cierre individual).
- Semanas 2–9: 4 ejemplos cada una (`grupo_1..4_NN`), redactados e insertados con
  `.tmp/insertar_ejemplos.py <semana> <fragmento>` (inserta tras la línea
  `evaluacion:` del bloque `- numero: N`).
  - 02 criptografía · 03 marco legal · 04 OSINT/escáner · 05 OWASP web ·
    06 hardening/Suricata · 07 DevSec/SBOM · 08 forense (adquisición, timeline,
    IoC) · 09 respuesta a incidentes y triaje estático de malware.
  - La rotación de roles se respetó leyendo `roles_de_la_semana`: 4–5 G1 Azul,
    G2 Púrpura, G3 Legal, G4 Rojo; 6–7 G1 Púrpura, G2 Legal, G3 Rojo, G4 Azul;
    8–9 G1 Legal, G2 Rojo, G3 Azul, G4 Púrpura.
- **Semana 10 (cierre)**: nueva capacidad `--cierre` en las 3 capas.
  - Capa 3 `execution/generar_instrucciones_semana.py`: `es_cierre = grupo == 0`,
    cabecera «Trabajo individual (cierre del curso)», job `cierre_{NN}`,
    validación con `validar_ejemplo(datos, semana, 0)`.
  - Capa 2 `flujo_instrucciones_semana.py`: `--cierre`, mutuamente excluyente con
    `--grupo`.
  - Capa 1 `directives/instrucciones_semana_curso.yaml`: **v1.2**, input
    `cierre`, salida `cierre_<NN>.{tex,pdf}`, 12 casos límite.
  - Entrada `ejemplos: [{grupo: 0, ...}]` con el recorrido completo de 4 h
    (aceptar alcance, reconocer, explotar controlado, preservar con hash,
    informe técnico + resumen ejecutivo + defensa oral).
- **Bug encontrado y corregido**: en la rama de cierre las secciones «Tu rol en
  la práctica» y «Qué aporta este rol» quedaban con `itemize` vacío →
  `! LaTeX Error: Something's wrong--perhaps a missing \item.` El flujo lo
  detectó y devolvió `status: error` con 1 línea `!` en el log (no lo dio por
  bueno aunque el PDF existiera). La rama `es_cierre` ahora emite una sección
  «Trabajo individual» con texto fijo. Verificado: el `.tex` de un grupo es
  **idéntico** antes y después del refactor (`diff` sin cambios) → el cambio no
  altera la salida de las 36 piezas por grupo.
- **Trampa de verificación registrada**: `grep -c 'Overfull \\\\hbox'` con ese
  escapado busca *dos* barras invertidas y devuelve 0 siempre → dio falsos
  «0 overfull» en las semanas 7–9. La fuente de verdad es el campo `overfull` de
  `execution/verificar_pdf.py --log ...`.
- 2 overfull reales en `grupo_4_08` (4,61 pt) y `grupo_4_09` (2,03 pt): no era
  ancho total de tabla sino una **celda** con palabra más larga que su columna
  («Comportamiento», «Discriminante»); al estrechar más la columna el overfull
  crecía. Corregido repartiendo anchos: `[3.0, 2.6, 2.4, 2.1, 2.7]` y
  `[2.4, 3.2, 2.1, 2.9, 2.4]`.
- Verificación final: **37/37 PDF limpios** (`status ok`, 0 `!`, 0 overfull,
  0 solapes; 3–5 páginas). `execution/test_generar_material_curso.py`: 72
  aserciones, 0 fallos.
- `AGENTS.md`: comando de `flujo_instrucciones_semana.py` actualizado con
  `[--grupo N | --cierre]` y `cierre_NN.{tex,pdf}`; se corrigió el conteo de
  aserciones del test del descriptor (52 → 72, estaba desfasado).
- Coste: 0 créditos OpenRouter (todo determinista, sin LLM).

### Tercera parte — commit y documentación

- Commit + push autorizados por el usuario:
  `63ea0b8 feat(curso): 33 ejemplos por grupo (semanas 2-10) y --cierre en 3 capas`
  (`1186c4d..63ea0b8`, 72 entradas: 6 modificados + 66 nuevos `.tex`/`.pdf`).
- **Trampa de `update_repo.sh`**: el script hace `pull --rebase` **antes** del
  commit, así que con cambios sin marcar falla
  (`no se puede pull con rebase: Tienes cambios sin marcar`). Se verificó
  `git fetch` + `rev-list --left-right --count origin/master...HEAD` = `0 0` y se
  repitió con `--no-pull --push`. Queda documentado en `AGENTS.md` → Git quirks.
- `AGENTS.md`: además de `--cierre`, se añadió el quirk anterior.
- `.agent/latex.md`: dos trampas nuevas documentadas — #22 el `Overfull \hbox`
  de una **celda** (estrechar la columna lo empeora) y el `grep` mal escapado que
  da 0 siempre (usar `grep -cF` o el campo `overfull` de `verificar_pdf.py`); #23
  el `itemize` vacío en `nonstopmode`, que genera PDF con `! LaTeX Error:
  Something's wrong--perhaps a missing \item` y solo se ve en el `.log`.

### Cuarta parte — exámenes fuera del repositorio público

- El usuario detectó que `cursos/CYBERSEGURIDAD/evaluaciones/` era público. Al
  revisar, el problema era mayor: **los tres cursos** tenían publicados
  `control_fase_1..3` y `evaluacion_final` (`.tex` + `.pdf`), 20 ficheros en git.
- Decisiones del usuario: ocultar los **tres cursos**, **reescribir el historial**
  y dejar la **rúbrica pública** (es criterio, no prueba).
- `.gitignore`: nuevas reglas `cursos/*/evaluaciones/*.tex` y `*.pdf` (glob, así
  cubre controles futuros); `git rm -r --cached` de los 20 ficheros. Los archivos
  siguen en disco (MEGA los sincroniza) y se regeneran con `flujo_disenar_curso.py`.
- Respaldo previo: `/tmp/electronica_pre_examenes.bundle` (785 MB, todas las refs).
- Reescritura: `git filter-repo --invert-paths --path-glob
  'cursos/*/evaluaciones/*.pdf' --path-glob 'cursos/*/evaluaciones/*.tex'`
  (325 commits parseados, 1,16 s + 21,4 s de repack). Verificación: **0** commits
  y **0** blobs con `control_fase|evaluacion_final` en toda la historia; `.git`
  787 MB → 784 MB.
- `filter-repo` elimina `origin`: se volvió a añadir y se empujó con
  `push --force` (`519109e` → `54e03b1`); upstream restaurado.
- SHA nuevos: `1186c4d` → `693ca05`, `63ea0b8` → `89d5815`, `519109e` →
  `78521e9`, y el commit nuevo `54e03b1`. Todo lo anterior a `2ed963bd`
  (primer commit con exámenes) conserva su SHA.
- Remoto verificado con `git ls-tree -r origin/master cursos/`: 0 ficheros de
  examen; quedan `rubrica_practica.yaml` y `resultados/README.md`.

- Verificación de que el ocultamiento no pierde nada:
  `flujo_disenar_curso.py --salida .tmp/check_gen --solo controles,final
  --sin-compilar` sigue escribiendo `control_fase_1..3.tex` y
  `evaluacion_final.tex`, y los cuatro son **idénticos byte a byte** a los
  locales ya ignorados (`cmp`); el directorio temporal se borró después.
  `git check-ignore -v` confirma que las dos reglas nuevas son las que
  alcanzan los exámenes de los tres cursos y que `rubrica_practica.yaml` y
  `resultados/README.md` siguen públicos.

## Pendientes
- `master` remoto en `d6ec3734`; árbol limpio y sin exámenes en la historia.
  Commits de esta cuarta parte: `54e03b1` (`.gitignore` + `git rm --cached` +
  reescritura) y `d6ec3734` (`AGENTS.md` + bitácora).
- GitHub puede conservar objetos inalcanzables en caché un tiempo: los PDF
  pueden seguir descargables por SHA directo hasta que GitHub recoja la basura.
  Quien ya hubiera clonado el repo conserva los exámenes.
- `master` remoto en `63ea0b8`; árbol limpio y sin PNG en la historia.
- GitHub puede conservar objetos inalcanzables en caché un tiempo: el tamaño del
  repositorio en la web puede tardar en reflejar los ~28 MB liberados.
- Revisar visualmente los 37 PDF de ejemplos (en esta sesión solo se validaron
  por log/texto, no uno a uno).
- `nota_minima: 5` confirmada por el usuario el 2026-11-08 y ya consta en el
  descriptor; nada que cambiar.
- Decisión aparcada: no contratar OpenCode Go ($10) y **no** cambiar
  `MODELO_FALLBACK` (sigue `openrouter/qwen/qwen3.8-max-0902`) — orden expresa
  del usuario («dejalo tal cual está, no modifiques»).
