# 2026-09-28 — purga_disco_tier_recargable

## Tema
purga_disco_tier_recargable

## Contexto
El P1 de la sesion del 2026-09-27 ("disco al 91.3 %, 0 MB recuperables, requiere
decidir que se sacrifica") estaba mal redactado. Al medir antes de actuar aparecio
que "0 MB" era el resultado de `--tier seguro` (el default), no una falta de
recursos: el catalogo completo declara 18,2 GB y el flujo se niega a tocarlos
porque el nivel lo elige el operador, nunca el script. No habia nada que
sacrificar; habia un tier sin elegir.

## Decisiones (usuario)
1. **"Tier recargable, sin recortes"**: purgar `recargable` completo. No se
   autorizan `sudo`, ni el tier `pesado` (rompe el RAG), ni reescritura de
   historico de git.
2. Se acepta que `google-chrome` (1,34 GB) quede fuera: se uso hoy y la guarda de
   antigüedad lo conserva. Es el comportamiento correcto, no un fallo.
3. **"Los envs del Grupo A no los estoy usando; elimínalos pero revisa que no
   rompa nada de lo que sí usamos"**: los 14 envs no críticos son residuo de los
   primeros estudios de aislamiento con conda.
4. **Alcance por regla, no por lista**: cuando las dos listas que presenté no
   cuadraron (decían 6,2 GB y sumaban 5,26; me había dejado 3 envs fuera al
   reescribirlas), el usuario eligió "los 12, por la regla" en vez de la lectura
   literal. La regla gana al inventario escrito a mano: es la que se sostiene
   cuando los números ya no cuadran.

## Actividades

### Medicion previa (sin borrar nada)
- `df -h /`: 202 GB usados de 234 GB, **91 %**, 21 GB libres.
- `flujo_disco.py --check` y `--dry-run --tier todos`: el `dry-run` de `todos`
  decia literalmente `recuperable todos: 0 B` mientras `decision.razon` citaba
  19,5 GB. Es el mismo bug de impresion que ya se habia corregido para
  `seguro` (commit `3959955`): `flujo_disco.py:141` imprime
  `resumen.get(args.tier, {}).get('humano', '0 B')` y **"todos" no es una clave de
  `reclaimable_por_tier`** (que solo tiene `seguro`/`recargable`/`pesado`). El
  default cae en `'0 B'` y miente. La decision, que usa
  `reclaimable_total_bytes`, si era correcta: son dos ramas distintas del mismo
  dato.
- Peso real por target (leido de `.tmp/disco_medicion.json`, contrasted con `du`):
  `conda-pkgs` 9,68 GB · `arduino-packages` 5,92 GB (219 dias sin uso) ·
  `google-chrome` 1,34 GB · `puppeteer` 1,34 GB · `opera` 1,32 GB ·
  `huggingface` 0,57 GB · `playwright-go` 0,27 GB · `chroma-model` 0,18 GB ·
  `trash` 0,15 GB · `mozilla` 0,12 GB · `cloud-code` 0,11 GB.
- Descartado como recuperable real: `conda-pkgs`. No queda **ni un `.tar.bz2`**
  (0 B en 9,68 GB). Lo que ocupa son paquetes ya extraidos y **hardlinkeados**
  (193.418 ficheros con `nlink > 1`) contra los envs: `du` de `pkgs` en solitario
  da 9,68 GB, pero junto a `envs` solo aporta 8,12 GB, y 193.418 ficheros
  compartidos no son espacio recuperable. `conda clean --all` solo puede tocar
  `pkgs/cache` (1,13 GB) y paquetes sin usar.

### Ejecucion
1. `execution/test_barrera_disco.py` -> **89 aserciones, 0 fallos**. La barrera
   que decide que es borrable estaba verde antes de borrar nada.
2. `--tier recargable --dry-run` -> 8 evaluados, 7 a borrar, 1 omitido
   (`google-chrome`, `conservado_reciente`). Coincidio con lo previsto.
3. `--tier recargable --yes` -> **10,06 GB liberados en 70,2 s**. 7 targets.
4. Verificacion post-purga:
   - `elect_env` y `IA` intactos: huella de `lib/` identica antes y despues
     (218 / 615 / 1747 entradas), los 16 envs siguen listados, y los tres
     criticos importan: `langchain`, `chromadb`, `sentence_transformers`,
     `requests`, `numpy`, `psutil`, `yaml` en `elect_env`; **TF 2.19.1** en `IA`.
   - Los 6 directorios de navegador/herramienta quedaron vacios (4 KB) = borrados.
   - `huggingface` (546 MB) y `chroma` (167 MB) intactos: el RAG no se tocó.
   - `google-chrome` 1,3 GB intacto, como se decidió.
5. `df -h /`: 192 GB usados, **87 %**, 31 GB libres. De 91,4 % a 87,1 %.

### Verificacion independiente
- `flujo_auditar_repo.py` completa (13 dimensiones, 50,9 s): veredicto
  **`con_avisos`, exit 0, 0 dimensiones con fallo**. Antes de esta purga el disco
  figuraba como `fallo` y era lo unico que lo era.
- `estado_sesion.py clean` -> purgado el `run_state.json` huerfano que dejaron
  las corridas `--check`/`--dry-run` de esta misma sesion. Los logs append-only
  intactos (166 logs, cadena de hashes verificada, 410 eventos).

## La cifra prometida y la cifra real
El flujo anuncio **17,5 GB** recuperables en `recargable` y entrego **10,06 GB**.
La diferencia (7,4 GB) es casi toda `conda-pkgs` (9,68 GB declarados, ~2,2 GB
reales de `pkgs/cache`). Se|reporta asi en vez de presentar la cifra bonita:
declarar 17,5 GB habria hecho que la proxima auditoria pareciera una perdida de
7 GB cuando en realidad el piso de lo recuperable sin romper nada es ese.

## Hallazgo lateral: `flujo_auditar_repo.py` deja andamio por construccion
`estado_sesion.py check` marco `run_state.json` como `huerfano` justo despues de
auditar, con la corrida declarada terminada. Causa: `flujo_auditar_repo.py:521`
escribe `STATE_FILE` y **nunca lo retira**, mientras `flujo_auditar_sistema.py`
si lo hace (`ruta_estado.unlink()` al cerrar, con `try/except OSError` para que
un andamio indomable no tumbe el informe). Es el mismo bug que se corrigio ayer
en el flujo de sistema, sin portar el arreglo al de repo. Y hay una segunda
pieza: **todos los `flujo_*` comparten `TMP/run_state.json`**, asi que la vista
de la auditoria se empareja con el log de otro flujo, o con ninguno. No es un
detalle de forma: es exactamente el bug del "quinto" de ayer
(`run_state_sistema.json` buscando un log con otro nombre), con el nombre bien
escrito y el problema peor, porque ahora N flujos compiten por el mismo fichero.

## Limpieza de entornos conda (segunda parte de la sesion)

### El criterio: `.pyc` y no `conda-meta/history`
La pregunta era quais envs no se estan usando. **La senal fiable es el `.pyc`**, porque
lo genera la *ejecucion* del interprete. Descartadas como prueba:
- `conda-meta/history` solo fecha la ultima operacion de paquetes. Un env usado a
  diario que no instala nada no lo toca, asi que **miente**: `IA` tiene el suyo en
  2025-10-25 y `fisica_env` en 2026-06-24 sin que eso signifique nada sobre su uso.
- mtime del directorio del env: tampoco cambia al ejecutar.
- `.bash_history`: 846 lineas, 12,9 KB, **sin timestamps** y truncable. Solo apoyo.
  Sirvio para confirmar que `elect_env` (24 menciones), `agro_env` (3), `cyber_env`
  (4) y `bio_env` (1) existen en la practica, no para probar un negativo.

Regla final: **cero `.pyc` en 90 dias Y ningun workspace vivo que lo declare por
nombre**. Se buscaron las referencias en todo `~/MEGA/VS_CODE_WORKSPACE`, no solo en
este repo, porque un `setup.sh` de otro proyecto con `ENV_NAME="pcb_env"` es una
dependencia real.

### 16 envs -> 4 conservados, 12 eliminados
- `elect_env` 5,7 GB: activo, 1460 ficheros en 30 dias, lo fija
  `.opencode/plugins/conda-env.js`.
- `IA` 2,3 GB: frio, pero unico TensorFlow funcional (2,19,1 verificado). Politica.
- `agro_env` 0,79 GB: **en uso**, 67 `.pyc` en 90 dias.
- `bio_env` 0,47 GB: frio, pero `BIOANALISIS` tiene commit del 2026-08-12.

Eliminados: `pcb_env` 1,00 · `agent_env` 0,78 · `cnc_bot_env` 0,78 · `hidro_env` 0,61
· `cyber_env` 0,59 · `agente_naviera` 0,44 · `pcb_env_312` 0,30 · `youtube_uploader`
0,28 · `d2c_env` 0,23 · `meerk_env` 0,19 · `fisica_env` 0,19 · `litografia_env` 0,18.

### Verificacion antes de borrar (5 vias, todas limpias)
Procesos vivos, ficheros de arranque (`~/.bashrc`, `~/.profile`, `~/.zshrc`),
servicios systemd, scripts/flujos/MCP del repo, y rutas de opencode: **ninguno**
apunta a los 12. `flujo_telegram.py` corre con `.venv`, no con conda. Guarda explicita
en el bucle de borrado: la lista no puede intersectar con los 4 conservados.

### Irreversibilidad corregida: los recipes NO iban a `.tmp`
Exportados primero a `.tmp/recipes_envs/*.yml` y eso habria sido un falso "es
reversible": **`.tmp/` esta gitignored y se purga**, asi que los recipes se perdian
igual al perder los envs. Movidos a `docs/ENTORNOS_CONDA/recetas/` (13 `.yml`, con su
seccion `pip:` completa) + `README.md` con el criterio, la tabla de referencias
colgadas y los pasos de recreacion. Committeados antes de borrar.

### 4 GB, no 5,6: el hardlink de conda
Lo liberado fueron **4,0 GB** (87 % → 85 %, 31 → 35 GB libres), no los 5,6 GB de la
suma de `du`. Motivo: conda **hardlinkea** cada env contra `anaconda3/pkgs` (7,5 GB),
asi que borrar un env solo libera los bloques que no comparte con la cache. Es la
misma causa raiz del P2 de `conda-pkgs` que ya estaba anotado, vista desde el otro
lado: la overestimate de `flujo_disco.py` y la infrapredict de esta suma son el mismo
fenomeno medido en dos direcciones.

### Sin regresion
`flujo_auditar_repo.py --rapido`: `con_avisos`, exit 0, **0 dimensiones con fallo**,
`logs` con la cadena de hashes intacta en 169 logs. `elect_env` e `IA` con mtime
anterior a hoy (2026-06-20 / 2025-10-25): intactos. `pandas` no esta en `elect_env`
pero ningun script del repo lo importa, y su ausencia es preexistente.

## `conda clean --packages`: los 44 huerfanos

Autorizado por el usuario con la condicion explicita "si lo que hacen es ocupar espacio
entonces hay que eliminarlos". La condicion se cumple y se verifico antes de ejecutar:
`--tarballs` y `--index-cache` no tienen nada, asi que los 536,7 MB de los 44 paquetes
eran toda la oportunidad disponible. Tras la limpieza, `conda clean --packages --dry-run`
responde "There are no unused package(s) to remove".

### Sin dano: huella antes/despues identica
`elect_env` 20830 `.pyc` · `agro_env` 8617 · `bio_env` 4323 · `IA` 9993, y los mismos
CPython (3.10.20 / 3.10.19 / 3.11.15 / 3.11.14 / base 3.13.5) antes y despues.
`elect_env` sigue importando `numpy requests sklearn serial`; `IA` sigue con
`tensorflow 2.19.1`. Es la confirmacion empirica de que borrar la cache no toca los
envs: sus ficheros estan hardlinkeados, no copiados.

### El espacio real recuperado no se puede demostrar
`pkgs` bajo de 7,5 G a 6,9 G segun la contabilidad de conda, **pero `df` no se movio**:
quedo en 200,13 GB usados / 37,45 GB libres. Y no se puede afirmar que se recuperaran
los 536,7 MB, por dos razones honestas:

1. **No guarde el `df` en bytes antes de ejecutar.** Con la eliminacion de los 12 envs
   si lo hice; aqui me conforme con la salida de 1 GB de `df -h`, que no tiene
   resolucion para 536 MB. Inconsistencia mia de rigor entre dos operaciones
   consecutivas: la segunda merecia el mismo cuidado que la primera.
2. **La cifra de conda no son bloques libres.** Medido sobre la cache restante:
   **85,6 %** de los ficheros de `pkgs` tienen `nlink > 1`, o sea un hardlink desde
   algun env; solo el 14,4 % tiene bloques exclusivos. `conda clean --packages` mide
   tamano de directorio, que es la misma sobreestimacion del P2 de `conda-pkgs` que ya
   estaba anotada, vista por tercera vez y desde el lado de conda.

Lo unico afirmable: los 44 paquetes no referenciados ya no estan. Lo que el sistema de
ficheros devolvio queda por debajo de la resolucion de lo medido.

## La dimension `entornos` (tercera parte de la sesion)

Se kodifico el criterio que estaba solo escrito en `docs/ENTORNOS_CONDA/README.md`. Tres
capas, como manda el marco: `directives/auditar_entornos_conda.yaml` (capa 1),
`flujo_auditar_repo.py` (capa 2) y `execution/auditar_envs_conda.py` (capa 3).

Veredicto actual: `aviso`, `1 de 4 entornos frios, 0.37 GB de bloques exclusivos`
(`bio_env`). Medido en 14,7 s como dimension del compositor; 13,5 s en solitario.

### `bytes_exclusivos()` vive en la capa 3, no en el script de la dimension

La medicion compartida esta en `execution/catalogo_disco.py`, junto a `tamano()` y
`du_bytes()`, que es donde ya vivian las primitivas de disco. `auditar_envs_conda.py` la
importa. La alternativa era duplicar el recorrido en el script de la dimension, que es
justo la forma de tener dos medidas de lo mismo que divergen en silencio.

La regla que hace que funcione: se cuenta un directorio SIEMPRE (con su `st_nlink >= 2`,
que en un directorio cuenta subdirectorios, no enlaces) y un fichero solo si
`st_nlink == 1`. Medido: `pkgs` 6,81 GB aparentes / **2,00 GB exclusivos**; `elect_env`
5,87 / 5,90; `IA` 2,33 / 1,48. Los 2,00 GB de `pkgs` confirman el ~2,2 GB que se venia
estimando a mano.

### Dos bugs reales, encontrados por escribir el control positivo

1. **`grep -l` hacia inutil el detector de referencias.** `buscar_referencias` usaba
   `grep -rIl`, que imprime SOLO el nombre del fichero, y luego atribuia cada
   coincidencia a un entorno mirando el contenido de la linea. El contenido no estaba
   ahi, asi que la funcion devolvia SIEMPRE vacio, sin error y sin nota: exactamente
   indistinguible de "no hay nada que limpiar". Seillo con un control positivo
   (`pcb_env`, que si esta referenciado) en vez de dar por buena la salida vacia.
   Ahora usa `grep -rIn` y atribuye con la MISMA funcion que genera el patron.

2. **El flag del entorno solo se cubria en corto.** Los anclajes aceptaban `conda
   create -n x` pero no `conda create --name x`, que es la forma que usa el `setup.sh`
   mas legible de todos, el que la gente copia al crear un entorno. Anadido `--name`
   a los cinco anclajes.

El recorte de la ruta tambien estaba mal: `rsplit(":", 2)` sobre `ruta:linea:contenido`
parte por los dos ultimos dos puntos, y como el contenido puede traer los suyos, el
numero de linea se quedaba pegado a la ruta. Resuelto anclando `:(digitos):`.

### Un fallo mio, no del codigo, que conviene no repetir

La primera asercion de borde del test afirmaba que "90 dias exactos cuenta como
dentro", y habia puesto el `.pyc` 5 s MAS ALLA del corte. El corte de `find -newermt` es
un `>` estricto y por tanto estaba bien; la afirmacion era mia. Se sustituyo por los dos
lados del borde con margen (89,9 dias dentro / 90,1 fuera) y se documento que la
semantica del corte se escribe, no se hereda sola.

Lo mismo con dos lineas de prueba: la de `envs/cyber_env/` y la de `-n agent_env` se
probaban contra el patron de `pcb_env`. Fallaban, y el fallo parecia del detector.

### El compositor obliga a actualizar la expectativa, no a derivar en silencio

`test_auditar_repo.py` falló 2 de 127 al anadir la dimension, por dos aserciones de
conteo (6 reutilizadas, 13 totales). Actualizadas a 7 y 14, mas una asercion nueva que
comprueba que `entornos` es reutilizada. Ese test es lo que impide que el numero de
dimensiones se quede viejo en silencio.

Bateria completa en verde: barrera 83/0, `test_auditar_repo` 128/0, `test_auditar_sistema`
102/0, `test_verificar_texto` 22/0, `test_auditar_entornos` 58/0. Auditoria completa: 14
dimensiones en 85,8 s, `con_avisos`, exit 0, 0 con fallo.

### `conda-pkgs` deja de prometer 7 GB que no existen

El P2 de arriba era la tercera vez que se veia la misma sobreestimacion. Se cierra de
una vez con `medir_exclusivo=True` en el `Target`: `bytes_purgables` pasa a ser el peso
exclusivo y el aparente se conserva aparte, para que la diferencia (6,8 GB / 1,9 GB)
sea visible y no una cifra magica. La descripcion del target, que hardcodeaba "11 GB" y
"~2,4 GB", esta actualizada: esas cifras estavam escritas a mano y ya no son ciertas.
Aviso de coste: el recorrido en exclusivo sobre `pkgs` son ~14 s extra en la dimension
`disco`.

- **P2 RESUELTO (correccion, no espacio)** la guarda de antiguedad de `disco_medir` y
  `disco_purgar` preguntaba al DIRECTORIO CONTENEDOR, no al target. Con un patron
  estrecho eso no es lo mismo: `tmp-clones` (`.tmp/repo_clone_*`, min 7d) se
  conservaba porque `.tmp/` tenia 211 ficheros de menos de 7 dias — los informes
  que genera la propia auditoria — y no por nada de los clones. Un guard que da
  True siempre que haya actividad en el repo no protege nada, solo oculta el
  espacio. Ahora `hay_entradas_recientes_de_target()` pregunta por las entradas
  que casan, que es la lista que `_plan_entradas()` borra; `contenido`/`rotar`
  (patron `*`) no cambian, porque ahi preguntar por todos los hijos ya era
  correcto. **No libera espacio**: ver P4, la razon de verdad es otra.
- **P4 abierto, requiere decision del usuario** los 115 MB de `tmp-clones` siguen
  conservados, y ahora por una razon VERIFICADA: `.git/` de cada clon tiene mtime
  de hace minutos, mientras el unico fichero reciente de 11.184 es el propio
  directorio `.git` (ni un solo objeto, ni reflog, ni FETCH_HEAD). Medido:
  `git status` dentro del clon mueve ese mtime sin reescribir `.git/index`.
  Es decir, la guarda la puede disparar una herramienta, no el humano. Y algo las
  dispara cada ~1-2 min: no hay crontab, ni timer systemd sospechoso, ni proceso
  vivo, y nada del repo invoca git sobre repos descubiertos. **No se identifica al
  autor.** La pregunta de politica es si `min_edad_dias` debe ignorar la
  bookkeeping de un VCS: `.git` cambiando no es actividad de la persona. Es la
  misma distincion que ya hace la dimension `entornos` con `.pyc` (evidencia de
  uso, no mtime de cualquier fichero), pero aqui la respuesta es al reves y relaja
  una guarda de borrado, asi que no se decide solo.
- **P2 obsoleto, se corrige la anotacion** el P2 anterior de `tmp-clones`
  ("marcado conservado_reciente por el `.git` interno de 19,8/22,9 dias") era
  medio verdad y senalaba a la solucion equivocada. El sintoma se ve igual, pero la
  causa de la guarda era el padre, no el `.git`. El `.git` explica el residuo (P4).

## Pendientes
- ~~**P1** `flujo_auditar_repo.py:521` retira `run_state.json` al cerrar.~~
  **RESUELTO**: la vista pasa a `run_state_{run_id}.json` y se borra al cerrar la
  corrida, con el mismo criterio y los mismos comentarios que
  `flujo_auditar_sistema.py`. Verificado: tras una pasada completa no queda ninguna
  vista de la corrida, y la dimension `estado_sesion` dejo de reportar huerfanos.
- **P2** el problema de fondo es de REPO, no de este flujo: **16 flujos siguen
  escribiendo el mismo `run_state.json`** (`flujo_disco`, `flujo_verificar_texto`,
  `flujo_evaluar_examen`, `flujo_elaborar_examen`, `flujo_analizar_imagen`,
  `flujo_consultar_docs`, `flujo_curar_dataset`, `flujo_diagnostico`,
  `flujo_elaborar_ejercicios`, `flujo_empaquetar_dataset`, `flujo_imagen_a_kicad`,
  `flujo_libro_a_skill`, `flujo_motor_fallback`, `flujo_publicar_hf`,
  `flujo_repo_a_skill`, `flujo_resolver_skill`). Con nombre fijo, dos flujos
  simultaneos se pisan la vista y el emparejamiento vista<->log que verifica
  `estado_sesion.py` atribuye la vista de uno al log del otro. NO se ha tocado
  ninguno: son 16 ficheros y la decision (migrar todos a `run_state_{run_id}.json`
  como hizo `auditar_sistema`, o un subdirectorio por flujo) merece su propia
  sesion, con su test, en vez de colarse aqui.
- ~~**P1** `flujo_disco.py:141` imprime `0 B` para `--tier todos`.~~
  **RESUELTO**. El arreglo no fue poner la clave que faltaba: la impresion y la
  decision leian el diccionario por dos caminos distintos, asi que el flujo podia
  decir una cifra y decidir sobre otra. Ahora las dos salen de `bytes_tier`, y el
  formateo se importa de `catalogo_disco.TAMANO_HUMANO` en vez de reimplementar el
  redondeo (dos redondeos distintos para el mismo numero hacen dudar de los dos).
  Medido: `--tier todos` pasa de `0 B` a `751,0 MB`.
- **P3** `.tmp/run_state_sismico.json` no tiene `run_id` ni `status`: la dimension
  `estado_sesion` lo reporta como "sin log append-only" y correctamente NO lo borra.
  Preexistente y ajeno a este trabajo; queda anotado para no confundirlo con un
  efecto secundario.
- ~~**P1** `execution/auditar_envs_conda.py` como dimension `entornos`.~~
  **RESUELTO**: registrada y en verde (`aviso`, `1 de 4 frios, 0.37 GB`). El criterio
  que estaba solo en prosa ya esta en codigo, con directiva y con test.
- **P2** `bio_env` aparece como `frio` en la dimension, aunque su proyecto
  (BIOANALISIS) esta vivo. No esta protegido por politica y ningun script lo declara por
  nombre, asi que el detector no tiene forma de saberlo: por construccion solo ve
  ejecucion y referencias. Decision pendiente: anadirlo a `--protegidos`, o aceptar que
  un proyecto vivo sin entorno declarado se lea como frio. La dimension no borra nada,
  asi que el riesgo es de lectura, no de perdida.
- **P2** `conda clean --packages` mide **536,7 MB** (44 paquetes) huerfanos en
  `anaconda3/pkgs` tras la limpieza. **RESUELTO más abajo.**
- **P2** 3 referencias colgantes a interpretes ya eliminados, **no reparadas**
  deliberadamente: `CYBERSEGURIDAD/.vscode/settings.json:2` (`cyber_env`),
  `AGENTE_IA_FABRICACION_DIGITAL/setup.sh:6` (`pcb_env`, se recrea al ejecutarse) y
  la mencion documental en `TELEMEDICINA/README.md:39` + `.gemini/AGENT_FRAMEWORK.md:18`
  (`agent_env`). Son proyectos congelados; tocarlos es trabajo en repos inactivos.
  Los recipes de todos estan en `docs/ENTORNOS_CONDA/recetas/`.
- ~~**P2** `flujo_disco.py` sobreestima `conda-pkgs`.~~ **RESUELTO** con
  `medir_exclusivo=True`: `bytes_purgables` es 1,9 GB (exclusivo) y el aparente (6,8 GB)
  se conserva aparte. Medir `pkgs/cache` + tarballs era la otra salida, pero recortaba
  una carpeta en vez de medir la diferencia real, y habria vuelto a mentir en el otro
  sentido si conda cambiara de layout.
- **P2** `tmp-clones` se marca `conservado_reciente` con `min_edad=7` siendo que
  los clones tienen 19,8 y 22,9 dias. El guard `find -newermt` encuentra el
  `.git` interno del clon como reciente. Senal de vida confundida con ruido: un
  clon abandonado tiene `.git` que el flujo tocó al clonar y no vuelve a tocar.
  Salida tecnicamente correcta, decision equivocada.
- **P2** Bajar del 87 % exige decisiones de verdad, ya identificadas y medidas:
  `flatpak` 4,9 GB con 3 versiones de `org.freedesktop.Platform.GL.default`
  (462+462+470 MB) y 2 de `Platform` (fuera del catalogo, requiere sudo).
  ~~14 envs conda sin uso medido~~ → **resuelto más abajo: 12 eliminados**.
- **P2** `.git` = 733 MB. Dos `workerd` de 102 MB trackeados en `node_modules`,
  mas `ESP32-LAB/.pio/` (118 MB) y el MP4 (40 MB). Sacarlos del indice NO reduce
  `.git`: exige reescribir historia. No autorizado hoy.
- Sin tocar, de sesiones previas: `-halt-on-error` en `compile_latex.py`; 3 PDF
  desfasados (`docs/MANUAL/manual.tex`, `docs/CIRC_DISP_ELECT/EJM-4-1.tex`,
  `docs/COMPUTO_PARALELO/diseno_cluster.tex`); `docs/MATENIMIENTO/` sin enlazar
  desde `AGENTS.md`; tabla canonica flujo-directiva (capa 1 no verificable); hueco
  de code-switching en el verificador de texto; monitoring del saldo de
  OpenRouter; 30 ficheros untracked.
