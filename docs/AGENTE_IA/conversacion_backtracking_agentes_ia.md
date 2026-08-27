# Técnica de Backtracking y Corrección de Errores en Agentes de IA

## Pregunta del Usuario
> Hay una técnica para corregir errores en el código y evitar cometelos de nuevo a futuro que utilizan los desarrolladores de Agentes ia llamada Backtraking. La conoces?

---

## Respuesta

Sí, la conozco muy bien. En el contexto de los **Agentes de Inteligencia Artificial** y el desarrollo de software, el *Backtracking* es una técnica que permite al agente **desechar una ruta de ejecución defectuosa** en lugar de seguir construyendo sobre código roto, y combinarla con memoria reflexiva para no repetir los mismos errores a futuro.

Sin embargo, es importante aclarar desde el inicio un matiz que suele confundirse en las explicaciones divulgativas: **el "backtracking" que usan los agentes en producción no es el algoritmo clásico, y hay que distinguir dos técnicas diferentes que se agrupan bajo el mismo nombre.**

---

## Matiz 1: son dos técnicas distintas, no una

| Técnica | Qué rebobina | Dónde se usa realmente |
|---|---|---|
| **Búsqueda en árbol (Tree of Thoughts)** | El *razonamiento*: explora múltiples ramas de pensamiento, evalua cada una y vuelve atrás en el árbol para probar otra. | Patrón de investigación (Yao et al., 2023). Raramente implementado en agentes productivos por su costo. |
| **Checkpoint / Rollback de estado** | El *estado de los artefactos*: código, archivos, config. Guarda un punto funcional, prueba, y si falla revierte ese estado y reintenta otra estrategia. | **Lo que realmente hacen los agentes programadores en producción.** |

Un LLM autoregresivo **no puede "deshacer sus propias decisiones de pensamiento"**: genera token por token hacia adelante y su razonamiento queda fijado en el contexto. Lo que sí se revierte es el **estado de los artefactos** — con git, snapshots, o archivos de estado — para luego intentar una ruta alternativa aprovechando el contexto acumulado sobre lo que ya falló.

---

## Cómo funciona en producción: ciclo Generate → Verify → Rollback → Retry

El agente operativo opera mediante este ciclo, que incluye disciplinas que las explicaciones simplificadas suelen omitir:

1. **Estado de Punto de Control (Checkpointing):** Guarda el estado funcional del código antes de aplicar un cambio (commit, snapshot, archivo de estado).
2. **Ejecución y Verificación (Feedback del entorno):** El agente escribe una solución y la prueba con linters, compiladores o tests unitarios. **La verificación debe ser determinista** (misma entrada → misma salida) e incluir la **validación de entradas/salidas esperadas**, no solo "que no tire error".
3. **Detección de fallo (fail loudly):** Si la prueba falla, entra en bucle, o la salida no coincide con lo esperado, el agente **se detiene y diagnostica** — no sigue generando parches sobre el código roto.
4. **Análisis de causa raíz (condición del reintento):** Antes de reintentar, el agente **clasifica el fallo**: es de *Lógica* (algoritmo), *Entorno* (dependencias, versiones) o *Recursos* (RAM, CPU). Reintentar sin este diagnóstico solo repite el mismo error con otra forma.
5. **Rebobinado (Rollback):** El agente revierte al punto de control anterior en los artefactos (no en su razonamiento).
6. **Reintento con restricción explícita:** Intenta una ruta alternativa aplicando una restricción aprendida: *"No uses `df.append()` en pandas 2.0 — falló con `AttributeError`; usar `pd.concat()`"*.
7. **Presupuesto de reintentos (retry budget):** El ciclo se repite **máximo un número acotado de veces (típicamente 3)**. Agotado el presupuesto, el agente **detiene y escala al humano** en lugar de caer en un bucle infinito.

---

## Cómo se evita cometer el mismo error a futuro

El *Backtracking* por sí solo evita el error **en la sesión actual**. Para **no volver a cometerlo a futuro**, los desarrolladores lo combinan con **Memoria de Reflexión**:

* **Memoria Procedimental / Episódica (Reflexión):** Al hacer *rollback*, el agente genera un resumen en lenguaje natural del fallo (patrón de los frameworks *Reflexion* y *LATS*):
  > *"Intenté usar `df.append()` en pandas 2.0 y causó un `AttributeError`. El método fue deprecado. Debo usar `pd.concat()`."*
* **Inyección en el Contexto Futuro:** Esa lección aprendida se guarda en una base de datos vectorial o en la memoria persistente del agente. La próxima vez que enfrente una tarea similar, recupera esta regla como instrucción del sistema y **evita el camino defectuoso antes de escribir la primera línea de código**.
* **Acumulación sobre SOPs:** En arquitecturas maduras, el conocimiento no solo se guarda como recuerdos sueltos sino que se incorpora a los **manuales de operación (SOPs) y registros de errores** que el agente consulta de forma permanente, sin borrar la historia: cada hallazgo se suma, no se sobrescribe.

---

## Ejemplo práctico en arquitecturas actuales

En frameworks como **LangGraph** o en espacios de trabajo con arquitectura de 3 capas (directivas → orquestación → ejecución):

```
[Inicio de Tarea]
       │
       ▼
[Checkpoint: estado funcional guardado]
       │
       ▼
[Generar Código (Estado A)]
       │
       ▼
[Verificación determinista:                    No ──► [Clasificar causa raíz]
 ¿tests + linters + validación de IO?]  ─────────────►   Lógica / Entorno / Recursos
       │                                                    │
       Sí                              [retry budget]        ▼
       ▼                              ┌──¿Quedan ┌─► [Guardar error en Memoria Reflexiva]
[Validar salida esperada]              │  intentos?            │
       │                               └─────No──► [Escalar al humano]        │
       ▼                                     │                                ▼
[Código Final Aprobado]                      ▼                [ROLLBACK a Estado A]
                                            │                                │
                                            └────► [Reintentar con restricción aprendida]
```

Esta combinación de **checkpoint + rollback de estado + presupuesto de reintentos + memoria reflexiva** es precisamente la diferencia entre un script básico que genera código y un **agente programador autónomo** capaz de resolver problemas complejos sin degradar la calidad con cada intento fallido.

---

## Resumen de matices corregidos

1. **Separar "búsqueda en árbol (ToT)" de "rollback de estado"**: el agente real revierte artefactos, no su razonamiento.
2. **Añadir retry budget (máx 3)**: el backtracking sin límite degenera en bucles; al agotar el presupuesto se escala al humano.
3. **Añadir análisis de causa raíz antes de reintentar** (Lógica / Entorno / Recursos), para no repetir el error con otra forma.
4. **Distinguir verificación (tests/lint) de validación de entradas/salidas esperadas**; ambas deben ser deterministas.
5. **Fail loudly**: ante una salida no conforme, detenerse y diagnosticar en lugar de parchear sobre código roto.
6. **La memoria reflexiva es lo que da el salto cualitativo a futuro**; idealmente integrada además en SOPs/registros de errores acumulativos, no solo en recuerdos sueltos.