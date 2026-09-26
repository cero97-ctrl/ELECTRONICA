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
7. `rm -rf ~/.npm/_npx/550b0ddd39c815e4` (62 MB, árbol corrupto, inservible). `_npx` queda en 1.1 GB / 7 entradas. Disco sigue al 98% (5.3 GB libres).
8. `python3 execution/alert_user.py success`.

## Pendientes
- **Reiniciar opencode** para que cargue la config nueva (los MCP se leen en el boot, no en caliente). No verificado por mí porque no puedo reiniciar el proceso desde dentro.
- Tras el reinicio, validar: (a) sin `WARN "server unavailable" key=platformio` en `opencode.log`; (b) banner nuevo en `~/.platformio-mcp/server.log`; (c) aparecen las tools `platformio_*`; (d) una tool de proyecto devuelve `esp32dev` usando `projectDir: "."`.
- Disco al 98%: decidir si limpiar `_cacache` (2.7 GB) y/o los `_npx` antiguos (los 6 restantes son de jul-sep, ~700 MB, de otros paquetes). Requiere autorización del usuario.
- Sin resolver por decisión del usuario: la alternativa C (`pio` CLI directo con las 3 capas, sin MCP) queda documentada pero descartada por ahora. Si el third-party `platformio-mcp` (dashboard web, socket.io, lockfiles, tools de flash/reset con approval gates; no oficial de PlatformIO) da problemas, es el plan B.
