---
origen: https://github.com/morluto/rea
fuente_primaria: https://github.com/morluto/rea (README) + https://rea.tools/ + https://github.com/morluto/rea/blob/main/docs/installation.md
tipo_fuente: repo
fecha_captura: 2026-10-12
fecha_fuente: 2026-10-12
autor_declarado: "morluto"
autor_verificado: sí
citable: no
estado: analizado
analisis: Sessions/2026-10-12_rea_evaluacion_incorporacion.md
---

# Ingeniería Inversa IA (REA — Reverse Engineer Anything)

> **Nota de procedencia.** Este `.md` es la conversión a markdown de una nota de
> NotebookLM (metadatos originales `exported: 2026-10-12`, `source: NotebookLM`,
> `title: "Ingeniería Inversa IA"`). Es una **fuente secundaria, no citable**: el
> texto de más abajo reproduce lo que dijo esa nota, **incluidos sus errores**.
> La fuente primaria verificable es el repositorio `morluto/rea` y el sitio
> `rea.tools`. El análisis crítico completo vive en
> `Sessions/2026-10-12_rea_evaluacion_incorporacion.md`.
>
> **Aviso de imprecisiones corregidas.** Contradice a la fuente primaria en: el
> nombre del paquete/comando de instalación, la lista de asistentes soportados, el
> alcance real de la herramienta y la ausencia de requisitos de runtime. Ver el
> bloque *Correcciones verificadas* justo debajo.

## Correcciones verificadas (2026-10-12)

| Lo que afirma la nota | Verificado en la fuente primaria |
|---|---|
| Paquete `rea-agent`; comando `npx rea-agent setup` | El paquete npm es **`rea-agents`** y el comando es **`npx rea-agents setup`** (release **6.4.0**, 2026-10-11). |
| "asistentes de IA (como Claude Code, Cursor, Codex y Gemini CLI)" | Soporta además, con client ID explícito, **OpenCode** (`--client opencode`), Windsurf, Devin, GitHub Copilot CLI, Qwen Code, VS Code, Grok Build, OMP, Pi, Hermes y **DeepSeek Harness** (`--client dsh`, solo en `main`, aún fuera de la 6.4.0). |
| "Ghidra, Hopper, descompiladores de .NET, Electron y paquetes Android" | La cobertura es mayor: binarios nativos, **ELF, Go, WASM y bytecode EVM**, JS/Electron, sitios web, capturas HAR, **.NET**, APK/dispositivos Android, JEB, **firmware (binwalk/unblob)**, paquetes/recursos y comportamiento de procesos. |
| (no menciona requisitos ni motores) | Requiere **Node.js 22.19+/24.11+/26+**. Los motores nativos **Hopper, IDA y JEB son software comercial** (no incluidos; Ghidra es libre). El análisis corre localmente. |

---

## Texto original de la nota (sin editar)

El enlace exacto al repositorio de GitHub del proyecto es:

-   **Repositorio en GitHub:**[https://github.com/morluto/rea](https://www.google.com/url?sa=E&q=https%3A%2F%2Fgithub.com%2Fmorluto%2Frea)
-   **Documentación oficial:**[https://rea.tools/](https://www.google.com/url?sa=E&q=https%3A%2F%2Frea.tools%2F)

### Detalles clave del proyecto:

-   **Autor / Organización:**`morluto`
-   **Nombre completo:REA (Reverse Engineer Anything)**
-   **Funcionalidad:** Actúa como un servidor **MCP (Model Context Protocol)** y CLI que conecta asistentes de IA (como Claude Code, Cursor, Codex y Gemini CLI) con descompiladores y herramientas de análisis local (como **Ghidra**, **Hopper**, descompiladores de .NET, Electron y paquetes Android) para reconstruir funcionalidades a partir de binarios y comportamiento en tiempo de ejecución.
-   **Licencia e instalación:** Licencia de código abierto MIT, instalable mediante `npx rea-agent setup`.

* * *

📥 ¿Te gustaría que agregue este repositorio a las fuentes de tu cuaderno para que podamos analizar a fondo sus comandos y flujo de trabajo?
