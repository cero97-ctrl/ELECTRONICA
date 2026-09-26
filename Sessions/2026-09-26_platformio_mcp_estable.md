# 2026-09-26 — platformio_mcp_estable

## Tema
Estabilizar el servidor MCP `platformio` (PlatformIO) que venía fallando al arrancar opencode.

## Contexto
- El usuario reporta que el MCP de PlatformIO no se cargó en esta sesión.
- `~/.local/share/opencode/log/opencode.log:70975` → `WARN "server unavailable" key=platformio type=local status=failed` (09:45:42 UTC, boot de esta sesión).
- `~/.platformio-mcp/server.log` tenía banners de arranque hasta 2026-09-25 17:00, **ninguno** del 26 → el proceso murió antes de loguear.
- `~/.npm/_logs/2026-09-26T09_45_09_000Z-debug-0.log`: `npx -y platformio-mcp` decidió reinstalar todo (`silly placeDep ROOT platformio-mcp@3.1.0 REPLACE for:`), con `no local data` / `cache miss` en cada tarball (serialport, bindings-cpp, node-gyp). El log se corta en la línea 224 sin `verbose exit` → npm fue matado a los ~33 s.
- Los boots del 23–25 sep fueron cachhits de 1.1 KB (instantáneos); el del 26 fue un reinstall completo de 30 KB.
- `~/.npm/_npx/550b0ddd39c815e4/node_modules/.bin/` había quedado con links creados ese día pero **sin `platformio-mcp`** (solo `pio-agent`) → árbol instalado a medias.
- Factores agravantes: disco al 98% (5.3 GB libres), `_cacache` de npm en 2.7 GB, `_npx` en 1.1 GB. Además el repo raíz no tiene `platformio.ini` (los proyectos viven en subcarpetas).

**Causa raíz:** lanzar el MCP con `npx -y` hace que cada boot consulte el registry y pueda reinstalar el paquete; hoy esa reinstalación tardó más que la ventana de arranque de MCP de opencode (~30 s), el servidor murió y quedó un árbol de `_npx` corrupto.

## Decisiones (usuario)
1. **Ruta A (descartadas B "solo pre-calentar npx" y C "abandonar el MCP, usar pio CLI")**: instalar el paquete **pinneado** de forma global y apuntar opencode al **binario absoluto**, para desacoplar el install del arranque. Se conserva el MCP.
2. **cwd**: apuntar el MCP al proyecto `Proyectos/ESP32_Kids_Lab` (no a la raíz del repo).
3. **`npm cache clean --force` NO autorizado** → no se ejecutó. Queda disponible si el usuario lo pide (liberaría hasta 2.7 GB).

## Actividades
1. `python3 execution/estado_sesion.py check` → `veredicto_global: ok`, sin huérfanos que purgar. `python3 execution/bitacoras.py check` de cierre → `ok`.
2. `npm install -g platformio-mcp@3.1.0` → 154 paquetes en 49 s. Prefix de npm = `/home/cero/.npm-global` (definido en `~/.npmrc`), así que el binario quedó en `/home/cero/.npm-global/bin/platformio-mcp`. Trae **prebuilds** de `@serialport/bindings-cpp` para `linux-x64` (glibc y musl) → sin compilación nativa en install.
3. Verificación del servidor por handshake MCP real (initialize + notifications/initialized + tools/list), con `env -i` replicando exactamente el entorno future de la config y `cwd = Proyectos/ESP32_Kids_Lab`:
   - stderr: banner `PIO Agent v3.1.0 running on stdio`, exit 0.
   - `serverInfo = {platformio-mcp-server, 3.1.0}`, `protocolVersion = 2024-11-05`, **72 tools**.
4. `get_project_config` (read-only) con `projectDir="."` **y** con ruta absoluta: ambos resuelven el proyecto → `env:esp32dev`, platform `espressif32`, board `esp32dev`, framework `arduino`, `lib_ldf_mode deep`, `monitor_speed 115200`, littlefs y las 9 `lib_deps`.
   **Hallazgo operativo:** las tools **exigen `projectDir` explícito**; el `cwd` de la config NO lo suple. Usar `projectDir: "."` (relativo al cwd del proceso) o la ruta absoluta.
5. `opencode.json`: bloque `mcp.platformio` reescrito — `command` absoluto (fuera `npx`), `cwd: "Proyectos/ESP32_Kids_Lab"`, `timeout: 60000`, `environment.PATH` con `elect_env/bin` primero (para que resuelva `pio`) + `.npm-global/bin`, y `PLATFORMIO_CORE_DIR=/home/cero/.platformio` explícito. Sin `--open-dashboard-on-start` (no abrir navegador). Newline final agregado.
6. Validación contra el schema oficial (`McpLocalConfig`): todas las claves usadas están soportadas (`command`, `cwd`, `enabled`, `environment`, `timeout`, `type`); `command[0]` existe y es ejecutable; `cwd` y `PLATFORMIO_CORE_DIR` existen. `timeout` sube del default de 5000 ms a 60000 ms (un `build`/`upload` tarda minutos).
7. `rm -rf ~/.npm/_npx/550b0ddd39c815e4` (62 MB, árbol corrupto, inservible).
8. `python3 execution/alert_user.py success`.

## Segunda fase — limpieza de disco (autorizada por el usuario)

El usuario autorizó explícitamente limpiar `_cacache` y los árboles `_npx` antiguos (el pendiente 3 de la fase 1).

**Inventario previo (qué se iba a perder, todo reversible por re-descarga):**

| Árbol `_npx` | Peso | Paquete | Fecha |
| :--- | :--- | :--- | :--- |
| `f437e8661646c77a` | 369 M | `node` + `wrangler@^4.112.0` | 2026-07-18 |
| `32026684e21afda6` | 195 M | `wrangler@^4.86.0` | 2026-07-10 |
| `0eedb5afd4158ff3` | 166 M | `wrangler@^3.114.17` | 2026-07-11 |
| `ebaba8b9e55fd0a9` | 144 M | `node` standalone (node-bin-setup) | 2026-07-18 |
| `489a79bf3aed000d` | 81 M | `markdown-pdf@^11` | 2026-07-24 |
| `55158e48eb5c59f7` | 66 M | `md-to-pdf@^5.2.5` | 2026-07-24 |
| `15c61037b1978c83` | 15 M | `chrome-devtools-mcp@^1.10.1` | 2026-07-10 |

**Verificaciones de riesgo hechas ANTES de borrar (todas negativas → borrado seguro):**
1. `grep -rn "npx"` en `opencode.json`, `~/.config/opencode/opencode.jsonc` y `.opencode/` → **cero referencias**. Ningún MCP queda lanado por `npx`, así que no puede reintroducirse el fallo de timeout de arranque.
2. `Proyectos/cloudflare-agent` tiene `wrangler` **instalado localmente** (`node_modules/wrangler` + `.bin/wrangler`) → los 730 MB de árboles `_npx` de wrangler eran duplicados, no su instalación.
3. `ps` sin procesos `npm`/`npx`/`node` en curso → nada usando los árboles.
4. El install global de `platformio-mcp` vive en `/home/cero/.npm-global/lib/node_modules/` (74 MB), **independiente** de `_cacache` y `_npx`.

**Ejecutado:**
- `rm -rf /home/cero/.npm/_npx/*` (7 árboles, 1.1 GB).
- `npm cache clean --force` (2.8 GB) → `~/.npm` queda en 268 KB.

**Resultado:** disco de **98% → 96%**, libres de **5.3 GB → 9.1 GB** (+3.8 GB).

**Prueba de regresión (lo importante):** handshake MCP completo **después** de borrar `_cacache`/`_npx`, con el mismo `env -i` y `cwd` de la config → `initialize OK` (`platformio-mcp-server` 3.1.0, proto 2024-11-05) y `get_project_config` → `env:esp32dev`. El servidor arranca **sin red y sin caché**, lo que confirma que el desacoplamiento del fix funciona. `npm` (10.9.8), `node` (v22.23.1) y `pio` (Core 6.2.0) siguen operativos.

## Tercera fase — purga de cachés "Grupo A" (autorizada por el usuario)

El usuario eligió el **Grupo A** de los tres grupos de cachés propuestos (cero
consecuencia: material re-descargable, no trabajo del usuario).

| Carpeta | Peso | Qué es | Comando usado |
| :--- | :--- | :--- | :--- |
| `~/.cache/pip` | 5,8 G | wheels/paquetes Python ya bajados | `python3 -m pip cache purge` → 3825 files, 6181.6 MB |
| `~/.cache/uv` | 628 M | caché del gestor `uv` | `uv cache clean` → 10702 files, 597.8 MiB |
| `~/.cache/thumbnails` | 135 M | miniaturas del explorador de archivos | `rm -rf` (se regeneran solas) |
| `~/.cache/node-gyp` | 67 M | cabeceras C++ para compilar módulos nativos | `rm -rf` (se re-bajan al compilar) |

Se usaron las herramientas de limpieza propias de cada gestor (`pip cache purge`,
`uv cache clean`) en vez de `rm -rf` indiscriminado, para que cada una valide su
propio formato de caché.

**Resultado:** disco de **96% → 94%**, libres de **9,1 GB → 16 GB**. `~/.cache` de 12 GB → **5,2 GB**.

**Corrección a la fase 2:** había clasificado mal `~/.cache/chroma` (167 M) y
`~/.cache/huggingface` (546 M) como "datos de trabajo del RAG". Verificado que **no**:
- `~/.cache/chroma` = `onnx_models/all-MiniLM-L6-v2` → copia local del modelo de
  embeddings que ChromaDB baja, re-descargable.
- `~/.cache/huggingface` = `sentence-transformers/all-MiniLM-L6-v2` y
  `paraphrase-multilingual-MiniLM-L12-v2` → los modelos que usa `rag_system.py`,
  re-descargables.
- El trabajo real e irreemplazable del RAG está en **`chroma_db/` (81 M, en el repo)**,
  NO en `~/.cache`: es el `chroma.sqlite3` con los embeddings de todos los PDFs/`.tex`.
  Nunca se tocó. Para rehacerlo habría que re-procesar todos los documentos.

**Sanity post-purga (todo verificado en vivo):** `platformio 6.2.0` (import), `pio 6.2.0`,
`npm 10.9.8`, `node v22.23.1`, `uv 0.11.11`, `pip 26.0.1`, symlink global
`platformio-mcp` intacto. Handshake MCP completo → `initialize OK`
(`platformio-mcp-server` 3.1.0) y `get_project_config` resuelve `env:esp32dev`.

**Balance total de la sesión (espacio en disco):** 5,3 GB → 16 GB libres (98% → 94%), +10,7 GB recuperados.

## Pendientes
- **Reiniciar opencode** para que cargue la config nueva (los MCP se leen en el boot, no en caliente). No verificado por mí porque no puedo reiniciar el proceso desde dentro.
- Tras el reinicio, validar: (a) sin `WARN "server unavailable" key=platformio` en `opencode.log`; (b) banner nuevo en `~/.platformio-mcp/server.log`; (c) aparecen las tools `platformio_*`; (d) una tool de proyecto devuelve `esp32dev` usando `projectDir: "."`.
- **Opcional, no autorizado — Grupo B y C de cachés (~5,1 GB):** navegadores/bots (`puppeteer` 1,3 G, `opera` 1,3 G, `google-chrome` 1,3 G, `ms-playwright-go` 253 M, `mozilla` 115 M, `cloud-code` 100 M) y modelos de IA re-descargables (`huggingface` 546 M, `chroma` 167 M). Con el disco en 94% y 16 GB libres **no hay urgencia**; se dejan como están. Restos menores: `arduino` 66 M, `mesa_shader_cache*` 64 M, `mintinstall` 37 M.
- Sin resolver por decisión del usuario: la alternativa C (`pio` CLI directo con las 3 capas, sin MCP) queda documentada pero descartada por ahora. Si el third-party `platformio-mcp` (dashboard web, socket.io, lockfiles, tools de flash/reset con approval gates; no oficial de PlatformIO) da problemas, es el plan B.
- Sin resolver por decisión del usuario: la alternativa C (`pio` CLI directo con las 3 capas, sin MCP) queda documentada pero descartada por ahora. Si el third-party `platformio-mcp` (dashboard web, socket.io, lockfiles, tools de flash/reset con approval gates; no oficial de PlatformIO) da problemas, es el plan B.
