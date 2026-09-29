# 2026-09-23 — renombre_carpeta_esp32_kids_lab

## Tema
Persistir que `docs/ESP32_KIDS_LAB/` es la ruta canónica; análisis de imagen PlatformIO; recomendaciones de compilación para colega; integración de PlatformIO con OpenCode; prototipo MCP servidor sismológico para Prof. Rommel Contreras.

## Contexto
- El usuario confirmó que la carpeta `docs/ESP32_KID_LAB` ya no existe; la canónica es `docs/ESP32_KIDS_LAB/` (renombrada/consolidada en la sesión 2026-09-23_esp32_kid_lab_platformio).
- Verificación en disco: `ls docs/` confirma solo `ESP32_KIDS_LAB/` y `ESP32-S3/`; grep de `ESP32_KID_LAB` solo aparece en la bitácora histórica de la sesión anterior (ya documenta el renombre correctamente).
- El usuario envió `docs/ESP32_KIDS_LAB/platformio.jpeg`: captura de un chat del colega (Rodolfo Acosta) con 4 recomendaciones previas a compilar un proyecto ESP32-S3 con PlatformIO + Edge Impulse (cerrar apps por OOM, ≥15 GB libres en `C:\Users\Rodolfo Acosta\.platformio\`, compilación de 45-60 min, no interrumpir en `micro_allocator.cpp`). Modelo actual sin soporte de imagen: se analizó vía flujo determinista (gemini-2.5-flash, informe en `docs/IMAGENES/informe_imagen/informe_analisis_platformio.pdf`).
- El usuario preguntó si PlatformIO se puede usar desde OpenCode (no solo VSCode). Respuesta: sí, PlatformIO es CLI-first; se procedió a integrarlo.
- Entorno: PC con 4 GB RAM (95% usado por el SO); RAM limitada, no usar tareas pesadas en paralelo.

## Decisiones (usuario)
1. Actualizar la memoria del agente: usar `docs/ESP32_KIDS_LAB/` como única ruta válida; no referenciar `docs/ESP32_KID_LAB`.
2. Generar `docs/ESP32_KIDS_LAB/recomendaciones.{tex,pdf}` (estilo infográfico) para compartir con el colega: sus 4 recomendaciones + adicionales (antivirus/pagefile/`pio run` en terminal, `PLATFORMIO_CORE_DIR`, espacio del proyecto, `build_cache_dir`/`ccache` en `platformio.ini`, fuera de OneDrive, "no necesitas salir de VSCode", después de compilar).
3. Integrar PlatformIO en OpenCode: instalar Core en `elect_env`, registrar MCP `platformio-mcp`, y documentar.

## Actividades
- Renombre de carpeta verificado y bitácora actualizada (inicio de sesión).
- Análisis de `platformio.jpeg` con `flujo_analizar_imagen.py` (backend gemini, sin créditos). JSON en `.tmp/analisis_platformio.json`.
- Generación y compilación de `docs/ESP32_KIDS_LAB/recomendaciones.{tex,pdf}` vía `.tmp/generar_recomendaciones_pio.py` (importa `PREAMBULO_INFOGRAFIA`; se corrigió `\path`/`\url` con barra invertida final → macro `\rutaPio` con `\texttt`).
- Instalación: `python3 -m pip install platformio` → PlatformIO Core 6.2.0 en `elect_env` (`/home/cero/anaconda3/envs/elect_env/bin/pio`).
- Prueba determinista en `/tmp/opencode/pio_esp32s3_test/` (board `esp32-s3-devkitc-1`, framework arduino, blink): `pio project init` + `pio platform install espressif32` (ya estaba) + `pio run` → SUCCESS en 79 s (RAM 5.7%, Flash 7.5%). Proyecto de prueba fue fora de repo.
- MCP: paquete npm `@platformio/mcp` NO existe (404); el real es `platformio-mcp` v3.0.0 (jl-codes, open-source). Registrado en `opencode.json` (`type: local`, `npx -y platformio-mcp`, environment PATH de `elect_env`+nvm). Verificado `initialize` handshake OK (serverInfo platformio-mcp-server). Requiere reinicio de opencode.
- Guía `docs/ESP32_KIDS_LAB/platformio_opencode.{tex,pdf}` generada con `.tmp/generar_platformio_opencode.py`: instalación, flujo básico CLI (init/run/upload/monitor/device list), regla determinista 3 capas, tabla VSCode vs OpenCode, verificación del build.
- Tras reinicio del usuario: MCP `platformio` cargado (herramientas del server visibles); `platformio_get_policy_status` → `flash_requires_approval` (uploads requieren aprobación); `platformio_get_lock_status` → `isLocked: false`.
- Nuevo tema: doblete sísmico en Venezuela; el colega físico Prof. Rommel Contreras quiere un servidor MCP para compartir datos sísmicos con investigadores/LLMs. Respuesta conceptual: MCP client-server, transporte Streamable HTTP para remoto, sin API LLM en el servidor, Cloudflare Tunnel recomendado por CGNAT en VE.
- Documento `docs/SISMOLOGIA_MCP/servidor_mcp_sismico_rommel.{tex,pdf}` (para Rommel) generado con `.tmp/generar_servidor_mcp_sismico.py`: modelo MCP, Streamable HTTP, topología CGNAT/Tunnel (ejemplo `cloudflared tunnel --url http://127.0.0.1:8000`), código FastMCP, config cliente opencode (`type: "remote"` + Bearer) y Claude Desktop (`type: "http"`), consideraciones. Corregidos `\textnumero{}` y `\hyperlink{}` (fuera de estilo infográfico).
- PROTOTIPO MCP SISMOLÓGICO (3 capas, completo y probado):
  - L3 `execution/servidor_sismico.py`: FastMCP determinista. Catálogo sintético con seed fija `20260923` (42 eventos: 40 + 2 réplicas `-B` del doblete), zonas Andes Venezolanos (Táchira/Mérida/Trujillo/Barinas), carga JSON/CSV real vía `--catalogo`, herramientas MCP `eventos`, `evento`, `waveform` (señal determinista por hash del id), `estadisticas`. `--generar-sintetico DIR` escribe `catalogo_sismico.json`.
  - L2 `flujo_servidor_sismico.py` (raíz): subcomandos `generar|iniciar|estado`; valida catálogo (existencia, forma lista, ids únicos); escribe `.tmp/run_state_sismico.json`; lanza L3.
  - L1 `directives/servidor_sismico.yaml`: SOP con goal, inputs, steps, outputs, tools, config de clientes y edge cases.
  - Probado: stdio handshake + tools/list + las 4 tools OK; streamable-http (uvicorn 127.0.0.1:8765) handshake y tools con SDK MCP OK.
  - Errores corregidos durante el desarrollo (para `.agent/python.md`): (a) FastMCP v1 requiere `@mcp.tool()` (con paréntesis), con `@mcp.tool` lanza `TypeError: The @tool decorator was used incorrectly`; (b) en mcp 1.30 `host`/`port` van en el constructor `FastMCP(...)`, NO en `run()` (`run` solo recibe `transport`/`mount_path`); (c) colisión de nombres: parámetro `eventos` (lista) sombreado por la herramienta `eventos` decorada → `'function' object is not iterable`; solución: renombrar el parámetro del closure a `catalogo`.
  - `--token` es informativo: FastMCP v1 no valida Bearer por defecto; se recomienda proteger a nivel de túnel/nginx (queda documentado en directiva y código).
- Manual de instalación para la máquina del Prof. Rommel: `docs/SISMOLOGIA_MCP/manual_instalacion_servidor_sismico.{tex,pdf}` generado con `.tmp/generar_manual_servidor_sismico.py`. Contenido: requisitos (Python 3.10+, `pip install "mcp<2"` — por qué el pin), Paso 1 clonar/copiar las 3 capas + catálogo sintético ya incluido (`generar`), Paso 2 prueba local stdio (config cliente opencode `type: "local"`), Paso 3 conectar datos reales (tabla de campos JSON/CSV: id, fecha_utc, latitud, longitud, magnitud, profundidad_km, lugar, tipo; validación de ids únicos por el orquestador), Paso 4 exponer con `streamable-http` + cloudflared tunnel (endpoint `/mcp`), Paso 5 token/HTTPS y seguridad (proteger a nivel túnel/nginx), Paso 6 configuración de clientes remotos de los colegas (opencode `type: "remote"` / Claude Desktop `type: "http"`), checklist final y tabla de troubleshooting.

## Pendientes
- Reiniciar opencode para cargar el MCP `platformio` (opencode no hot-reloads config). — HECHO; MCP cargado y verificado.
- Decidir si el proyecto ESP32-Kids-Lab se clona/copia a este workspace para trabajar con `pio` desde OpenCode (no existía proyecto local; solo el de prueba en /tmp).
- (Nota créditos/recursos: MCP y `pio` no consumen OpenRouter; el análisis de imagen usó cuota free de Gemini.)
- Prototipo sismológico: queda entregado y probado (3 capas). Pendiente si Rommel quiere datos reales: sustituir `--catalogo` por su JSON/CSV real, exponer con `--transporte streamable-http` detras de Cloudflare Tunnel/nginx, y si requiere auth real implementar `token_verifier` OAuth de FastMCP (fuera de alcance del prototipo). Sugerencia: guardar los aprendizajes de FastMCP v1 (a/b/c) en `.agent/python.md`.
