**"Circuito de Respuesta Rápida"** o *Quiz Buzzer*. Su función principal es el "enclavamiento", lo que significa que el primer participante que presiona su botón activa su luz y bloquea automáticamente a los otros tres competidores.

Esquema electrónico detallado utilizando componentes económicos, muy fáciles de conseguir y sin necesidad de programación.

## ---

**⚙️ Esquema basado en Circuitos Integrados (Flip-Flops)**

Esta es la opción más limpia, profesional y exacta. Utiliza dos circuitos integrados **74LS74** (que contienen 2 Flip-Flops tipo D cada uno) o un **74LS373** (Octal Latch).

A continuación, te detallo el diseño utilizando **Compuertas Lógicas NAND (CD4011)** o **Flip-Flops (74LS74)**, pero la forma más sencilla y didáctica de armarlo es con **Relés** o con el famoso **CI 555 / Tiristores**.

Aquí tienes el diseño óptimo y más fácil de soldar usando **Tiristores (SCR C106)**:

                  `+9V a +12V (Alimentación)`  
                      `│`  
              `[Botón Reset (NC)]`  
                      `│`  
      `┌───────────────┴───────────────┬───────────────┐`  
      `│                               │               │  (Se repite para Estudiante 3 y 4)`  
  `[Led 1]                         [Led 2]             │`  
      `│                               │               │`  
  `[Resistencia 1k]                [Resistencia 1k]    │`  
      `│                               │               │`  
      `├───┐                           ├───┐           │`  
      `│   │                           │   │           │`  
    `Anodo │                         Anodo │           │`  
  `┌───────┴──────┐                ┌───────┴──────┐    │`  
  `│   SCR 1      │                │   SCR 2      │    │`  
  `│   (C106)     │                │   (C106)     │    │`  
  `└───────┬──────┘                └───────┬──────┘    │`  
   `Cátodo │                        Cátodo │           │`  
          `├──────────────┐                ├───────────┼───┐`  
          `│              │                │           │   │`  
          `│         [Zumbador /]          │           │   │`  
          `│          [ Buzzer  ]          │           │   │`  
          `│              │                │           │   │`  
          `│              └────────────────┼───────────┼───┤`  
          `│                               │           │   │`  
          `▼ GATES (Compuertas de activación cruzada mediante los botones)`

## **📋 Lista de Materiales (Bombas/Componentes)**

* **4 Tiristores SCR C106**: Actúan como interruptores electrónicos que se quedan encendidos al recibir un pulso.  
* **4 Botones pulsadores (Normalmente Abiertos \- NA)**: Uno para cada estudiante.  
* **1 Botón pulsador (Normalmente Cerrado \- NC)**: Para el uso exclusivo del moderador (Reset).  
* **4 Diodos 1N4148**: Para crear la línea de bloqueo.  
* **4 LEDs**: Uno de cada color para identificar al estudiante.  
* **4 Resistencias de 1 kΩ**: Para proteger los LEDs.  
* **1 Zumbador (Buzzer) piezoeléctrico de 5V o 12V**: Para la señal acústica general.  
* **1 Protoboard o baquela**: Para armar el circuito.  
* **Fuente de poder**: Una batería de 9V o transformador de 12V.

## ---

**🕹️ Cómo Funciona el Circuito**

1. **Estado de Espera**: El moderador hace la pregunta. Ningún LED está encendido.  
2. **Primer Impacto**: El estudiante 1 presiona su botón. La señal viaja a la compuerta (Gate) de su SCR 1\.  
3. **Enclavamiento**: El SCR 1 se activa, enciende su LED y activa el Buzzer común.  
4. **Bloqueo Absoluto**: Al activarse el SCR 1, satura la línea de bloqueo común a través de los diodos. Esto tumba el voltaje de los botones de los estudiantes 2, 3 y 4\. Si ellos presionan después, no pasará nada.  
5. **Liberación (Reset)**: El moderador presiona su botón "Reset" (NC), cortando momentáneamente la energía de todo el circuito. El sistema vuelve a cero para la siguiente pregunta.

## ---

**🛠️ Alternativa Moderna (Arduino)**

Si tienes conocimientos básicos de programación, puedes usar un **Arduino Uno / Nano**:

* Conectas los 4 botones a 4 pines de entrada configurados como INPUT\_PULLUP.  
* Conectas los 4 LEDs y el Buzzer a pines de salida.  
* El código bloquea las lecturas mediante una variable booleana en el primer microsegundo que detecta un cambio de estado bajo (LOW).