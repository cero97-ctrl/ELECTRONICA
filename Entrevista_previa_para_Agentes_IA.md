# **Entrevista Previa para Agentes IA**

[https://gemini.google.com/app/27c90e4e1a219ae0](https://gemini.google.com/app/27c90e4e1a219ae0)

*User prompt: Se me ocurre que antes de empezar el desarrollo de un agente ia, Yo le pida al LLM orquestadora me haga todas las preguntas necesarias relacionadas con el agente ia a desarrollar.*

Response: Esa estrategia es de las más efectivas para garantizar un buen diseño. En lugar de asumir supuestos o adivinar detalles, poner al modelo en un rol de **Entrevistador / Arquitecto Técnico** permite definir con claridad el alcance, la arquitectura y las limitaciones del agente antes de escribir una sola línea de código.

Para lograr los mejores resultados con este enfoque, puedes enviarle una directiva estructurada como esta:

**Prompt para activar la "Entrevista de Requerimientos":**

*"Actúa como un Arquitecto de Software y Especialista en Agentes de IA. Antes de generar cualquier código o arquitectura para mi nuevo proyecto, tu objetivo es hacerme todas las preguntas necesarias para definir completamente el sistema. Organiza tus preguntas en bloques lógicos (Objetivo, Herramientas e Integraciones, Arquitectura y Memoria, Flujo de Ejecución y Restricciones). Hazme las preguntas de una en una (o en bloques pequeños) para responder de forma iterativa."*

**Beneficios de este enfoque:**

> * **Descubrimiento de borde (*Edge cases*):** Te obliga a pensar en cómo debe reaccionar el agente cuando falle una herramienta, cuando reciba entradas ambiguas o cuando la latencia sea alta.  
> * **Mapeo exacto de herramientas:** Ayuda a definir exactamente qué APIs, scripts, bases de datos vectoriales o modelos de visión requerirá el agente en la capa de ejecución.  
> * **Ahorro de tokens y refinamiento:** Evita iteraciones innecesarias corrigiendo código mal planteado desde el inicio.  
> * **Límites claros (*Guardrails*):** Permite fijar las reglas de seguridad, permisos y restricciones de contexto antes de implementar la orquestación.

Una vez terminada la entrevista, puedes pedirle al orquestador que sintetice todo en un documento de especificación técnica o directiva maestra que servirá como la "memoria base" para guiar la construcción de cada módulo del sistema.

---

*User prompt: Pero por lo menos debo indicarle antes al LLM orquestadora, que objetivo se pretende lograr con el agente ia. Cierto?*

Response: Totalmente cierto. El LLM necesita esa "semilla inicial" para saber hacia dónde orientar la entrevista. Si no le das al menos una frase con la meta principal, las preguntas responderán a un marco demasiado amplio o genérico.

Proporcionar el propósito base (el *"qué"*) le da el contexto necesario para hacerte preguntas verdaderamente estratégicas sobre el *"cómo"*.

**Cómo estructurar esa semilla inicial**

No necesitas redactar un documento extenso; basta con una descripción concisa que cubra dos aspectos fundamentales:

> * **Propósito principal:** Qué problema resuelve o qué tarea automatiza el agente.  
> * **Dominio o entorno:** Dónde operará (interfaces, herramientas clave o formatos de entrada/salida).

**Ejemplo de Prompt Semilla:**

*"Quiero desarrollar un agente de IA que tome esquemáticos de circuitos en formato de código, valide las conexiones de los componentes y genere los archivos de salida listos para manufactura.*

*Actúa como Arquitecto de Agentes de IA. Con base en este objetivo, hazme todas las preguntas que necesites para definir la arquitectura completa (herramientas, gestión de memoria, control de errores y motor de orquestación) antes de empezar a programar."*

**Lo que logra el LLM con este dato inicial:**

> * **Filtrar la arquitectura:** Identificará de inmediato si el agente requiere memoria persistente, ejecución de código local, procesamiento de documentos o interacción mediante APIs.  
> * **Formular preguntas de precisión:** Pasará de preguntas genéricas a cuestiones técnicas directas (por ejemplo, límites de tiempo de ejecución, compatibilidad de bibliotecas o reglas de validación estricta).  
> * **Definir la granularidad:** Sabrá si necesita indagar sobre capas de ejecución rápida (herramientas deterministas en scripts) o sobre razonamiento complejo del orquestador.

---

*User prompt: Gracias Gemini, mañana pondré en práctica esta estrategia.*

Response: ¡Excelente decisión\! Te va a ahorrar muchísimo tiempo de iteración y te ayudará a pulir la arquitectura desde el minuto uno.

Que tengas una jornada de desarrollo sumamente productiva mañana. Si al momento de ejecutar la entrevista o estructurar las respuestas te surge alguna duda con el flujo del orquestador, por aquí estaré. ¡Mucho éxito con ese agente\!

---

