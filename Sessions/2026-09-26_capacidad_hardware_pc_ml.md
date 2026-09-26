# 2026-09-26 — capacidad_hardware_pc_ml

## Tema
Inventario real del hardware del PC (tras reinicio) y veredicto sobre su uso para
entrenamiento de modelos de IA.

## Contexto
El usuario Asked si el workspace tenía un `flujo_*` para conocer el hardware, con la
intención de decidir si su PC servía para TensorFlow. La sesión empezó siendo una
consulta de inventario y acabó fijando una **política de capacidad** del proyecto.

Inventario medido (vía `execution/env_diagnostic.py` + `free` + `lscpu` + `lsblk`):

| | |
|---|---|
| Placa / BIOS | Lenovo `LNVNB161216` · BIOS `DVCN20WW` (2021-05-25) |
| CPU | Intel Celeron N4020 @ 1,1 GHz — **2 núcleos**, turbo 2,8 GHz |
| SIMD | **solo `sse4_1` / `sse4_2`** — sin AVX, AVX2 ni FMA (confirmado por 3 vías) |
| RAM | 3,63 GB totales · ~1,6 GB disponibles |
| Swap | `/swapfile` 4 GB + `zram0` 1,8 GB (evita OOM, pero ralentiza) |
| Disco | Samsung `MZALQ256HAJD-000L2` NVMe 238,5 GB (SSD, ~87% usado) |
| GPU | **ninguna usable**: Intel UHD 600 integrada; TensorFlow no la exploitada |

Dos bugs de datos encontrados y corregidos (importantes para no decidir sobre cifras falsas):

1. **`get_ram_info()` reportaba 0,15 GB disponibles y 95,9% de uso cuando la verdad
   eran ~1,5 GB y ~55%.** Dos causas encadenadas: `psutil` no estaba instalado en
   `elect_env` (aunque `requirements.txt` lo declara) y el fallback a `/proc/meminfo`
   leía `MemFree` en vez de `MemAvailable` — el `if not mem_free: # priorizar
   MemAvailable` se cumplía con el campo equivocado porque en `/proc/meminfo`
   `MemFree` aparece *antes* que `MemAvailable`. Con el dato falso, cualquier agente
   concluiría "imposible" y abortaría tareas o delegaría a Colab sin motivo.
2. **El parser de `lsblk` truncaba el modelo del disco** (`SAMSUNG` en vez de
   `SAMSUNG MZALQ256HAJD-000L2`) porque un `split()` ingenuo parte
   `MODEL="con espacios"` en varios tokens y descuadra las columnas siguientes.
   Resuelto con `lsblk -P` + `shlex.split()`. También se filtró `zram0`, que no es
   almacenamiento.

## Decisiones (usuario)
1. **Esta PC NO se usará para entrenamiento de modelos de IA.** Todo entrenamiento
   se hace en **Google Colab**. Sin excepciones: la decisión es de política, no
   condicionada a una medición ("si cabe, lo hago local").
2. **El framework de entrenamiento en Colab es TensorFlow** (no PyTorch), decidido
   por el usuario tras revisar el notebook de prueba de Colab que existía en la raíz
   del repo.
3. En consecuencia, **no hace falta** el script de verificación de capacidad
   (`execution/verificar_capacidad_ml.py`) que se había propuesto: al ser la regla
   incondicional, deja de ser una decisión a medir y pasa a ser una constante de la
   política. No construir lógica de decisión donde la regla ya es constante.
4. **Se conserva el notebook de Colab** y se convierte en la entrada canónica de la
   vía de entrenamiento: `docs/COLAB/entorno_colab.ipynb`.

## Actividades
- Corregido el bug de RAM en `execution/env_diagnostic.py`: `psutil` instalado en
  `elect_env` (7.2.2) y fallback reescrito con parseo por clave exacta vía
  `shlex`. Añadidos `free_gb` y `fuente` (`psutil` / `proc_meminfo`) para auditar el
  origen del dato. Verificado bloqueando `psutil` a propósito: el fallback da
  1,60 GB / 55,9%, idéntico a `psutil`.
- Ampliado el inventario con `get_board_info()` (DMI de sysfs, **sin sudo**, a
  diferencia de `dmidecode`) y `get_disk_devices()` (modelo + SSD/HDD vía `lsblk`).
- Ambas secciones renderizadas en el informe PDF (`flujo_diagnostico.py`):
  `\subsection{Placa Base y BIOS}` y `\subsection{Discos Detectados (SSD / HDD)}`.
- Bug propio corregido durante la verificación: en un f-string **no raw**, `\\n` es
  backslash + `n`, no salto de línea, así que un `\n` literal llegó al LaTeX como
  comando inexistente.
- **Laguna de validación detectada (NO corregida, pendiente de decisión):**
  `execution/compile_latex.py` invoca `pdflatex` con `-interaction=nonstopmode` y
  solo comprueba `returncode`. En nonstopmode `pdflatex` continúa tras un error y
  sale con 0 generando PDF, así que un `.tex` roto se reporta como
  "✅ Reporte PDF generado". Los `!` del log solo se leen si `returncode != 0`, o
  sea nunca. El arreglo sería `-halt-on-error` (solo detiene en errores, no en
  warnings, así que las 2 pasadas siguen resolviendo `LastPage`); NO se aplicó
  porque `compile_latex.py` lo comparten el MCP de LaTeX y otros flujos.
- Verificado que TensorFlow **sí funciona** en esta máquina (env `IA`, TF 2.19.1):
  `matmul 1000×1000` en 0,25 s ≈ 8 GFLOP/s, 485 MB de RSS. Se descartó la hipótesis
  de que la falta de AVX lo impidiera: las wheels modernas hacen *dispatch* en
  runtime y el propio `cpu_feature_guard` confirma que solo usa SSE4.1/SSE4.2.
  Por tanto la causa de no entrenar es la **política** del usuario, no una
  imposibilidad técnica.
- Verificaciones: `pdflatex` 2 pasadas → 0 errores, 0 overfull, 0 refs indefinidas,
  3 páginas. `env_diagnostic.py` path-agnostic y determinista en estructura.
  `execution/test_barrera_disco.py` intacto: 87 aserciones, 0 fallos.
- Regenerados `docs/DIAGNOSTICOS/informe_diagnostico.{tex,pdf}`.

## Ejecutado (autorizado por el usuario)
### A. Limpieza de conda — 3,40 GB liberados
- Añadido el target **nativo** `conda-pkgs` (`~/anaconda3/pkgs`, tier `recargable`,
  `cmd="conda clean --all -y"`) a `execution/catalogo_disco.py`. El `-y` es necesario
  porque el flujo lo ejecuta sin terminal interactiva. **No se invocó `conda clean`
  desde la shell**: todo borrado pasa por `flujo_disco.py` y la whitelist del catálogo.

### B. Canario de Colab — entrada canonica del entrenamiento en TF
- **Canario de Colab creado:** `test_colab.ipynb` (raiz del repo, 4 celdas, solo
  torch) → `docs/COLAB/entorno_colab.ipynb` vía `git mv`, conservando historial.
  Reescrito como **entrada canónica** de la vía de entrenamiento en TF:
  - **Celda 1 = persistencia (Drive).** Era el agujero real: las sesiones de Colab son
    efímeras y el notebook original no montaba nada, así que cualquier modelo
    entrenado se perdía al cerrar sesión. Ahora monta Drive y crea
    `MyDrive/electronica_ml/{datasets,checkpoints,modelos,resultados}`.
  - Celda 2: inventario de la sesión (Python, SO, RAM, núcleos, disco de `/content`).
  - Celda 3: versión de TF, GPUs detectadas y detalles vía `get_device_details`.
  - Celda 4: **fuerza un `matmul` 2000×2000 en GPU** con `with tf.device('/GPU:0')` y
    llamada `.numpy()` para forzar ejecución, más comparativa CPU y factor de
    aceleración. Detectar la GPU no es computar en ella: un runtime puede anunciarla y
    fallar al usarla.
  - Celda 5: tabla de veredicto con los 3 criterios (Drive montado, ≥1 GPU, GPU OK).
- **Verificado, no supuesto:** las 5 celdas de código parsean con `ast.parse`; barrido
  de caracteres no latinos (CJK/circílico) para cazar un `核` que se me coló en un
  título — eliminado; ninguna celda queda con variables sin definir; 0 referencias al
  nombre viejo en el repo.
- **Política anclada en `AGENTS.md`** ("Know before you act"): el entrenamiento va a
  Colab con TensorFlow y el canario es requisito previo. Antes `AGENTS.md` no mencionaba
  Colab en absoluto, así que la decisión no habría sobrevivido a la sesión.
- **Pregunta abierta, no respondida:** ¿dónde vive TensorFlow en local? No se tocó
  `IA`: es el único env con TF 2.19.1 y la única fuente de `keras`/`pandas`/`matplotlib`.
  Borrarlo libera 2,2 GB pero obliga a reinstalar ~600 MB con el disco al 91%.
- **La barrera anti-borrado frenó el primer intento.** El test solo trataba
  `modo="directorio"` como destino y, para `nativo`, validaba el primer *hijo* de
  `pkgs`, que legítimamente no está en el catálogo → `fuera_de_catalogo`, 1 fallo.
  Corregido el test: `nativo` se valida sobre la ruta propia del target, que es
  exactamente lo que valida `disco_purgar` antes de ejecutar. Volvió a 0 fallos con
  88 aserciones. La barrera impidió purgar fuera de catálogo: funcionó como debía.
- Secuencia: `--check` → `--dry-run` → `--yes`. **Liberados 3,40 GB**
  (17,24 → 20,64 GB libres; 92,6% → 91,1%). Segunda pasada: **0 B (idempotente)**.
- Envs verificados intactos tras la purga: `elect_env` (torch 2.12.0, numpy 2.2.6,
  psutil 7.2.2), `IA` (tensorflow 2.19.1), `base` (numpy 2.1.3). Ningún env usa
  symlinks al `pkgs`, que es la advertencia oficial de `conda clean --all`.
- **Corrección de la premisa de los "11 GB":** la cifra venía de `du` sobre el
  directorio, no de lo recuperable. Solo ~2,4 GB lo eran; los ~7,5 GB restantes son
  paquetes en uso por los 16 envs. Aun así quedó en 91,1% de uso, por debajo del
  umbral del 90% solo por poco: la próxima sesión debe mirar `arduino-packages`
  (5,4 GB) y `conda env remove IA`, no esperar a que `conda clean` lo resuelva.

## C. Entorno de TF local — se decide KEEP en `IA` (no hay ahorro posible)
Pedido: "ejecuta la opción que implique ahorro de espacio". **La premisa era falsa y
no se ejecutó ningún borrado.** Lo que se midió:

| Entorno | Peso | Resultado |
|---|---|---|
| **`IA`** (py3.11.14, `tensorflow` 2.19.1) | **2,2 GB** | **FUNCIONA** (`.so` de 584 MB) |
| venv py3.10 (`tensorflow` 2.19.1) | 2,1 GB | **SIGILL** (`.so` de 1,1 GB) |
| venv py3.10 (`tensorflow-cpu` 2.19.1) | 2,1 GB | **SIGILL** (`.so` de 655 MB) |
| venv py3.11.15 (`tensorflow` 2.19.1) | 2,2 GB | **SIGILL** (`.so` de 1,18 GB) |

- **No existe ahorro**: todos los candidatos pesan 2,1–2,2 GB, igual que `IA`. El
  ahorro estimado que di antes ("~600 MB de reinstalación") era **falso**: TF domina
  el tamaño y da igual la wheel. `IA` es ya el mínimo, y además el **único que
  funciona**.
- **Corregida mi hipótesis del Python**: no era cp310 vs cp311. También revienta en
  3.11. La variable real es **el build del `.so`**: el de `IA` (584 MB) sí hace
  *dispatch* en runtime a SSE4.1/SSE4.2 (lo anuncia: *"To enable SSE4.1 SSE4.2, rebuild
  TensorFlow"*), los freshly-installed (1,1–1,18 GB) usan instrucciones que la N4020 no
  tiene y mueren con exit 132. No se Investigó más allá: no es una regla conocida y la evidencia es empírica.
- **Auditoría previa a borrar**: nada depende de `IA` (sin pin en VS Code/opencode,
  sin shebangs en el repo, sin servicios systemd). Aun así no se borró: borrar el
  único TF funcional para ganar 0 GB habría sido absurdo.
- **Hallazgo colateral grave: `base` tiene TF 2.20.0 (1,8 GB) que NO ARRANCA**
  (SIGILL al importar, py3.13). Es peso muerto: 1,8 GB que no puede usarse en esta
  máquina. Es la **única ahorro real** que queda, pero está en la raíz de conda →
  **no se tocó sin confirmación del usuario**.
- **Bug de conda detectado (bloquea crear entornos)**: `conda create -n X python=3.11`
  falla con *"appears to be corrupted... ouster.png"*. Los tres builds de `tk`
  (8.6.13/14/15) están **parcialmente extraídos** en `pkgs/` (existe `lib/tk8.6/demos`
  pero faltan las imágenes) y sus tarballs ya no están (los borró el
  `conda clean --all` de esta sesión). Fijar otro build de `tk` no ayuda: el manifiesto
  de los tres lo lista. Workaround usado: `python -m venv` desde un interpreter
  existente, que no pasa por la resolución de conda.
- **Contabilidad de la sesión**: el venv fallido se borró (neutro), pero `pip` retuvo
  **1,6 GB de wheels** en `~/.cache/pip` → `pip cache purge` (305 ficheros, 1.704 MB).
  Disco final 21 GB libres / 91%, igual que antes de este intento.

## D. Reparaciones ejecutadas (autorizadas por el usuario)

### D1. TF muerto de `base` eliminado — 1,8 GB
- `conda remove` decía `PackagesNotFoundError: tensorflow`: **no lo instaló conda, lo
  instaló `pip`** (`INSTALLER: pip`, ausente de `conda-meta`). Por eso hay que quitarlo
  con `pip uninstall`, no con conda. `Required-by:` vacío → nada dependía de él.
- `pip uninstall -y tensorflow` (2.20.0) en `base` → **1,8 GB liberados**.
- **Efecto secundario real:** `keras 3.11.3` de `base` quedó **roto**, porque
  `keras/src/utils/module_utils.py` hace `from tensorflow.python.trackable...` de forma
  incondicional → `ModuleNotFoundError` al importar. Se desinstaló también
  (`Required-by:` vacío). No se deja un paquete roto "por si acaso".
- `base` verificado sano tras la operación: numpy 2.1.3, pandas 2.2.3,
  matplotlib 3.10.0, tkinter 8.6, ssl, sqlite3. **No queda TF ni keras en `base`.**

### D2. `tk` de `pkgs/main` es defectuoso — imposible de reparar localmente
- **Causa raíz (upstream, no local):** el manifiesto del paquete declara 12 imágenes
  de demo en `lib/tk8.6/demos/images/` pero el tarball solo trae 10. Falcan
  `ouster.png` y `earthmenu.png`. Al verificar, conda aborta **cualquier** creación de
  entorno que necesite `tk` (y `python` lo depende para tkinter).
- **Re-descargar NO lo arregla** (se probó): `conda install --force-reinstall
  tk=8.6.14` re-descargó el tarball y falló igual, ahora con **dos** ficheros
  ausentes. Los tres builds en caché (8.6.13/14/15) están afectados.
- **La transacción abortó limpiamente** (verificación fallida → rollback): `base`
  quedó intacto, `certifi` sin tocar.
- **Causa de que `base` no estuviera roto:** su `tk` funciona (tkinter 8.6 OK) porque
  a `tkinter` no le hacen falta las imágenes de demo; el fallo es solo la verificación
  estricta del manifiesto en la extracción.
- **Reparación disponible: usar `conda-forge`**, cuyo build sí trae las 12 imágenes
  (verificado: `ouster.png` presente). Verificado de extremo a extremo:
  `conda create -n X --override-channels -c conda-forge python=3.11` → Python 3.11.16
  con tkinter 8.6, ssl y sqlite3 operativos.
- **Nota sobre `--dry-run`:** `conda create --dry-run` **no reproduce el fallo** (no
  extrae ni verifica), así que un dry-run "pasa" y el fallo aparece al ejecutar. No
  usar dry-run como prueba de que la creación de entornos está sana.
- Entornos de prueba creados y eliminados; sin residuos.

## Pendientes
- **Entrenamiento de IA → Colab** (decisión firme). Local solo: inferencia, prototipos
  y validación. Si se propone entrenar aquí, recordar la política.
- Decidir si se añade `-halt-on-error` a `execution/compile_latex.py` (ver Actividad).
- **Fidelidad del dry-run nativo (sin arreglar):** en modo `nativo` la simulación estima
  `bytes_antes` (el `du` completo del directorio: 10,8 GB para `pkgs`), no lo que la
  herramienta oficial liberaría; sobreestima ~4,5x. La medición real posterior sí es
  exacta (`bytes_antes - bytes_despues`), así que el informe final no miente, pero la
  predicción sí. Arreglo posible: que el modo nativo consultara el `--dry-run` de la
  propia herramienta en vez de usar `du`.
- Sin commit: `execution/env_diagnostic.py`, `flujo_diagnostico.py`,
  `execution/catalogo_disco.py`, `execution/test_barrera_disco.py`, ambas bitácoras y
  el PDF regenerado están en el working tree.
- TF no está en `elect_env` (solo en `IA`); si alguna vez hiciera falta aquí,
  usar `tensorflow-cpu` y no `tensorflow` (la wheel completa arrastra paquetes
  NVIDIA de 2-3 GB inservibles aquí, y el disco está al 87%).
