# 2026-09-26 — mantenimiento_disco

## Tema
mantenimiento_disco

## Contexto
- El workspace estaba en 15.11 GB libres (93.5% de uso) y había crecimiento sostenido. Objetivo de la sesión: un sistema *determinista y seguro* de mantenimiento de espacio, no un `rm -rf` puntual.
- Requisito explícito del usuario: **nunca** borrar fuera de una whitelist; los targets sensibles (herramientas, datos, agentes) se listan y **no** se purgan solos.
- Barrera anti-borrado: 4 validaciones (`raíz permitida`, `no protegido`, `sin symlink`, `dentro del catálogo`) revalidadas **por entrada**, no solo por target.
- Tiers: `seguro` (17), `recargable` (7), `pesado` (2). Sin `--yes` el flujo **solo simula**; nunca `sudo`; nunca autoescala de tier.

## Decisiones (usuario)
1. `~/.arduino15/staging` = seguro (paquetes de toolchain re-descargables); `~/.arduino15/packages` = recargable.
2. `~/.npm-global` = protegido (contiene `platformio-mcp`, `pio-agent`, `anchor`); `npm-cacache`/`npm-npx` sí son purgable.
3. measure-only debe distinguir `medido` de `reclaimable`: la guarda de antigüedad no se informa como espacio disponible.
4. El diagrama de flujo es **obligatorio** (convención ISO 5807) y debe compilar sin solapes.
5. Purgar de más era el riesgo principal → primero la barrera + tests, después medir, y solo al final purgar.

## Actividades
- Creadas las 3 capas: `directives/mantenimiento_disco.yaml`, `flujo_disco.py`, `execution/{catalogo_disco,disco_medir,disco_purgar,test_barrera_disco}.py`.
- **Capa de ejecución (barrera):** `validar_destino()` es la única puerta de borrado; `_esta_en_catalogo` acepta subárboles solo en modos `contenido`/`glob`/`rotar` (el contenedor no se borra nunca, sus hijos sí, uno a uno).
- `contenedor_de(t)` como fuente única de resolución: un `glob` puede no llevar comodín en `ruta` (tenía `patron` aparte), y buscar `*` a mano medía el directorio equivocado (2.1 GB falsos en `pycache-repo` → 73.6 MB reales).
- `du_mayores`/`du_hijos`/`hay_entradas_recientes` usan `find -printf` y parsean stdout **aunque `find` devuelva !=0** (código 1 = denegados en directorios protegidos, los resultados parciales son válidos).
- **Purga real autorizada (tier seguro): 1.72 GB / 449 entradas** — `arduino-staging` 1580.4 MB (2), `uv-cache` 88.3 MB (1), `arduino-cache` 65.3 MB (2), `mesa-shaders-db` 23.7 MB (52), `tmp-latex` 3.1 MB (33), `trash-info` 1.4 MB (356).
- Al volver a pasar el orquestador: 16 targets `omitido` (`conservado_reciente`, `no_existe`) → **0 bytes liberados**. Idempotente.
- Corregidos 3 defectos encontrados al revisar el código antes de commitear:
  1. `disco_purgar._purgar_nativo` pasaba `t.cmd` (string) a `subprocess.run` con `shell=False` → `FileNotFoundError`; ahora `shlex.split(t.cmd)`.
  2. La rama nativa se ejecutaba **antes** de la guarda de antigüedad y sin `validar_destino`; ahora pasa por ambas (mismas barreras que el resto).
  3. `disco_medir` validaba el **contenedor** como destino, así que los targets `contenido`/`glob`/`rotar` daban `0 B` purgables (`raiz_no_permitida` en el repo, `no_existe` en el comodín). Ahora la unidad borrable depende del modo (`contenedor` vs `entradas`) y la capa de purga es quien aplica la barrera entrada por entrada.
- **Tests de barrera: 81 → 87 aserciones, 0 fallos.** Hallazgo importante: los negativos del test eran **vacuous** — literals `~.ssh` en vez de `~/.ssh`; `expanduser()` solo expande `~` seguido de `/`, así que llegaban a `validar_destino` como rutas relativas y pasaban solo por la alternativa `no_existe`. Corregidos y afinados con anclas `^` (el test ahora valida el *motivo* exacto: `protegido_exacto`, `es_symlink`, `fuera_de_catalogo`).
- Añadida regresión del modo nativo (no había ningún target nativo en el catálogo, luego la rama estaba sin cubrir): con target sintético en `/tmp` + canario `touch` se prueba que la guarda de antigüedad bloquea, que `--dry-run` no ejecuta y que la ejecución real funciona.
- **Diagrama:** el solape `No`/`Si` no era del descriptor sino del **generador**: la etiqueta se ponía *al final* del path, así que dos aristas que convergen en un mismo nodo apilaban sus rótulos. Arreglo en `generar_diagrama_flujo.py` (`pos=0.5`, etiqueta al centro de la arista) + rediseño del descriptor sin aristas que salten filas ni puntos de convergencia → **0 solapes, 0 errores, 0 overfull**. Verificados los otros 2 diagramas existentes (motor_fallback, sync_faq) con el generador modificado: siguen en 0.
- Registrado el flujo en `AGENTS.md` (Commands, Output conventions y comando de test).

## Pendientes
- `~/.arduino15/packages` (5.5 GB) y los targets `recargable` siguen sin purgar: requieren que el operador elija el tier explícitamente.
- Los 2 targets `pesado` (modelos IA ~972 MB) igual: nunca se purgan solos.
- 2 rutas requieren `sudo` (pistas reportadas, nunca tocadas): si el operador las autoriza, habría que hacerlo por fuera del flujo.
- El `max_tokens`/saldo de OpenRouter no se tocó en esta sesión (ajeno al tema).
- **PENDIENTE PARA LA PRÓXIMA SESIÓN (acordado con el usuario):** añadir `~/anaconda3/pkgs` (11 GB de caché de paquetes conda) al catálogo como target `nativo` con `cmd="conda clean --all"`, tier `recargable`, más su aserción en `execution/test_barrera_disco.py`. **No se ejecutará nada sin que el usuario lo pida** con `--tier recargable --yes`. Motivo: el catálogo excluye `anaconda3` a propósito (borrar un `.so` de site-packages deja el entorno roto y conda no lo re-instala), pero la caché de `pkgs` SÍ es regenerable y tiene su herramienta oficial. Candidatos relacionados: `conda env remove IA` (2,2 GB, solo si el usuario confirma que no lo usa) y `libtensorflow_cc.so.2` de 973 MB en el base env (NO tocar: paquete instalado, no caché).
- 3 copias de TensorFlow detectadas en el escaneo profundo: base py3.13 (973 MB), `envs/IA` py3.11 (584 MB) y `pkgs` (584 MB).
- **Opcional:** los PDFs de `docs/AGENTE_IA/{faq_higiene_estado_sesion,motor_fallback,sync_faq_flujo}_flujo.pdf` siguen siendo los generados con la versión antigua del generador; la próxima vez que se regeneren ya saldrán con la etiqueta al centro (verificado: 0 solapes).
