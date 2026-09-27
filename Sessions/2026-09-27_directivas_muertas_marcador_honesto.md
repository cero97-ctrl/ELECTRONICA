# 2026-09-27 — directivas_muertas_marcador_honesto

## Tema
directivas_muertas_marcador_honesto

## Contexto
- (Por qué se aborda / eventos detectados que motivan la sesión.)

## Decisiones (usuario)
1. (Acuerdos explícitos del usuario. NO inventar; si no hay, anotar qué se
   asumió y por qué.)

## Actividades
- (Qué se hizo: pasos, scripts, salidas, veredictos.)

## Hallazgo: las 12 referencias no eran deriva, eran capacidad jamas construida

`git log --all --diff-filter=D -- execution/<script>.py` vacio para los 12, y
`git log --all -- execution/db_save_memory.py execution/git_sync.py
execution/sys_maintain.py` tambien vacio. Ninguno se borro nunca: **ninguno
existio**. 10 directivas de solo capa 1, con la forma de un SOP ejecutable y nada
detras. La auditoria ya lo decia bien: "no avisa, simplemente nunca se ejecuta".

## Correccion de un error mio anterior

En la sesion previa deje escrito que "4 referencias se pueden reapuntar a
implementaciones que ya existen". **Eso era falso.** Salio de comparar NOMBRES
(`sys_maintain.py` con `flujo_diagnostico.py`: ambos de sistema), no
contratos. Leyendo los contratos, las 4 caen:

| directiva | promete | lo mas parecido | por que no |
| --- | --- | --- | --- |
| get_github_repo_contents | clonar + arbol | `extraer_repo_github.py` | concatena texto por relevancia para repo->skill; no emite arbol |
| git_update | SemVer + JSON | `update_repo.sh` | 0 menciones de version/semver/bump |
| system_maintenance | purgar RAM/ZRAM/disco + BD | `flujo_diagnostico.py` | solo mide y genera LaTeX; no purga nada |
| generate_kicad_pcb_script | PCB + Gerbers | `generar_kicad_sch.py` | esquematico, no PCB |

Ademas, las 4 de memoria apuntan a ChromaDB, que SI existe (81M, rag_system.py):
la capa de datos esta, los 4 CLI y su orquestador no. Y `generar_kicad_sch.py` /
`generar_kicad_llm.py` son esquematico, lo que hace el caso de PCB mas
claramente unimplementado de lo que parecia.

Leccion: reapuntar por topicidad es la forma de mentir sin querer. Hay que leer
el contrato del script destino, no su nombre. Es el 6o error de medicion de la
sesion y todos tienen la misma causa: leer el sitio equivocado en vez de la
fuente.

## Decision del usuario

"Marcador honesto + arreglar git_update". Descartadas: implementar las 8
capacidades (dias de trabajo, y nadie las ha pedido) y retirarlas (se pierde el
conocimiento del SOP).

## Lo hecho

1. **`Status: planificado` en 9 directivas**, cada una con la razon concreta de
   lo que falta. `git_update.yaml` se reescribio aparte.
2. **`git_update.yaml` al contrato real de `update_repo.sh`**, leido linea a
   linea. Lo encontrado al reescribir:
   - `git pull --rebase`, no merge. El conflicto sale con codigo 3 y NO stagea.
   - `DRY_RUN=false`: `--dry-run` es opt-in, no el default (yo lo habia escrito
     al reves en el primer borrador).
   - `git add -A` sin filtro: stagea los 28 untracked ajenos. Riesgo real, queda
     como edge case con la recomendacion de `--confirm`.
   - `push` solo con `--push`: por defecto el remoto no se toca.
   SemVer y el JSON pasan a `No_implementado`, no a capacidad. El nombre del
   script muerto se cita SIN el prefijo `execution/` a proposito: el regex busca
   la forma literal en todo el texto.
3. **`comprobar_directivas` distingue la trampa del hueco declarado**:
   - rota en `activo` -> `fallo` (sin cambio)
   - rota en `planificado` -> `aviso`, nombrada
   - `planificado` que todo resuelve -> `aviso` (marcador obsoleto)
   - `Status` fuera de vocabulario -> `marcadores_invalidos`, se trata como
     `activo`
   - `planificado` **nunca** da `ok`

   Resultado: 12 -> 0 silenciosas + 11 declaradas. Dimension `aviso`, veredicto
   global sigue `con_fallos` por disco.

   El texto se escanea entero, comentarios incluidos, a proposito: comentar un
   paso no puede ser una forma de pasar. Mi propio comentario en
   `git_update.yaml` disparo un `fallo` y la solucion fue reformular el
   comentario, no relajar el regex.

4. **Tests 112 -> 123.** Incluyen que `planificado` nunca da `ok`, el obsoleto, el
   `Status` inventado, y que una referencia solo mencionada en un comentario
   cuenta.

## Pendientes
- (Qué queda abierto; pendientes acordados de otras sesiones que NO se tocaron.)
