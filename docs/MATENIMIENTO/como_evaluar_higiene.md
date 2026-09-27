# Como evaluar la higiene del repositorio (procedimiento reproducible)

Documento normativo. Describe, paso a paso, como se construyo y se mantiene
`flujo_auditar_repo.py`, de forma que cualquier LLM (o persona) pueda
reconstruirlo y reproducir sus resultados sin contexto previo.

- **Alcance:** higiene del **repositorio**. La higiene del **sistema** (RAM, CPU,
  servicios) no tiene ningun flujo con veredicto; ver la seccion 11.
- **Implementacion de referencia:** `flujo_auditar_repo.py` (capa 2),
  `execution/auditar_repo.py` (capa 3), `directives/auditar_repo.yaml` (capa 1).
- **Diagrama:** `docs/AGENTE_IA/auditar_repo_flujo.pdf` (5 paginas).
- **Origen:** 2026-09-27. Corregido dos veces el mismo dia (contrato del CLI y
  un falso "0 MB" en la dimension de disco).

---

## 1. La regla que gobierna todo lo demas

**Gana el peor estado. Nunca el promedio.**

Estado de cada dimension: `ok` > `aviso` > `fallo` > `no_verificado`, con esta
precedencia (un estado peor siempre gana):

| Estado | Significado | Bloquea el verde |
| --- | --- | --- |
| `ok` | Medido y correcto | no |
| `aviso` | Medido, con accion pendiente | no |
| `fallo` | Medido y esta mal | **si** |
| `no_verificado` | **No se pudo medir** | **si** |

Por que existe, con el caso que la motivo: el repo tenia 12 dimensiones sanas
sobre 13, y una de ellas era el disco al 91 %. Un promedio daria 0.92 y el
flujo saldria "limpio". El promedio esconde exactamente lo que hay que arreglar.

Consecuencia practica: **`no_verificado` es un veredicto de primera clase**, no
un "no me importa". Si una dimension no se pudo comprobar, el conjunto entero no
puede declararse limpio. Es la diferencia entre un repositorio sano y uno que
nadie ha mirado.

---

## 2. Arquitectura obligatoria de tres capas

Un evaluador de higiene **no** es un script suelto. Segun `AGENTS.md`:

| Capa | Fichero | Responsabilidad |
| --- | --- | --- |
| 1. Directiva | `directives/<nombre>.yaml` | Que hacer (SOP, entradas, pasos, outputs, casos limite) |
| 2. Orquestacion | `flujo_<nombre>.py` (raiz) | Decision, validacion, composicion, timeouts, veredicto |
| 3. Ejecucion | `execution/<nombre>.py` | Trabajo determinista de una sola responsabilidad |

Si falta una capa, no es un flujo del proyecto: es un script suelto que otro
agente no sabra ni encontrar ni confiar.

Todos los scripts se ejecutan **desde la raiz del repo** (los imports usan rutas
relativas). Los flujos `flujo_*.py` viven en la raiz, NO en `execution/`.

---

## 3. Procedimiento, paso a paso

### Paso 0 — Orientarse antes de actuar

```bash
python3 execution/estado_sesion.py check   # frescura de las vistas de corrida
ls -t Sessions/ | head -3                  # que se decidio en sesiones previas
```

Lee `AGENTS.md` y la directiva del flujo antes de escribir nada. Si el trabajo
toca LaTeX, lee tambien `.agent/latex.md`; si toca scripts que parsean JSON de
un LLM, `.agent/python.md`.

### Paso 1 — Inventariar los verificadores que YA existen (reutilizar antes de construir)

Este paso es el que evita duplicar trabajo y es el que motivo el flujo entero: el
repositorio tenia 13 verificadores parciales independientes y **ningun
compositor**. Cada uno era correcto en su ambito y todos podian salir en verde
mientras el repositorio estaba peor de lo que ninguno miraba.

```bash
python3 flujo_auditar_repo.py --json > /dev/null   # si ya existe, no se construye
grep -l "checks\|veredicto" execution/*.py          # buscar candidatos
```

El caso concreto que lo demuestra: `.tmp/run_state.json` era JSON valido pero sin `run_id`, y
`estado_sesion.py` lo clasificaba como corrupto. Nadie lo habia visto, porque
cada verificador miraba su propio trozo. **Un compositor encuentra fallos que
ningun componente individual puede ver.**

### Paso 2 — Decidir las dimensiones

Dos fuentes:

- **Reutilizadas** (`DIMENSIONES_REUTILIZADAS` en el orquestador): verificadores
  que ya existen y se invocan como subproceso. Cada uno necesita su
  **intérprete** (seccion 4).
- **Nuevas** (`DIMENSIONES_NUEVAS` en `execution/auditar_repo.py`): lo que
  ningun verificador cubre. Cada nueva debe justificarse por escrito con
  `por_que_nueva`; si no se puede escribir esa frase, probablemente sobra.

Las 7 nuevas que existen, y por que ninguna estaba cubierta:

| Dimension | Que mide | Por que es nueva |
| --- | --- | --- |
| `secretos` | Claves de proveedor, tokens y claves privadas en texto propio del repo | Un `.env` trackeado se filtra al hacer push y ningun verificador lo detecta |
| `logs` | Cadena de hashes de cada `.tmp/session_log_*.jsonl` | Un log append-only truncado rompe la trazabilidad en silencio |
| `directivas` | Scripts de `execution/` que las directivas invocan y no existen, separando **trampa silenciosa** de **hueco declarado** (`Status: planificado`), y avisando de marcadores obsoletos | Una directiva que apunta a un script borrado **nunca se ejecuta y no avisa** |
| `capas` | Flujos `flujo_*.py` que no nombran ningun script real de `execution/` | Un flujo que hace todo en el chat no es determinista, y nada lo delata |
| `peso_git` | MB trackeados, ficheros >= 5 MB, carpetas que no deben estar en el indice | GitHub no avisa por email: el push falla al final, cuando ya se hizo el trabajo |
| `untracked` | Ficheros sin trackear (aviso en 20) | Es la forma mas comun de perder trabajo: un `git add .` se lleva lo de otra sesion |
| `pdf_stale` | PDF cuyo `.tex` es mas reciente | El PDF es lo que lee el usuario final; un `.tex` bonito con un PDF viejo no comunica nada |

Umbrales de `peso_git`: aviso **50 MB**, bloqueo **100 MB** (los de GitHub).
Carpetas que nunca deben trackearse: `.pio`, `.venv`, `__pycache__`,
`node_modules`, `venv`.

### Paso 3 — Escribir la capa 3 (`execution/auditar_repo.py`)

Cada comprobacion es una funcion pura `raiz -> dict` con esta forma exacta:

```python
{
  "dimension": "<nombre>",
  "estado": "ok" | "aviso" | "fallo" | "no_verificado",
  "resumen": "<una linea legible>",
  "evidencia": { ... datos contables ... },
  "accion": "<que hacer, y por que>",   # obligatoria si estado != "ok"
}
```

Reglas de la capa 3:

- **Solo lectura.** Nada de borrar, de tocar el indice de git ni de reescribir
  historia. Si una comprobacion necesita permiso de escritura, no es una
  dimension de auditoria.
- **Devuelve contables, no veredictos vagos.** `secretos` devuelve cuantos
  ficheros inspecciono y cuantos descartó; quien decide el estado es el
  orquestador.
- **Excluye el codigo de terceros.** `node_modules`, `.pio`, `miniflare` y
  `.git` quedan fuera. Un detector que solo sabe decir "algo hay" acaba
  ignorandose.
- Instrumenta con el envoltorio `_cronometrar` para que cada dimension exponga
  `duracion_s` (ver seccion 7).
- Registrala en `DIMENSIONES_NUEVAS`.

### Paso 4 — Escribir la capa 2 (`flujo_auditar_repo.py`)

- Tabla `DIMENSIONES_REUTILIZADAS` con `nombre`, `descripcion`, `script`, `args`,
  `timeout`, `lenta` e `interpreta` **por dimension**.
- `clasificar_salud(dimensiones)`: **funcion pura**, sin ficheros, sin git, sin
  red. Es la parte que mas dano haria si se rompiera en silencio, asi que es la
  que mas se testea.
- Un timeout por dimension, y `no_verificado` si se agota.
- Un interprete que lance excepcion **no tumba el flujo**: se captura y la
  dimension queda `no_verificado` nombrando al interprete culpable.

Verifica **trazabilidad**: escribe `flujo/inicio` y `flujo/fin` con
`execution/sesion_log.py add`, y escribe `.tmp/run_state.json` **con `run_id`**.
Sin `run_id`, `estado_sesion.py` clasifica la vista como corrupta y el propio
flujo aparece como su propio hallazgo.

### Paso 5 — Escribir la capa 1 (`directives/auditar_repo.yaml`)

Secciones obligatorias: `goal`, `required_inputs`, `dimensions` (con `que_mide` y
`por_que_nueva` por dimension), `steps` (cada uno con `script`), `expected_outputs`,
`codigos_de_salida`, `edge_cases` e `invariantes`.

Los `edge_cases` no son teoria: cada uno documenta un fallo **real** que ocurrio
mientras se construia. Ver seccion 6.

### Paso 6 — Tests

Regla: **el nucleo (`clasificar_salud`) se testea como funcion pura**, y cada
comprobacion de capa 3 se prueba sobre un repo minimo construido en un
`temporarydir`. Hoy son 123 aserciones.

```bash
python3 execution/test_auditar_repo.py
```

**Y el interprete se testea con la forma REAL de salida del script**, jamas con
un fixture inventado a mano. Ver seccion 5, que es el error mas importante que
se cometio aqui.

### Paso 7 — Autoauditoria: deja que el flujo se mida a si mismo

Ejecutalo entero. Es de solo lectura, asi que corre sin miedo:

```bash
python3 flujo_auditar_repo.py
```

La primera pasada completa encontro **dos fallos en su propio test nuevo**:

- un caracter CJK en un comentario, que cazó la dimension `texto`;
- un header de clave PEM literal usado como fixture, que cazó `secretos`.

Un evaluador que no se pasa a si mismo primero no tiene derecho a opinar sobre
los demas.

### Paso 8 — Diagrama de flujo (ISO 5807, determinista)

```bash
python3 execution/generar_diagrama_flujo.py \
    --descriptor .tmp/descriptor_<proceso>.json \
    --output docs/<tema>/<proceso>_flujo
```

El descriptor modela nodos (terminador/proceso/decision/almacenamiento/entrada-
salida/documento/nota) y conexiones con `col`/`fila`. **Cada simbolo muestra
solo su etiqueta** (T/P/D/E/A/N + numero = id del nodo) y las conexiones llevan
rotulos cortos; el significado completo vive en la tabla *Leyenda de etiquetas*
bajo el diagrama. Los iconos deben existir en `fontawesome5`
(`clipboard-check`, `gavel`, `shield-alt` confirmados; `magnifying-glass` **no
existe**).

Valida que el generador devuelva `errores: []` y `solapes_total: 0`. Un PDF
publicado con errores de compilacion no es un entregable.

### Paso 9 — Commit selectivo y bitacora

```bash
python3 execution/bitacoras.py nueva --tema "<tema>"   # bitacora canonica
python3 execution/bitacoras.py check                   # al cerrar la sesion
git add <ficheros explicitos, uno a uno>               # NUNCA `git add .`
```

Nunca `git add .`: el repositorio arrastra trabajo de otras sesiones y un add
masivo se lo lleva. Al commit, cuerpo con el **por que** de cada decision, no el
que.

### Regla asociada — la dimension `directivas` y la declaracion honesta

La dimension `directivas` caza scripts de `execution/` que las directivas invocan
y no existen. El caso grave no es que falte el script: es que **la directiva no
avise**. Una directiva con la forma de un SOP ejecutable (pasos, entradas,
salidas esperadas, edge cases) y nada detras es peor que no tener directiva,
porque invita a alguien a intentarlo.

La distincion que hace falta:

| Que dice la directiva | Que pasa | Gravedad |
| --- | --- | --- |
| nada (o `Status: activo`) | el lector cree que funciona | `fallo`: trampa silenciosa |
| `Status: planificado` | el lector sabe que no existe | `aviso`: hueco declarado y contado |
| `Status: planificado` pero todo resuelve | el marcador esta obsoleto | `aviso`: miente al reves |

`planificado` **nunca** produce `ok`. Baja la gravedad porque el hueco ya es
visible para quien lee la directiva, no porque dejara de existir: sigue contado en
`referencias_declaradas_no_implementadas` y nombrado en la accion.

Cuatro guardas, porque un marcador de estado es un escondite facil:

1. **Vocabulario cerrado** `{activo, planificado}`. Un valor inventado se
   reporta en `marcadores_invalidos` y se trata como `activo`, que es el default
   conservador: **ausente = `activo`**, asi que no declarar nunca oculta nada.
2. **Marcador obsoleto detectable**: un `planificado` cuyas referencias si
   resuelven se reporta, porque entonces la directiva miente en sentido
   contrario.
3. **Se escanea el texto entero, comentarios incluidos.** Comentar un paso no
   puede ser una forma de pasar la comprobacion.
4. **`git log` para el diagnostico, no el nombre del fichero.** Saber si un
   script se borro o nunca existio (`git log --diff-filter=D -- <ruta>`) es la
   unica forma de distinguir deriva de capacidad jamas construida, y las dos
  y las dos acciones correctas son distintas.

Y la regla de decision que evita el error por defecto: **no todos los huecos se
implementan**. 8 capacidades sin pedir (CLI de memoria, busqueda web, FreeCAD,
KiCad PCB) se declaran; construirlas todas cuesta dias y anade superficie que
nadie mantiene. Implementar de mas no es rigor, es trabajo que nadie pidio.

Tampoco al reves: una directiva que apunta a un script **real** y promete cosas
que ese script no hace (versionado semantico que no existe, JSON que no se
emite) es la forma mas danosa de esta dimension, porque el script funciona y la
directiva miente sobre el.

---

## 4. Contrato de los interpretes (la parte que mas falla)

Un interprete traduce la salida de un verificador al vocabulario
`ok/aviso/fallo/no_verificado`.

**No existe contrato uniforme entre los verificadores.** Esta es la fuente de
los errores mas caros. Formas reales capturadas de cada script:

| Dimension | Script | Clave que usa | Forma REAL |
| --- | --- | --- | --- |
| `texto` | `execution/verificar_texto.py` | codigo de salida | texto plano; `0` limpio, `1` hallazgos, `2` sin verificar |
| `estado_sesion` | `execution/estado_sesion.py check` | `checks` | **lista** de objetos `{archivo, run_id, veredicto, razon, corrida}` |
| `bitacoras` | `execution/bitacoras.py check` | `bitacoras`, `accionables` | `bitacoras` es una **lista**; `accionables` es un **entero** |
| `disco` | `execution/disco_medir.py` | `filesystem`, `resumen_catalogo` | `filesystem.uso_pct`; los bytes viven en `resumen_catalogo.reclaimable_por_tier.seguro.bytes` |
| `barrera_disco` | `execution/test_barrera_disco.py` | texto | linea `Aserciones OK: N   Fallos: M` |
| `test_texto` | `execution/test_verificar_texto.py` | texto | linea `Aserciones OK: N   Fallos: M` |

Vocabulario de `estado_sesion` (mapear **por veredicto**, no por contador):

| Veredicto | Significado | Como se trata |
| --- | --- | --- |
| `ok` | La vista casa con su log append-only | ok |
| `huerfano` | La corrida termino; la vista sobrevivio | aviso (mantenimiento) |
| `corrupto` | JSON invalido o sin `run_id` | **fallo** |
| `no_verificable` | Sin log append-only; no se puede juzgar | aviso |

Solo `corrupto` es fallo. `estado_sesion.py` mete `huerfano` y `corrupto` en la
misma bolsa y lo publica como `anomalias`: contar esa cifra trataria como fallo
de integridad a una vista simplemente pendiente de purgar.

Reglas para todo interprete:

1. **Timeout primero.** Si se agota el timeout, `no_verificado`.
2. **Salida que no se reconoce, `no_verificado`.** Si falta la clave esperada o
   el JSON no parsea, la dimension queda sin verificar **y nombrando el
   motivo**. Nunca la convierte por defecto en `ok`.
3. **Un estado fuera del vocabulario degrada a `no_verificado`**, y nombra la
   dimension. Un `if` mal anidado que deja caer el valor devolvia `limpio`: una
   errata en una cadena producia un "repositorio sano".
4. **La accion va con su consecuencia.** "Purgar vistas huerfanas: es
   regenerable y no se pierde nada real" es accion. "Revisar" no lo es.

---

## 5. El error mas importante: un fixture inventado no prueba el contrato

Este fallo ocurrio y casi pasa, asi que va destacado.

`_interpreta_disco` leia `datos.get("recuperable")`, **clave que `disco_medir.py`
nunca ha emitido**. Los bytes vivian en
`resumen_catalogo.reclaimable_por_tier.seguro.bytes`. Como la clave no existia y
el codigo hacia `or 0`, el informe afirmaba:

```
disco al 91.3% (20.38 GB libres); 0 MB recuperables con borrado seguro
```

Un **0 afirmado como dato medido**, cuando en realidad era una clave ausente. Y
si hubiera habido 8 GB realmente recuperables, tambien habria dicho 0.

Porque los tests pasaban. Los tests de disco usaban fixtures escritos a mano:

```python
FA._interpreta_disco(0, json.dumps({"filesystem": {"uso_pct": 91.3, "libre_gb": 20}}), False)
```

Ese fixture omite `resumen_catalogo` por completo, asi que **la rama del
recuperable nunca se ejecutaba**. Los tests demostraban que los umbrales
funcionaban y no decían absolutamente nada del numero.

Dos reglas que salen de ahi:

1. **Fixture con la forma real, capturada del script.** No de memoria. Si no
   puedes pegar la salida real, el contrato no esta verificado.
2. **La ausencia de dato no se rellena con un default.** `or 0` convierte "no
   lo sé" en "cero", y "cero" es un hecho. Si la clave no viene, el resumen
   declara la laguna:

   ```
   disco al 91.3% (20.35 GB libres); 16.1 MB recuperables con borrado seguro
   disco al 91.3% (20.35 GB libres); recuperable no informado por disco_medir.py
   ```

   El estado de la dimension lo decide `uso_pct` en ambos casos; lo que cambia es
   si el informe **afirma** una cifra o la declara ausente.

---

## 6. Trampas reales, con la evidencia

Cada una ocurrio durante la construccion. Están tambien en la directiva.

| Trampa | Sintoma | Regla |
| --- | --- | --- |
| `RAIZ` un nivel arriba | El flujo no encuentra sus scripts | Los `flujo_*.py` viven en la raiz; no copiar el patron de uno que vive en `execution/` |
| Interprete que asume la forma equivocada | La dimension siempre `no_verificado` | Probar el interprete con la salida real del script, no con la imaginada |
| `huerfano` contado como `corrupto` | Un fallo de mantenimiento se reporta como integridad rota | Mapear por veredicto, no por contador agregado |
| Estado fuera del vocabulario | El clasificador devuelve `limpio` | Degradar a `no_verificado` y nombrar la dimension |
| Deteccion de capa 3 por forma de ruta | 13 falsos positivos en flujos que si delegan | Intersectar el **nombre** del script con los ficheros reales de `execution/` |
| Escaneo de secretos en codigo vendorizado | Falsos positivos en `workerd` / `miniflare` | Excluir por prefijo las carpetas de codigo ajeno |
| Fixture inventado (seccion 5) | El informe afirma un `0` que nadie midio | Fixture desde la salida real; la ausencia se declara |
| Interprete sin clave `accion` | La dimension mas grave no sale de "Que hacer" | Toda dimension con estado distinto de `ok` devuelve accion |
| Cifra sin declarar su ambito | "16.1 MB recuperables" se lee como "el disco esta bien" | Decir que es lo unico que el flujo *puede* borrar, no lo que el disco *puede* liberar |
| Marcador de estado como escondite | Marcar todo `planificado` y la dimension se pone verde | Vocabulario cerrado, ausente = `activo`, obsoletos se reportan, nunca `ok` |
| Reescribir un nombre por topicidad | `sys_maintain.py` -> `flujo_diagnostico.py` porque "ambos son de sistema" | Leer el contrato del script destino antes de reapuntar |
| `PROGRAMA` con palabra inglesa pegada | "y no se **knew** antes" | El verificador de texto busca CJK, mojibake y `camelCase`; **no** detecta code-switching en comentarios |
| Icono inexistente en el diagrama | `! Package fontawesome5 Error: ... was not` | Probar cada icono; el generador puede publicar un PDF con errores |

Ultima fila, con detalle: el verificador de texto **solo mira prosa**
(caracteres intrusos, cadenas conocidas, `camelCase` opt-in). Una palabra
inglesa pegada en un comentario en castellano es invisible para el y para la
auditoria. Es un hueco de cobertura conocido, no un fallo del verificador.

---

## 7. Codigos de salida

| Codigo | Significado |
| --- | --- |
| `0` | Todas las dimensiones medidas, sin fallos (puede haber avisos, y se listan) |
| `1` | Al menos una dimension en `fallo` |
| `2` | Al menos una dimension en `no_verificado`. **Reservado** para esto |
| `3` | Uso incorrecto: flag desconocido, valor mal formado o dimension inexistente |

`argparse` devuelve `2` por defecto, y aqui `2` significa "no verificado", asi
que se remapea a `3` con una subclase:

```python
class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(3)
```

Sin esto, escribir mal un flag se reporta como una dimension que no se pudo
comprobar: una lectura falsa que invita a reintentar la medicion cuando el
problema era el comando.

Aplica a las dos capas, incluida la raiz invalida de capa 3, que tambien
devolvia `2`.

**El flag de dimension se acepta en dos formas equivalentes, y se unen:**

```bash
python3 flujo_auditar_repo.py --dimension texto --dimension disco
python3 flujo_auditar_repo.py --solo texto,disco
python3 flujo_auditar_repo.py --dimension texto --solo disco   # restringe a las dos
```

---

## 8. Rendimiento: medir antes de prometer

Mediana de 3 corridas en esta maquina (Celeron N4020, 2 nucleos):

| Modo | Tiempo |
| --- | --- |
| Completa (13 dimensiones) | **43,5 s** |
| `--rapido` (10 dimensiones) | **24,6 s** |

`--rapido` omite `texto`, `barrera_disco` y `test_texto` (15,9 s de 43,5 s, un
36,6 %). **No equivale a la pasada completa** y el codigo de salida puede
diferir: no usarlo como sustituto en un gate.

Reparto del costo: `disco` 23,1 %, `texto` 22,6 %, `secretos` 18,8 %, `logs`
15,4 %, `test_texto` 11,7 %, `barrera_disco` 3,0 %.

**Advertencia:** la varianza es enorme. `disco` tardo 10 s en unas corridas y
36 s en otra (total 63,6 s). Estas cifras son medianas, **no garantias**: no
usarlas como timeout.

Como la instrumentacion por dimension no existia, la primera conclusion sobre
`--rapido` fue falsa (una sola medicion dio 41 s con el flag contra 39 s sin el,
lo que hacia pensar que era inutil). Se conservo el flag, pero porque la mediana
de tres mostro un ahorro real del 43 %, no porque la intuicion lo dijera.

---

## 9. Verificacion antes de entregar

```bash
python3 -m py_compile flujo_auditar_repo.py execution/auditar_repo.py
python3 execution/test_auditar_repo.py        # 123 aserciones
python3 execution/test_barrera_disco.py       # 88
python3 execution/test_verificar_texto.py     # 22
python3 execution/verificar_texto.py AGENTS.md directives/auditar_repo.yaml
python3 -c "import yaml;yaml.safe_load(open('directives/auditar_repo.yaml'))"
python3 flujo_auditar_repo.py                  # exit 1 si hay fallos reales
python3 flujo_auditar_repo.py --flag-malo; echo $?   # debe ser 3
python3 execution/bitacoras.py check
git diff --check
git status --porcelain                       # revisar untracked ajeno
```

Lo que de verdad importa: **el veredicto del repo actual no debe cambiar** al
tocar el CLI ni los interpretes. Si los tests pasan pero el veredicto se mueve,
el cambio esta mal.

Y el generador de diagramas, que es quien mas tranco ha dado:

```bash
python3 execution/generar_diagrama_flujo.py --descriptor .tmp/descriptor_<x>.json \
    --output docs/<tema>/<x>_flujo
# debe imprimir: "status": "ok", errores [], solapes_total 0
```

---

## 10. Restricciones que no se negocian

- **Solo lectura.** Escribe unicamente en `.tmp/` (tres salidas: informe,
  `run_state.json` y su log). No borra, no toca el indice de git, no reescribe
  historia, no pide `--yes`, no usa sudo. Por eso puede correr sin miedo.
- **Determinista.** Sin red y sin LLM. El mismo repo produce el mismo veredicto.
- **Sin repair automatico.** Lo que encuentra se reporta con su accion y su
  consecuencia. Arreglarlo es decision del operador.
- **Idempotente.** Correrlo dos veces no cambia nada mas que su timestamp.
- **Cubierto automaticamente por el verificador de texto:** evita caracteres CJK o Hangul,
  mojibake y palabras fusionadas en toda la prosa, incluidos los `.md` que
  escribas.

---

## 11. Lo que este procedimiento NO cubre

- **Higiene del sistema (RAM, CPU, servicios):** no hay ningun flujo con
  veredicto. `flujo_diagnostico.py` genera un PDF con RAM, CPU y uptime pero
  **sin codigo de salida**: no se puede usar como gate. `flujo_disco.py` es de
  mantenimiento (medir, purgar la whitelist, verificar), no un evaluador de
  salud. La unica dimension de nivel sistema dentro de la auditoria del repo es
  `disco`.
- **El alcance de la dimension `disco` es la whitelist, no el disco.** Medido el
  2026-09-27: `du` ve 124 GB de los 201 GB que declara `df`, y **43,6 GB de esa
  diferencia son imagenes de Docker en `/var/lib/docker`** (96 % recuperables
  segun `docker system df`; 3 contenedores parados hace 7 meses). Es el 22 % de
  todo lo que ocupa el disco, y las 27 entradas de `catalogo_disco.py` no pueden
  alcanzarlo. No es un descuido: la barrera existe para que el flujo nunca toque
  rutas del sistema, y esa decision tiene esta consecuencia. Pero significa que
  "no hay nada recuperable" quiere decir "no hay nada recuperable **dentro del
  proyecto**", y el resumen de la dimension lo dice ahora explicitamente para
  que no se lea como "el disco esta cuidado". Los ~33 GB restantes (Waydroid,
  containerd) solo se pueden medir con `sudo du -xsh /var/lib/* | sort -rh`.
- **Capa 1 completa:** no se verifica que cada flujo tenga su directiva. El
  mapeo flujo-directiva no es 1:1 y solo 4 de 20 flujos declaran `orchestrator:`.
  Se reporta como no verificable en vez de inventar una regla que no se sostiene.
- **Code-switching** (palabras inglesas dentro de prosa o comentarios en
  castellano): lo detecta a mano una revision, no el verificador automatico.

Para cerrar el hueco de sistema, el procedimiento es exactamente este documento:
tres capas, mismas reglas de veredicto, un interprete por script y fixtures
tomados de la salida real.

---

## 12. Resumen ejecutable

```bash
# La respuesta corta a "que flujo corro para evaluar la higiene":
python3 flujo_auditar_repo.py

# Veredicto rapido sin las 3 dimensiones lentas (no es equivalente):
python3 flujo_auditar_repo.py --rapido

# Solo una dimension, para depurar:
python3 flujo_auditar_repo.py --dimension disco

# Informes legibles por maquina:
python3 flujo_auditar_repo.py --json

# Interpretacion de las salidas: 0 limpio/con avisos, 1 con fallos,
# 2 sin verificar (nunca verde), 3 uso incorrecto.
```
