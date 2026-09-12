# CONVERZACIóN: Skills para extracción de conocimientos de documentos y Validación Neuro-Simbólica

## 1. Entrada / Consulta Inicial

Recientemente creé un Agente IA que a partir de un documento en formato pdf extrae información para crear un skill (habilidad) que puede ser usada por un LLM para resolver problemas basándose en la teoría contenida en el documento.

## 2. Respuestas y Conceptos Claves

### Arquitectura de Extracción de Skills
Generar habilidades (*skills*) estructuradas a partir de literatura técnica o libros de texto permite a un LLM operar con **fundamento teórico preciso**, evitando alucinaciones y resolviendo problemas mediante metodologías formales en lugar de mera intuición de lenguaje.

Para que esta arquitectura pase de "responder preguntas sobre el libro" a realmente **razonar y resolver problemas complejos** basados en él, los patrones de diseño clave que estructuran estas habilidades suelen dividirse en varias etapas estratégicas:

#### Estructura clave para la representación del Skill
* **Indexación conceptual jerárquica:** No basta con extraer chunking por densidad de texto. El skill debe organizar los conceptos como un grafo de dependencias (p. ej., para entender *Ecuación de Bernoulli*, el skill debe exigir que la LLM valide primero las premisas de *Flujo Incompresible* y *Línea de Corriente*).
* **Plantillas de Razonamiento (Reasoning Templates):** Extraer los algoritmos paso a paso que utiliza el autor del documento para resolver ejercicios tipo. La habilidad no solo guarda teoría, guarda la *metodología de resolución*.
* **Restricciones y Condiciones de Borde (Boundary Conditions):** Extraer explícitamente cuándo **no** aplica una fórmula o teorema. Esto previene que el LLM aplique modelos teóricos en contextos donde la física o la lógica del documento fallan.
* **Formatos de Entrada/Salida Unificados:** Convertir las ecuaciones o reglas del documento en representaciones formales (como bloques de código ejecutable, reglas en formato JSON o especificaciones explícitas) para que la LLM pueda invocar herramientas externas (ej. compiladores de Python o solucionadores simbólicos) al aplicar el skill.

#### Flujo de Ingesta y Ejecución
```text
[Documento] ──> [Extracción Teórica y Reglas] ──> [Skill Estructurado (JSON/Markdown)]
                                                              │
[Problema del Usuario] ──> [Agente / LLM] <────────────────────┘
                               │
                               ├──> 1. Valida condiciones de aplicabilidad
                               ├──> 2. Ejecuta plantilla de razonamiento
                               └──> 3. Emite solución verificada
```

## 3. Generación de Nuevo Conocimiento

Puede un LLM generar conocimiento nuevo basado en los concimientos adquiridos del documento?

**Respuesta:**  
La respuesta corta es **no en el sentido estricto de la ciencia**, pero **sí en el sentido sintético e deductivo**. 

Un LLM no posee capacidad introspectiva ni "comprensión" biológica para generar descubrimientos teóricos totalmente inéditos por sí solo. Sin embargo, al combinar la teoría del documento con una estructura de *Skill* adecuada, puede lograr lo que formalmente se conoce como **inferencia deductiva, síntesis no trivial e interpolación compleja**.

### Lo que SÍ puede hacer (Inferencia y Síntesis)
1. **Deducción lógica sobre casos no vistos:** Si el documento establece los Principios $A$ y $B$, el LLM puede deducir la consecuencia $C$ para un problema específico que **nunca apareció en el texto original**, siempre que $C$ sea una consecuencia lógica inevitable de las premisas.
2. **Transferencia de analogías y dominios:** Puede aplicar la estructura matemática o metodológica descrita en el documento a un problema en otro campo que comparta el mismo isomorfismo formal (por ejemplo, aplicar un modelo de dinámica de fluidos a la optimización de tráfico de redes).
3. **Descubrimiento por Combinatoria Conceptual:** Al conectar un concepto de la página 50 con una condición límite de la página 300, el agente puede formular una solución que el autor del documento no escribió explícitamente, pero que estaba implícita en la teoría.

### Lo que NO puede hacer (Conocimiento Nuevo Real)
* **Inducción Epistemológica:** No puede crear nuevos paradigmas científicos ni formular leyes fundamentales que trasciendan los axiomas del libro.
* **Validación Empírica:** No puede verificar si sus deducciones son verdaderas en el mundo real sin experimentación o herramientas de simulación externa.
* **Salida del Espacio de Estados:** El modelo opera dentro del "espacio de hipótesis" delimitado por los datos con los que fue entrenado y las reglas introducidas en la habilidad.

### Matriz de Clasificación del Conocimiento

| Tipo de Conocimiento | ¿Lo genera el LLM con el Skill? | Mecanismo |
| :--- | :--- | :--- |
| **Nuevo Descubrimiento Científico** | ❌ **No** | Requiere observación empírica y formulación axiomática original. |
| **Solución Inédita a un Problema** | ✔ **Sí** | Recombinación lógica y aplicación de algoritmos del libro a nuevas condiciones iniciales. |
| **Síntesis y Demostración** | ✔ **Sí** | Cadenas de razonamiento deductivo basadas en los teoremas provistos. |

En resumen: el agente no inventa nueva ciencia, pero **extrapola y aplica la teoría existente a escenarios inéditos** a una velocidad y profundidad que simula la resolución creativa de problemas.

## 4. Integración Neuro-Simbólica (SymPy / Z3)
  
¿Cómo se pueden integrar solucionadores simbólicos (como SymPy o Z3) con el LLM para validar formalmente las deducciones generadas desde el skill?

**Respuesta:**  
Para validar formalmente las deducciones de un LLM utilizando la teoría del documento, la clave radica en **separar el razonamiento cualitativo de la verificación lógica**. El LLM actúa como el "traductor/formulador" de la teoría a código formal, mientras que el solucionador simbólico (SymPy o Z3) actúa como el "oráculo riguroso" que ejecuta y valida las matemáticas o la lógica de forma determinista.

### Patrón de Arquitectura: Neuro-Simbólico en 3 Pasos

```text
[Problema + Skill] ──> [LLM (Formulador)] ──> [Código Formal (Python/SMT-LIB)]
                                                          │
                                                  [Solucionador Exec]
                                                          │
                                            ┌─────────────┴─────────────┐
                                            ▼                           ▼
                                      [Éxito / Proof]            [Error / Unsat]
                                            │                           │
                                     [Respuesta Final]         [Bucle de Reflexión]
```

### Integración Paso a Paso

1. **Traducción a Dominio Formal (LLM)**  
   El LLM toma la consulta y la habilidad extraída del libro. En lugar de calcular el resultado final directamente, genera un script ejecutable o especificación lógica:
   * **Para SymPy (Matemática/Física):** Declara variables explícitas, define ecuaciones diferenciales o algebraicas, e impone restricciones de dominio ($x > 0$, $t \ge 0$).
   * **Para Z3 (Satisfacibilidad y Reglas Lógicas):** Modela axiomas, precondiciones y postcondiciones usando variables de lógica booleana, entera o real (`z3.Solver()`).

2. **Ejecución en Sandbox Aislado**  
   Un entorno de ejecución (REPL de Python o proceso Z3) evalúa la validez del script generado.
   * **SymPy:** Resuelve símbolos mediante `sympy.solve()`, simplifica expresiones con `sympy.simplify()`, o verifica identidades con `sympy.equals()`.
   * **Z3:** Ejecuta `solver.check()`. Si la salida es `sat` (satisfacible), extrae el modelo matemático; si es `unsat`, demuestra formalmente que las premisas o deducciones son inconsistentes.

3. **Bucle de Realimentación y Reflexión (Self-Correction Loop)**  
   Si el solucionador arroja un error de sintaxis, una inconsistencia matemática o `unsat`:
   * El traceback o estado de error de Z3/SymPy se inyecta de vuelta al prompt del LLM.
   * El LLM ajusta las ecuaciones o las restricciones lógicas y reintenta la generación sin alucinar sobre los cálculos.

### Comparativa de Solucionadores para la Validación de Skills

| Solucionador | Caso de Uso en la Habilidad | Tipo de Validación |
| :--- | :--- | :--- |
| **SymPy** | Cálculo simbólico, física, álgebra, matrices y ecuaciones diferenciales. | **Exactitud matemática:** Garantiza derivaciones algebraicas exactas sin errores aritméticos. |
| **Z3 (SMT Solver)** | Reglas de negocio, condiciones de borde, verificación de consistencia axiomática. | **Consistencia lógica:** Comprueba si un conjunto de reglas teóricas entra en contradicción o si una propiedad se cumple formalmente. |
