---
exported: 2026-10-05T11:32:04.862Z
source: NotebookLM
type: note
title: "Guía MCP FreeCAD"
---

# Guía MCP FreeCAD

Exported at: 5/10/2026, 7:32:04

---

He generado el documento `freecad\_mcp\_gpt6\_guide.md` estructurado y optimizado específicamente para que un **Modelo de Lenguaje Grande (LLM)** o agente CAD lo consuma como especificación técnica, guía de contexto o _system prompt_\[1\]\[2\].

* * *

### **Resumen del contenido estructurado en el Markdown**

1.  **Arquitectura y Bucle de Control (Control Loop):**
    -   Explica el flujo interactivo donde **GPT-6 Astra** genera código Python para FreeCAD, lo transmite mediante el **MCP Connector** (a través de un servidor RPC local) y recibe como retroalimentación capturas de pantalla del _viewport_ 3D para evaluar la geometría y refinar el modelo paso a paso\[1\].
2.  **Guía de Configuración Técnica (6 Pasos):**
    -   **ChatGPT Desktop App:** Requisito de ejecución local\[2\]\[4\].
    -   **FreeCAD (v1.1.3):** Instalación base del software CAD\[4\].
    -   **UVX Utility:** Herramienta CLI configurada mediante PowerShell como Administrador\[5\].
    -   **Add-on FreeCAD MCP:** Copia de la carpeta del add-on en el directorio `%appdata%\FreeCAD\v1.1\Mod`\[6\].
    -   **Conexión Servidor MCP:** Parámetros exactos de conexión `stdio` (`command: uvx`, `args: frecad-mcp`) en ChatGPT\[7\].
    -   **Inicialización y Verificación:** Activación del servidor RPC en FreeCAD y comprobación del enlace\[3\]\[8\].
3.  **Patrones de Prompts y Casos de Uso:**
    -   **Caja para ESP32:** Extracción automática de dimensiones desde un modelo 3D de referencia, flujo de aprobación de planos en 2D/3D previos a la construcción y refinamiento industrial con rejillas de ventilación\[9\].
    -   **Perilla de Guitarra:** Modelado paramétrico preciso a partir de un plano técnico utilizando el _Part Design Workbench_ y su árbol de operaciones\[11\]\[12\].
    -   **Jarrón Japandi:** Diseño generativo y paramétrico basado únicamente en una imagen conceptual\[12\].
    -   **Calibre Vernier:** Ensamblaje con piezas móviles, grabados métricos en relieve negativo (_shallow pockets_) e interacción directa seleccionando caras del modelo en pantalla para añadir moleteado (_knurling_)\[13\]\[14\].
4.  **Directivas Operativas para el Agente LLM:**
    -   Reglas de tolerancia para impresión 3D, inspección previa de objetos en el documento activo y flujo iterativo obligatorio de validación visual mediante capturas antes de dar por terminada una pieza\[2\].

* * *

💡 _¿Te gustaría que adapte este documento en un prompt de sistema (System Prompt) listo para usar en tu propio agente de diseño o que desglosemos más ejemplos de scripts Python para FreeCAD?_
---

## References

[1] I Gave GPT-6 Astra Control of FreeCAD (It Designs Like an Engineer)
[2] I Gave GPT-6 Astra Control of FreeCAD (It Designs Like an Engineer)
[3] I Gave GPT-6 Astra Control of FreeCAD (It Designs Like an Engineer)
[4] I Gave GPT-6 Astra Control of FreeCAD (It Designs Like an Engineer)
[5] I Gave GPT-6 Astra Control of FreeCAD (It Designs Like an Engineer)
[6] I Gave GPT-6 Astra Control of FreeCAD (It Designs Like an Engineer)
[7] I Gave GPT-6 Astra Control of FreeCAD (It Designs Like an Engineer)
[8] I Gave GPT-6 Astra Control of FreeCAD (It Designs Like an Engineer)
[9] I Gave GPT-6 Astra Control of FreeCAD (It Designs Like an Engineer)
[11] I Gave GPT-6 Astra Control of FreeCAD (It Designs Like an Engineer)
[12] I Gave GPT-6 Astra Control of FreeCAD (It Designs Like an Engineer)
[13] I Gave GPT-6 Astra Control of FreeCAD (It Designs Like an Engineer)
[14] I Gave GPT-6 Astra Control of FreeCAD (It Designs Like an Engineer)
