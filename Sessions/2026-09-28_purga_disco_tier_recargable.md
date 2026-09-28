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

## Pendientes
- **P1** `flujo_auditar_repo.py:521` retira `run_state.json` al cerrar, igual que
  `flujo_auditar_sistema.py`. Y desambiguar `STATE_FILE` por flujo
  (`run_state_{run_id}.json` o un subdirectorio por flujo), porque el emparejamiento
  vista<->log es justo lo que `estado_sesion.py` verifica.
- **P1** `flujo_disco.py:141` imprime `0 B` para `--tier todos`: "todos" no es
  clave de `reclaimable_por_tier`. Regresion del arreglo de `3959955`, que solo
  cubria el default. Con regresion.
- **P1** `execution/auditar_envs_conda.py` como dimension `entornos` de
  `flujo_auditar_repo.py`. Motivacion medida: la dimension `disco` del compositor
  declara "39,2 MB recuperables" mientras la respuesta buena eran 4 GB de conda que
  no mira. El criterio (`.pyc` en 90 dias + referencias en
  `~/MEGA/VS_CODE_WORKSPACE`) ya esta escrito y razonado en
  `docs/ENTORNOS_CONDA/README.md`: falta solo codificarlo. Enquanto sea manual, la
  proxima sesion vuelve a reconstruir la evidencia a mano.
- **P2** `conda clean --packages` mide **536,7 MB** (44 paquetes) huerfanos en
  `anaconda3/pkgs` tras la limpieza. NO ejecutado: es una operacion nueva, fuera de
  la whitelist de `flujo_disco.py` y sin autorizacion del usuario. Es re-descargable
  y no toca ningun env, asi que el riesgo es bajo, pero es decision suya.
- **P2** 3 referencias colgantes a interpretes ya eliminados, **no reparadas**
  deliberadamente: `CYBERSEGURIDAD/.vscode/settings.json:2` (`cyber_env`),
  `AGENTE_IA_FABRICACION_DIGITAL/setup.sh:6` (`pcb_env`, se recrea al ejecutarse) y
  la mencion documental en `TELEMEDICINA/README.md:39` + `.gemini/AGENT_FRAMEWORK.md:18`
  (`agent_env`). Son proyectos congelados; tocarlos es trabajo en repos inactivos.
  Los recipes de todos estan en `docs/ENTORNOS_CONDA/recetas/`.
- **P2** `flujo_disco.py` sobreestima `conda-pkgs` contando el peso bruto de un
  directorio lleno de hardlinks. Medir `pkgs/cache` + tarballs, no la carpeta.
  Sobreestimacion ya anotada en sesiones previas; hoy cuantificada: ~2,2 GB reales
  frente a 9,68 GB declarados.
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
