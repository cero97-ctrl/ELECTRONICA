# 2026-10-05 — freecad_mcp_proyecto_aplazado

## Tema
Analizar si el proyecto FreeCAD-controlado-por-LLM descrito en `docs/FreeCAD/guia-mcp-freecad.md` es implementable en este workspace, y registrar el proyecto y las trampas de entorno que quedaron anotadas.

## Contexto
- El usuario creó `docs/FreeCAD/guia-mcp-freecad.md` y preguntó si el proyecto se puede hacer aquí sustituyendo "GPT-6 Astra" por cualquier otro LLM.
- **El markdown NO es una especificación técnica**: es un resumen de un video de YouTube exportado por NotebookLM. Las 13 "referencias" apuntan todas al mismo video, y el propio archivo dice *"He generado el documento `freecad_mcp_gpt6_guide.md`"* — o sea, ni siquiera incluye ese documento, solo lo describe. Los 6 pasos son Windows-específicos (ChatGPT Desktop App, PowerShell como Administrador, `%appdata%\FreeCAD\v1.1\Mod`).
- La arquitectura real del artículo NO depende del modelo: `LLM → cliente MCP → freecad-mcp (Python) → XML-RPC 127.0.0.1:9875 → add-on dentro de FreeCAD`. El LLM solo aporta el *tool-calling loop*. El paquete upstream lo dice literalmente: *"The addon provides CAD tools; an external MCP client is still responsible for the conversation and model's tool-calling loop"*, y su README apunta a "Claude Desktop **and other MCP clients**".
- `directives/generate_freecad_script.yaml` ya declaraba esta capacidad sin cumplirla (`Status: planificado`, referencia a `execution/freecad_generate.py` inexistente). Esto no era un proyecto desde cero: era cerrar una deuda ya declarada honestamente.

### Verificación del entorno (medida, no supuesta)
| Componente | Estado |
| :--- | :--- |
| FreeCAD | **NO instalado** (ni binario, ni módulo Python, ni paquete) |
| Flatpak `org.freecad.FreeCAD` | **Sí**, 1.1.4 en flathub |
| `uvx` / `uv` | **Sí**, en `~/.local/bin/` |
| `freecad-mcp` en PyPI | **Sí**, v0.1.25, MIT, 17 tools, release 2026-09-24 |
| `elect_env` (conda) | Python **3.10.20** → incompatible con `freecad-mcp` (exige ≥3.12) |
| MCP en opencode | **Ya hay precedente**: `platformio` en `opencode.json` |
| Disco | 85% usado, 34 GB libres — FreeCAD flatpak ≈1,5 GB |
| **RAM** | **3,7 GB totales, solo 787 MB disponibles** ← bloqueo real |

- RSS culprits en el momento de la medición: `opencode` 750 MB (19,6%), Chrome ~1,5 GB agregado. zram al 100% (1,3/1,8 GB) y `/swapfile` con 492 MB en uso.
- La ruta del artículo **exige la GUI de FreeCAD viva**: los screenshots del viewport (`get_view`) y `execute_code` corren en el hilo de la GUI. FreeCAD + OCC en X11 consume ~600 MB–1 GB.

### Trampas de entorno descubiertas (evitar re-investigarlas)
1. **`freecad-mcp` NO puede instalarse en `elect_env`**: el conda env es Python 3.10.20 y el paquete exige ≥3.12. Va por `uvx`, que aprovisiona su propio intérprete. Ojo: el plugin `.opencode/plugins/conda-env.js` antepone `elect_env` al PATH, lo que altera el auto-detección de binarios.
2. **Flatpak y `execute_code_headless`**: el auto-detector busca `freecadcmd` en el PATH y el flatpak no lo pone ahí. Hay que sobrescribirlo con `freecad-mcp --freecadcmd "flatpak run --command=freecadcmd org.freecad.FreeCAD"`.
3. **Patrón MCP ya aprendido en esta máquina** (`Sessions/2026-09-26_platformio_mcp_estable.md`): apuntar al **binario absoluto pinneado**, nunca a un launcher que reinstale en cada boot. Para FreeCAD el análogo es no depender de que `uvx` resuelva el paquete durante la ventana de arranque del MCP.
4. `platformio` (MCP de terceros) **no** figura en la sección "### MCP servers" de `AGENTS.md` porque esa lista es solo para servidores propios `mcp_*_server.py`. FreeCAD no debe añadirse ahí tampoco.

## Decisiones (usuario)
1. **El proyecto FreeCAD queda APLAZADO hasta conseguir una PC con hardware más robusto.** No es "imposible": es que la GUI no cabe en la RAM actual. Decisión consciente del usuario tras conocer los números.
2. **No crear `directives/freecad_mcp.yaml`.** Sería una segunda línea de deuda para la *misma* capacidad, y `AGENTS.md` advierte exactamente de eso: dos declaraciones que divergen en silencio. Se enriquece la cabecera de la directiva existente (`generate_freecad_script.yaml`), que ya tiene el marcador honesto.
3. Registrar el aplazamiento en `AGENTS.md` → sección "Know before you act", junto a la entrada de Colab, para que la respuesta esté antes de re-investigar.

## Actividades
1. Lectura de `docs/FreeCAD/guia-mcp-freecad.md` y de `directives/generate_freecad_script.yaml` (confirmado `Status: planificado` + cabecera que ya declaraba la ausencia).
2. Comprobación del entorno: `which freecad/FreeCADCmd` (vacío), `import FreeCAD` (ModuleNotFoundError), `dpkg -l | grep freecad` (vacío), `flatpak search freecad` (1.1.4 en flathub), `which uvx uv` (presentes), `pip show mcp` (1.30.0), `python -V` (3.10.20).
3. Consulta de la documentación oficial de `freecad-mcp` en GitHub: `README`, `docs/tools.md`, `docs/installation.md`, `docs/configuration.md`, `docs/execution.md`; y metadata de PyPI vía JSON (v0.1.25, `requires_python >=3.12`, `mcp[cli]<3,>=1.28.1`).
4. Lectura de `Sessions/2026-09-26_platformio_mcp_estable.md` para recuperar el criterio de configuración MCP ya validado en esta máquina.
5. Línea base de la auditoría **antes** de tocar nada: `python3 flujo_auditar_repo.py --dimension directivas` → `con_avisos`, **exit 0**, "51 directivas, 213 referencias: 11 referencia(s) declarada(s) no implementada(s) en 9 directiva(s) con Status: planificado". El hueco de FreeCAD ya estaba contado como aviso nombrado, no como fallo.
6. `python3 flujo_auditar_sistema.py --json` ejecutado, pero **solo se capturó la cola de la salida** (dimensión `aceleracion` = ok). El veredicto formal de RAM no se leyó; los números de RAM de esta bitácora salen de `free -m` directo. No se afirma un veredicto que no se leyó.
7. Reescrita la cabecera de declaración de `directives/generate_freecad_script.yaml` (se conservan `Status: planificado` y la referencia rota, para no alterar el conteo de la auditoría).
8. Insertado el bullet de FreeCAD en `AGENTS.md` línea 36, agrupado con la entrada de hardware de Colab.
9. Verificación posterior (ver Pendientes).

**Lo que NO se hizo (deliberadamente):** no se instaló FreeCAD, no se tocó `opencode.json`, no se añadió el MCP, no se escribió en `docs/FreeCAD/`, no se alteró el resto de `AGENTS.md`.

## Pendientes
- **Al conseguir PC con hardware más robusto**, revisar en este orden:
  1. `free -m` / `python3 flujo_auditar_sistema.py`: confirmar que la GUI de FreeCAD entra sin empujar a swap. Si sigue justo, la ruta headless no necesita esperar.
  2. **Ruta A (headless, compatible con las 3 capas y la recomendada)**: `freecadcmd` sin GUI (~250 MB) + scripts deterministas en `execution/`. Encaja con `AGENTS.md` y cierra la referencia ya declarada a `execution/freecad_generate.py`. Sustituye el loop visual de screenshots por **validación geométrica programática**: volumen, bounding box, `Shape.isValid()`, intersecciones y medidas de sección con umbrales; un fallo numérico bloquea la entrega. El LLM no decide geometría: descriptor JSON de parámetros → `execution/enrutador.py` (tier por regla pura) → script que genera el `.py` de FreeCAD, ejecuta, valida y exporta STL/STEP.
  3. **Ruta B (MCP completo, fiel al artículo)**: flatpak FreeCAD + add-on `FreeCADMCP` en `~/.var/app/org.freecad.FreeCAD/data/FreeCAD/v1-1/Mod/` + `uvx freecad-mcp` + bloque `mcp.freecad` en `opencode.json` (tipo `local`, `command` absoluto, `timeout` generoso, `environment.PATH` con `elect_env/bin` primero). Da el bucle visual y `run_fem_analysis`, pero exige la GUI viva y un add-on que se instala a mano. **Usar el MCP para lo que sí es lectura** (el caso "extraer dimensiones de un modelo de referencia" de la propia nota), no para decidir la pieza.
  4. Instalar el add-on es manual (copiar `addon/FreeCADMCP` al directorio de Mod y reiniciar FreeCAD); el RPC arranca a mano o con **Auto-Start Server** (persiste en `freecad_mcp_settings.json`). El puerto por defecto es `127.0.0.1:9875`, **sin autenticación ni cifrado**: si algún día se habilitan conexiones remotas, poner token (`FREECAD_MCP_TOKEN`) o túnel SSH, porque `execute_code` ejecuta Python arbitrario con los permisos del usuario.
- **No indicado por el usuario**, por si aparece después: si el objetivo real acaba siendo solo *medir* modelos existentes, esa parte es lectura y no necesita la GUI; se podría ejecutar antes de la ruta A.