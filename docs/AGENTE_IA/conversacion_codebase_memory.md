# Conversación: Explorado CodeBase Memory y su Integración MCP

## Resumen de la Conversación

En esta conversación se exploró la herramienta **`codebase-memory-mcp`**, su funcionamiento, integración en entornos de desarrollo asistidos por IA (como OpenCode), aplicabilidad en lenguajes como Python, C y Rust, y su comparación conceptual con sistemas de gestión de conocimiento como Obsidian.

> **Nota de revisión (v2):** Este documento ha sido corregido tras contrastarlo con el repositorio real (`DeusData/codebase-memory-mcp`, GitHub). Los matices se marcan como **\[Corrección v2]** dentro del texto.

---

## Historial de la Conversación

### 1. Presentación de CodeBase Memory
**Usuario:**  
En GitHub hay un repositorio que se llama CodeBase Memory. ¿Lo conoces?

**Asistente:**  
Sí, se trata principalmente de **`codebase-memory-mcp`** (desarrollado por DeusData en GitHub), un servidor de **MCP (Model Context Protocol)** diseñado como motor de inteligencia de código.

Está pensado para solucionar el problema del consumo excesivo de tokens al hacer explorar un repositorio entero a asistentes o agentes de IA de código.

**Características principales:**

* **Grafo de conocimiento estático:** Utiliza *tree-sitter* y análisis AST (más Hybrid LSP en varios lenguajes) para indexar la estructura de tu proyecto: clases, funciones, llamadas, rutas HTTP y dependencias.
* **Ahorro masivo de tokens:** En lugar de que la IA aplique `grep` o lea múltiples archivos enteros, consulta directamente el grafo. Esto reduce el consumo de contexto hasta en un 99%.
  > **\[Corrección v2] "99%" es el titular de marketing del README.** El preprint de investigación del propio proyecto ([arXiv:2603.27277](https://arxiv.org/abs/2603.27277)) reporta cifras más conservadoras y verificables: ~**10× menos tokens (≈90%)** con 83% de calidad de respuesta en 31 repositorios reales. Es un ahorro enorme, pero conviene citar la cifra del paper, no la de portada.
* **Rendimiento ultra rápido:** Ejecuta la indexación en memoria (SQLite en RAM + compresión LZ4). Puede indexar proyectos medianos en segundos.
  > **\[Corrección v2] Impreciso y desactualizado.** La versión actual no indexa "en RAM": **persiste el grafo en SQLite en disco** (`~/.cache/codebase-memory-mcp/`, modo WAL, ACID-safe) y **sobrevive reinicios de sesión y compresión de contexto**. Ese claim de "SQLite en memoria + LZ4" correspondía a las versiones tempranas (cuando era un binario Go). El rendimiento real citado por el repo: repositorio medio en milisegundos, Linux kernel (28M LOC, 75K archivos) en 3 minutos, consultas estructurales <1ms.
* **Herramientas de análisis:** Expone herramientas MCP para detección de código muerto, rastreo de impacto de cambios (análisis de *blast radius*), detección de duplicados y arquitectura.
  > **\[Corrección v2]** El número exacto actual es **14 herramientas MCP** (no 15), incluyendo `get_architecture`, `search_graph`, `trace_path`, `index_repository`, entre otras.
* **Visualización 3D:** Incluye una interfaz gráfica local interactiva en 3D (`localhost:9749`) para explorar la red del proyecto visualmente.
  > **\[Corrección v2]** Confirmado. Ojo: la UI solo se expone si se ejecuta con `--ui=true` y descargando la variante con assets de UI.
  > **\[Omisión v2 enriquecida]** Además de la UI, hay **modo CLI**: se pueden invocar las mismas herramientas de análisis directo desde la shell, sin necesidad de cliente MCP.
* **Integración local:** Funciona como un binario estático único (en C/C++), sin dependencias externas y procesando todo al 100% de forma local.
  > **\[Corrección v2]** El repositorio actual es **C puro** (no C/C++): `src/main.c` como punto de entrada, con gramáticas tree-sitter embebidas en el binario. Single static binary, sin runtime de lenguaje, sin servicio hosteado y sin API key.

**\[Omisión v2 — Auto-sync]:** El servidor incorpora un **watcher en background* que detecta cambios (polling de git con intervalos adaptativos) y **re-indexa de forma incremental** sin intervención manual. No es "indexar una vez y quedarse obsoleto".

---

### 2. Integración en OpenCode
**Usuario:**  
¿Se puede usar en un proyecto dentro de OpenCode?

**Asistente:**  
**Sí, se puede integrar perfectamente.** Dado que OpenCode soporta la especificación de **MCP (Model Context Protocol)**, puedes añadir `codebase-memory-mcp` como un servidor MCP local para que el agente de OpenCode consulte el grafo de conocimiento del proyecto antes de leer o editar archivos.

#### Configuración Paso a Paso

1. **Binario o ejecutable del servidor:**  
   Asegúrate de tener el binario ejecutable de `codebase-memory-mcp` compilado/descargado o de poder ejecutarlo mediante `npx` / `uvx` / ejecutable directo en tu entorno Linux.

2. **Añadir a la configuración de OpenCode:**  
   Abre tu archivo de configuración global o local de OpenCode (por ejemplo, `~/.config/opencode/config.json` o `.opencode/mcp.json` según la estructura de tu espacio de trabajo):

   ```json
   {
     "mcpServers": {
       "codebase-memory": {
         "command": "codebase-memory-mcp",
         "args": ["--project-path", "."],
         "env": {}
       }
     }
   }
   ```
   *(Si utilizas un binario descargado directamente, reemplaza `"codebase-memory-mcp"` en `"command"` por la ruta absoluta al ejecutable, ej: `"/home/usuario/bin/codebase-memory-mcp"`).*

3. **Probar la integración en la sesión:**  
   Al iniciar OpenCode dentro del repositorio:
   * El servidor MCP construirá automáticamente la base de datos en memoria (SQLite + LZ4) del proyecto actual.
     > **\[Corrección v2]** No se "construye en memoria": el índice se **persiste en `~/.cache/codebase-memory-mcp/`** y se reutiliza entre sesiones (gracias al modo WAL y al watcher incremental). Solo requiere el paso `index_repository` con **ruta absoluta** en el primer uso.
   * El agente de OpenCode detectará las nuevas herramientas (`tools`) expuestas por el servidor, como la búsqueda de símbolos, grafo de llamadas o detección de dependencias.
   * Cuando le pidas al agente tareas como *"analiza el impacto de modificar esta función"*, OpenCode llamará primero a la herramienta de `codebase-memory` para obtener la estructura exacta en lugar de escanear y leer múltiples archivos raw.

**\[Corrección v2 — confirmación]:** El propio repo lista **OpenCode** explícitamente entre los clientes soportados ("Plug and play across 11 coding agents" / 43 superficies de cliente), junto a Claude Code, Codex CLI, Cursor, Windsurf, Gemini CLI, Aider, entre otros. La integración es real y soportada de primera mano.

---

### 3. Aplicabilidad en Lenguajes (Python, C, Rust)
**Usuario:**  
Me pregunto si será útil esta herramienta para el desarrollo de código Python, Rust, C, etc.

**Asistente:**  
**Sí, es extremadamente útil para esos lenguajes**, pero el nivel de profundidad varía según cómo extrae la estructura de cada uno.

El valor principal de `codebase-memory-mcp` reside en que utiliza **Tree-sitter** para análisis sintáctico (AST) rápido combinado con servidores **LSP (Language Server Protocol)** o analizadores nativos cuando están disponibles.

> **\[Corrección v2 — matiz clave sobre "LSP"]:** El proyecto NO ejecuta servidores LSP. Emplea una capa propia llamada **Hybrid LSP**: una **implementación ligera en C de los algoritmos de resolución de tipos** de los language servers (inspirada en pyright, gopls, rust-analyzer, tsserver, Roslyn, JDT), embebida en el mismo binario. La diferencia es importante: resuelve imports, genéricos, herencia y tipos de stdlib **sin lanzar un proceso externo por proyecto**. Los lenguajes con Hybrid LSP completo: Python, TypeScript/JS/JSX/TSX, PHP, C#, Go, C, C++, Java, Kotlin y Rust. Lenguajes sin esa capa caen en resolución textual (siempre hay *alguna* respuesta).

#### Análisis por Lenguaje

* **Python:** 
  * **Utilidad:** **Muy Alta.**
  * **Por qué:** Al ser un lenguaje dinámico, los modelos de lenguaje suelen confundirse siguiendo importaciones relativas, decoradores o estructuras complejas de paquetes. El servidor mapea funciones, clases, tipos e importaciones sin ejecutar el código, permitiendo al agente saber exactamente qué módulos dependen de otros sin saturar la ventana de contexto.
  * **\[Corrección v2]** Python entró a la capa Hybrid LSP en v0.7.0 (imports + submodule walks, dataclasses, `Self`, generics, `@property`, `match/case`, SQLAlchemy 2.0 `Mapped[T]`, Pydantic `BaseModel`). Está en el tier "Good" (75-89%) del benchmark oficial.

* **C:**
  * **Utilidad:** **Alta / Crítica en código legado.**
  * **Por qué:** En C no hay conceptos de alto nivel como *namespaces* nativos u objetos; todo se reduce a archivos `.h`/`.c`, structs, macros de preprocesador y llamadas a funciones. El grafo reconstruye visualmente la jerarquía de llamadas (*call graph*) y permite saber inmediatamente qué archivos de cabecera o funciones se verán afectados si cambias la firma de una función.
  * **\[Corrección v2]** C está en el tier **"Excellent" (≥90%)** del benchmark oficial — de los mejores soportados.

* **Rust:**
  * **Utilidad:** **Excelente.**
  * **Por qué:** La estructura modular de Rust (`mod`, `use`, `traits`, y visibilidades con `pub`) es rígida y jerárquica. Tree-sitter parsea impecablemente los bloques `impl`, structs y enums. Esto permite al agente de IA navegar entre definición de traits e implementaciones concretas instantáneamente sin tener que compilar el código.
  * **\[Corrección v2]** Rust entró a Hybrid LSP en v0.8.0 (`use` + paths de módulo, bloques `impl` y métodos de trait, generics con trait bounds, desugaring de traits de operadores, síntesis de métodos por derive-macro, paths estáticos UFCS, preludio std común). Tier "Good" (75-89%).

#### Casos de Uso Clave donde Destaca

* **Análisis de *Blast Radius* (Impacto de Cambios):** Antes de modificar una función en C o Python, le preguntas al agente cuál es el impacto. La herramienta consulta el grafo y responde exactamente qué 5 o 10 funciones en todo el proyecto llaman a esa rutina.
* **Detección de Código Muerto:** Identifica rápidamente funciones, structs o módulos que no tienen referencias entrantes en el grafo.
* **Onboarding en repositorios gigantes:** Puedes pedirle a la IA que trace la ruta completa desde el punto de entrada (`main` o endpoint HTTP) hasta la capa de persistencia de datos (herramienta `trace_path`).
* **\[Adición v2] Arquitectura instantánea:** La herramienta `get_architecture` devuelve en una sola llamada lenguajes, paquetes, puntos de entrada, rutas HTTP, hotspots, límites, capas y clusters — orientación total de un repo desconocido sin leer archivos.

---

### 4. Comparación con Obsidian
**Usuario:**  
¿Esta herramienta es similar a Obsidian?

**Asistente:**  
**Tiene similitudes conceptuales en su núcleo, pero sirven para propósitos completamente distintos.**

La analogía es adecuada porque ambas herramientas **indexan información y construyen un grafo de conexiones** (nodos y enlaces) para evitar que la información sea un bloque plano de texto. Sin embargo, se diferencian marcadamente en su ejecución y destinatarios:

| Característica | Obsidian | `codebase-memory-mcp` |
| :--- | :--- | :--- |
| **Objetivo** | Gestión del conocimiento personal (PKM / "Segundo Cerebro"). | Indexación y navegación rápida de código fuente para IAs. |
| **Entrada de datos** | Archivos Markdown creados o editados por humanos. | Código fuente (Python, C, Rust, etc.) analizado vía AST/Tree-sitter. |
| **Construcción de enlaces** | Enlaces bidireccionales explícitos (`[[nota]]`) escritos manualmente. | Grafo implícito generado automáticamente (llamadas, herencias, imports). |
| **Usuario principal** | **Humanos** (navegan visualmente por las notas). | **Agentes de IA / LLMs** (consultan el grafo mediante el protocolo MCP). |
| **Interfaz** | Aplicación gráfica rica (editor, vista de grafo 2D/3D). | Servidor backend en segundo plano (con visualizador 3D opcional local). |

#### La Gran Diferencia

* **Obsidian** está diseñado para que **tú** conectes ideas conceptuales en notas de texto.
* **CodeBase Memory** está diseñado para que un **agente de IA** entienda la arquitectura de un sistema de software sin tener que leer todos los archivos del disco, reduciendo el consumo de tokens mediante consultas estructuradas.

Si buscas algo verdaderamente equivalente a Obsidian pero orientado a IAs, existen proyectos MCP como *`obsidian-graph-memory`*, los cuales permiten a un LLM leer y navegar el grafo de notas Markdown en tu vault de Obsidian.

---

## \[Adición v2] Relación con los sistemas de memoria tipo RAG (contraste importante)

Una confusión común es pensar que `codebase-memory-mcp` **compite** con un sistema RAG (Retrieval-Augmented Generation) para código. No es así: son capas **ortogonales** y complementarias.

| Aspecto | RAG (embeddings) | Grafo de conocimiento estructural |
| :--- | :--- | :--- |
| **Unidad de indexación** | Vectores semánticos de fragmentos de texto | Nodos/aristas sintácticos (funciones, llamadas, imports) |
| **Qué responde** | *Similitud semántica*: "¿qué habla de X?" | *Estructura exacta*: "¿quién llama a Y?", "¿dónde se define Z?" |
| **Ventaja** | Conoce el *significado* de la prosa, docs, comentarios | Exactitud determinista sobre símbolos y dependencias |
| **Limitación** | No resuelve referencias exactas entre símbolos | No entiende el *contenido semántico* de textos largos |
| **Caso típico** | Preguntas sobre documentación, conceptos, PDFs | *Blast radius*, dead code, trazado de llamadas, arquitectura |

Para un espacio de trabajo multi-lenguaje (Python, C, Rust, Verilog, LaTeX), lo ideal es **usarlos como capas combinadas**: el grafo estructural para navegar símbolos y medir impacto de cambios; el RAG para recuperar contexto semántico de documentación. Uno no sustituye al otro.

---

## Resumen de matices corregidos

1. **Persistencia real:** el índice se guarda en SQLite en disco (`~/.cache/codebase-memory-mcp/`, WAL), sobrevive reinicios; no es "SQLite en RAM".
2. **Cifra de tokens:** "99%" es marketing del README; el paper ([arXiv:2603.27277](https://arxiv.org/abs/2603.27277)) reporta ~10× menor consumo (≈90%).
3. **Lenguaje del binario:** C puro (no C/C++), con 14 herramientas MCP actuales.
4. **"LSP" ≠ procesos LSP:** la capa Hybrid LSP es una implementación ligera embebida en C, sin servidores externos.
5. **Auto-sync y watcher:** re-indexación incremental automática vía polling de git (no manual).
6. **Modo CLI y `get_architecture`:** capacidades adicionales relevantes que el diálogo original omitía.
7. **Relación con RAG:** son capas complementarias (estructural vs semántico), no competidoras.