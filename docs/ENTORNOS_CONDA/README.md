# Entornos conda: política de retention yrecipes de recreación

Documento de referencia de los entornos conda de la máquina y del criterio con el que
se decide cuáles se conservan. Sustituye a la inspección manual que hubo que hacer el
2026-09-28 para responder "¿cuáles entornos están sin usar?".

## Por qué existe

Los 14 entornos no críticos eran resultado de los primeros estudios sobre aislamiento
de proyectos con conda. Doce de ellos no corresponden a ningún proyecto que siga vivo.
Ocupaban **5,6 GB** y la pregunta de higiene del repo (`flujo_auditar_repo.py`) no los
miraba: los 39 MB que borraría el catálogo de disco no eran ni el 0,6 % de la respuesta.

Por eso este documento existe: para que la evidencia sea reproducible y la decisión
auditable, no para repetirla a mano.

## Criterio de retención (el que se aplicó)

Un entorno se considera **frío** si se cumplen las dos condiciones:

1. **Cero ficheros `.pyc` generados en los últimos 90 días.** Los `.pyc` los crea la
   *ejecución* del intérprete, no la instalación de paquetes. Es la única señal fiable
   de uso, a diferencia de:
   - `conda-meta/history`, que solo fecha la última operación de paquetes. Un entorno
     usado a diario sin instalar nada no lo toca: **miente**.
   - el mtime del directorio del entorno, que tampoco cambia al ejecutar.
   - `.bash_history`, que en esta máquina tiene 846 líneas, 12,9 KB y **sin timestamps**
     (además puede estar truncado). Sirve como apoyo, nunca como prueba.
2. **Ningún workspace vivo que lo declare por nombre.** Se buscan las referencias en
   todo `~/MEGA/VS_CODE_WORKSPACE` (no solo en el repo actual), porque un `setup.sh`
   de otro proyecto que dice `ENV_NAME="pcb_env"` es una dependencia real.

Si un entorno falla cualquiera de las dos, se conserva.

## Entornos conservados

| Env | Tamaño | Motivo |
|---|---|---|
| `elect_env` | 5,7 GB | **Activo.** Entorno del workspace ELECTRONICA; lo fija el plugin `.opencode/plugins/conda-env.js`. Único en 1460 ficheros tocados en 30 días. |
| `IA` | 2,3 GB | Sin uso desde 2025-10-25, pero es el **único TensorFlow funcional de la máquina** (2.19.1 verificado). Política: no se toca aunque esté frío. |
| `agro_env` | 0,8 GB | **En uso.** 67 `.pyc` en 90 días; `Agente-IA-Agro-Inteligente` tuvo commit el 2026-08-23 y lo declara en su `AGENTS.md`. |
| `bio_env` | 0,5 GB | Frío (0 `.pyc` desde 2026-06-25) pero `BIOANALISIS` tuvo commit el 2026-08-12 y 354 ficheros tocados en 90 días. Proyecto vivo, entorno inactivo. |

### Por qué `bio_env` está en `PROTEGIDOS_POR_POLITICA` y no se "arregló" el detector

`bio_env` es el caso que el criterio **no puede deducir**. El detector ve dos cosas:
ejecución (`.pyc` generados) y referencias (anclajes de conda en el workspace). Un
proyecto vivo cuyo entorno no aparece en ningún `setup.sh` —porque quien lo usa lo
activó a mano y ya no lo nombra en ninguna parte— es **invisible** para las dos señales
a la vez. Por eso salió `frío` con el proyecto corriendo.

La tentación era relajar el heurístico para que "un proyecto con commits recientes
cuente como uso". Eso sería **inventar un hecho**: commits recientes en un repo que
puede que ni siquiera se abra este mes. La alternativa elegida es declarar la
excepción donde ya vivían las otras dos:

```python
# execution/auditar_envs_conda.py
PROTEGIDOS_POR_POLITICA = ("elect_env", "IA", "bio_env")
```

Consecuencias, y son deliberadas:

- `bio_env` **deja de ofrecerse** como recuperable. Es correcto: la decisión de
  conservarlo ya está tomada y no la toma un script.
- `bio_env` **sigue informándose** en `frios_conservados`, con su peso exclusivo
  (0,37 GB), su `ultimo_pyc` y el motivo. Proteger cambia *si se recupera*, no
  *si se informa*: un entorno sin ejecución que ocupa disco sigue siendo un hecho,
  aunque la decisión sea conservarlo.
- La lista está **congelada en `test_auditar_entornos.py`**. Ampliarla tiene que
  romper un test a propósito, no colarse como consecuencia de otra medición.

La lista también se publica en la evidencia de la dimensión
(`criterio.protegidos_por_politica`): una excepción que no se ve es una excepción
que el próximo no puede ni cuestionar.

## Entornos eliminados (2026-09-28)

12 entornos, **5,6 GB** liberados. Todos con recipe en `recetas/` y todos cumpliendo
las dos condiciones del criterio.

| Env | Tamaño | Último `.pyc` | Nombrado fuera del repo (referencia colgada) |
|---|---|---|---|
| `pcb_env` | 1,00 GB | 2026-04-06 | `AGENTE_IA_FABRICACION_DIGITAL/setup.sh:6` → `ENV_NAME="pcb_env"` |
| `agent_env` | 0,78 GB | 2026-03-05 | `TELEMEDICINA/README.md:39`, `TELEMEDICINA/.gemini/AGENT_FRAMEWORK.md:18` |
| `cnc_bot_env` | 0,78 GB | 2026-02-23 | — |
| `hidro_env` | 0,61 GB | 2026-05-08 | — |
| `cyber_env` | 0,59 GB | 2026-05-24 | `CYBERSEGURIDAD/.vscode/settings.json:2` → `python.defaultInterpreterPath` |
| `agente_naviera` | 0,44 GB | 2026-01-14 | — |
| `pcb_env_312` | 0,30 GB | 2026-04-16 | — |
| `youtube_uploader` | 0,28 GB | 2026-01-12 | — |
| `d2c_env` | 0,23 GB | 2026-06-21 | — |
| `meerk_env` | 0,19 GB | 2026-06-07 | — |
| `fisica_env` | 0,19 GB | 2026-06-24 | — |
| `litografia_env` | 0,18 GB | 2026-02-04 | — |

### Efectos colaterales conocidos

Ninguno rompe nada en ejecución, pero quedan referencias colgantes a un intérprete
inexistente. **No se repararon**: son proyectos congelados y arreglar su `settings.json`
o su `setup.sh` sería trabajo en repos que no están activos.

- `CYBERSEGURIDAD/.vscode/settings.json:2` apunta a
  `/home/cero/anaconda3/envs/cyber_env/bin/python3.11`. VS Code mostrará el intérprete
  como no resuelto. Irónico: ese mismo repo ya documenta en `.agent/python.md:13` el
  aviso de Pylance por intérprete no encontrado como problema conocido, así que el
  sintoma es idéntico al que ya conocías.
- `AGENTE_IA_FABRICACION_DIGITAL/setup.sh` recrea `pcb_env` al ejecutarse; su
  `requirements.txt` sigue en pie.
- `TELEMEDICINA` solo menciona `agent_env` en documentación, incluido
  `.gemini/AGENT_FRAMEWORK.md` **como ejemplo genérico** de un framework (junto a
  `CONDA_NAME=<PROJECT_NAME>_env`), no como vinculación real.

## Recrear un entorno eliminado

Cada recipe es un `conda env export` completo, **con su sección `pip:`** (no solo conda:
`cyber_env` arrastra `scapy` y 100+ paquetes pip que no aparecen en un
`conda env export --from-history`).

```bash
# verificar que el recipe existe antes de nada
ls docs/ENTORNOS_CONDA/recetas/<env>.yml

# recrear (minutos; lo que tarda es resolver los canales de conda)
conda env create -f docs/ENTORNOS_CONDA/recetas/<env>.yml
```

Después hay que **reapuntar** las referencias colgadas de la tabla anterior, si el
proyecto vuelve a la vida.

## Lo que este documento NO cubre

- ~~La detección es manual. Falta la dimensión `entornos` en `flujo_auditar_repo.py`.~~
  **Resuelto el 2026-09-28**: la dimensión existe (`execution/auditar_envs_conda.py`,
  directiva `directives/auditar_entornos_conda.yaml`, 73 aserciones en
  `execution/test_auditar_entornos.py`) y aplica exactamente este criterio, más
  `bytes_exclusivos`. Las dos diferencias con la inspección manual: la dimensión no
  conoce la política de este documento por sí sola (la recibe en
  `PROTEGIDOS_POR_POLITICA`) y no cruza commits, porque no es una señal de ejecución.
- `.pyc` no distingue "se ejecutó" de "se importó sin ejecutar nada" (un `import` en un
  REPL también compila). Es el límite conocido del criterio: por eso los entornos
  protegidos por política siguen informándose en vez de desaparecer de la lectura.
- Los tamaños de esta tabla salen de un recorrido de ficheros que salta symlinks
  (`os.walk` + `islink`), así que difieren en torno a un 5 % de `du -B1`. La dimensión
  ya no tiene esa limitación: usa `bytes_exclusivos` de `catalogo_disco.py`, que es
  la cifra que de verdad se recuperaría.
