# 2026-09-27 — auditoria_higiene_repo

## Tema
auditoria_higiene_repo

## Contexto
- Pregunta del usuario: si ya existe en el workspace un evaluador de higiene del
  repo, y si no, crear el flujo. Motivo de fondo: el proyecto tiene 13
  verificadores parciales independientes (texto corrupto, estado de sesion,
  bitacoras, logs append-only, disco, FAQ, LaTeX...) y ningun compositor. Cada
  uno era correcto en su ambito y todos podian salir en verde mientras el repo
  estaba peor de lo que ninguno de ellos mira. El caso concreto que lo
  motivation: `.tmp/run_state.json` era JSON valido pero sin `run_id`, y por eso
  `estado_sesion.py` lo clasificaba como corrupto. Nadie lo habia visto, porque
  cada verificador miraba su propio trozo.
- El flujo de texto (commit `6a0eaf3`, mismo dia) habia destapado el problema
  desde el otro lado: 22 aserciones fijaban su comportamiento. La auditoria
  sirve para lo contrario, demostrar que una comprobacion sin test vuelve a
  romperse sola.

## Decisiones (usuario)
1. El veredicto global debe ser el PEOR estado de las dimensiones, sin
   puntuacion ni media. Motivo medido: 12 dimensiones sanas sobre 13 darian un
   promedio de 0.92 y taparian un disco al 91%. Decidido por el usuario tras
   exponer el caso, no por criterio propio.
2. "No verificado" es un veredicto de primera clase con su propio codigo de
   salida (2): una dimension que no se pudo medir impide que el conjunto salga
   como limpio.
3. La auditoria es de solo lectura. No borra, no toca el indice de git y no
   reescribe historia. Lo que encuentre se reporta con su accion y su
   consecuencia; corregirlo es decision del operador.
4. Reducir el historial de git (los 3 `workerd` de 97.4 MB) queda FUERA: exige
   `filter-repo`, tiene consecuencias y no se decide en una sesion de hygiene.
5. Los 12 untracked antiguos NO se stagean. Son trabajo de otras sesiones; un
   `git add .` a ciegas se lo lleva.

## Actividades
- Inventario de los verificadores existentes: confirma cobertura fragmentada y
  la ausencia de compositor. Se corrige una suposicion previa: NO existe
  `docs/AGENTE_IA/higiene_estado_sesion.md`, solo el `.tex`, su PDF y el FAQ.
- Capa 3 `execution/auditar_repo.py`: 7 comprobaciones nuevas (secretos, logs,
  directivas, capas, peso_git, untracked, pdf_stale), todas de solo lectura.
- Capa 2 `flujo_auditar_repo.py`: orquesta 13 dimensiones (7 nuevas + 6
  reutilizadas), cada una con su timeout y su interprete explicito.
- Capa 1 `directives/auditar_repo.yaml`: 6 pasos, 18 edge cases, 9 invariantes.
- `execution/test_auditar_repo.py`: 81 aserciones. El nucleo es
  `clasificar_salud`, que es FUNCION PURA y se testea sin ficheros ni git.

Hallazgos del propio flujo durante la construccion (todos ya corregidos):
- `RAIZ` apuntaba un nivel por encima del repo: `flujo_auditar_repo.py` vive en
  la raiz, no en `execution/`, y el patron estaba copiado de `flujo_disco.py`.
- Los interpretes de `bitacoras` y `estado_sesion` asumian que el total era un
  entero; son listas. Con la forma real de la salida, ambas dimensiones salian
  `no_verificado` siempre. Cada interprete se probo con la salida real de su
  script, no con la imaginada.
- `estado_sesion.py` mete `huerfano` y `corrupto` en la misma bolsa y lo publica
  como `anomalias`. Contar esa cifra daba `fallo` a una vista que solo estaba
  pendiente de purgar. Se cambio a mapear por veredicto: solo `corrupto` es
  fallo.
- BUG REAL DE SEGURIDAD: un `estado` fuera del vocabulario caia fuera de todos
  los `if` del clasificador y salia como `limpio`. Es el mismo verde falso por
  otra via, y lo introdujo el diseno horas antes. Ahora degrada a
  `no_verificado` y nombra la dimension.
- La deteccion de capa 3 buscaba la forma de la ruta (`SCRIPT_DIR / execution`) y
  dio 13 falsos positivos en flujos que si delegan, porque construyen la ruta
  con `Path(...)`. Se cambio a intersectar el nombre del script con los ficheros
  REALES de `execution/`.
- El escaneo de secretos dio falsos positivos en codigo vendorizado (workerd,
  miniflare). Se excluyen por prefijo; un detector que solo sabe decir "algo
  hay" acaba ignorandose.
- El flujo detecto DOS fallos en su propio test nuevo, en la primera pasada
  completa: un caracter CJK en un comentario y un header de clave PEM
  literal usado como fixture. El primero lo cazaba la dimension `texto`; el
  segundo, la dimension `secretos`. Ambos en `execution/test_auditar_repo.py`.
- Se corrigio de paso el bug de trazabilidad de `flujo_verificar_texto.py`: no
  escribia `run_id` ni log append-only, que es justo lo que hacia que
  `estado_sesion.py` lo marcara corrupto. Ese flujo era, sin saberlo, el primer
  fallo real que la auditoria iba a encontrar.
- Se elimino `_interpreta_logs_append_only` del flujo: quedo como codigo muerto
  cuando la dimension `logs` paso a ser nueva. En una herramienta de hygiene,
  dejar codigo muerto seria ironico.

Diagramas: `docs/AGENTE_IA/auditar_repo_flujo.tex`/`.pdf`, 5 paginas, dos
secciones (la pasada y el algebra del veredicto), 0 errores y 0 solapes.
El icono `magnifying-glass` resulto no existir en fontawesome5; se sustituyo por
`shield-alt`. Los iconos del resto de descriptores del repo si valen.

## Pendientes
- **12 referencias a scripts inexistentes en 10 directivas.** Es el unico fallo
  estructural de la capa 1: una directiva que apunta a un script borrado no
  avisa, simplemente nunca se ejecuta. Los scripts son
  `db_delete_memory.py`, `db_list_memories.py`, `db_query_memory.py`,
  `db_save_memory.py` (4 directivas de memoria), `freecad_generate.py`,
  `kicad_auto_pcb.py`, `clone_repo.py`, `generate_tree.py`, `git_sync.py`,
  `web_search.py`, `process_search_results.py` y `sys_maintain.py`. Decidir por
  cada una: crear el script, o reescribir/retirar la directiva.
- **Disco al 91.3%, 20.39 GB libres, 0 MB recuperables** con borrado seguro. No
  lo arregla este flujo: exige decidir que se sacrifica.
- **3 PDF desfasados** respecto a su `.tex`: `docs/MANUAL/manual.tex` (5071 s),
  `docs/CIRC_DISP_ELECT/EJM-4-1.tex` (852 s) y
  `docs/COMPUTO_PARALELO/diseno_cluster.tex` (713 s). Recompilar.
- **3 `workerd` de 97.4 MB trackeados**, bajo el limite de 100 MB pero a 2.6 MB
  de que GitHub bloquee el push. Sacarlos del indice no reduce `.git`.
- **MP4 de 38.6 MB** `docs/CURSO_PYTHON/Crear_3_programas_Solana.mp4` sigue
  trackeado. Retirarlo exige reescribir historia; decision del usuario.
- **Capa 1 no verificable**: el mapeo flujo-directiva no es 1:1 y solo 4 de 20
  flujos declaran `orchestrator:`. Si se quiere cerrar esa dimension hace falta
  una tabla canonica de equivalencias.
- 1 vista de estado sin log append-only (`.tmp/run_state_sismico.json`): no se
  borra sola, es evidencia de un flujo antiguo.
- Pendientes de otras sesiones, NO tocados aqui: `-halt-on-error` en
  `compile_latex.py`; la sobreestimacion ~4.5x del dry-run de disco; targets
  `recargable` y `pesado` de purga; "5 celdas" a 4 en el canario de Colab;
  monitoring del saldo de OpenRouter.
- Bloqueos de fondo: `conda defaults` falla por manifiesto `tk` corrupto
  (workaround `--override-channels -c conda-forge`); Groq legacy devuelve 403
  desde Venezuela y requiere VPN.
