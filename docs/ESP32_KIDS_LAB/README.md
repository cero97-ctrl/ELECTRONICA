# ESP32 Kids Lab 🚀🧪

## Descripción General
**ESP32 Kids Lab** es una plataforma educativa interactiva diseñada para que los niños exploren conceptos básicos de electrónica, sensores y actuadores. El proyecto convierte un ESP32 en un laboratorio de bolsillo autónomo, exponiendo una red Wi-Fi propia (SoftAP) y un servidor web interactivo con un diseño moderno y amigable.

## Características Principales
* **Conexión Directa:** El ESP32 crea su propia red Wi-Fi (`Laboratorio ESP32`) por lo que no requiere internet ni un router externo.
* **Interfaz Web Moderna:** Creada con HTML5, CSS3 y JavaScript puro. Se sirve directamente desde la memoria flash del ESP32 usando **LittleFS**.
* **Sensores en Vivo:** Lectura en tiempo real de Distancia, Luz y Temperatura.
* **Control de Actuadores:** Interruptores en la web para encender y apagar LEDs de colores, un Relé y un Buzzer.
* **Taller Mágico (Display 7 Segmentos):** Resuelve sumas matemáticas desde la web y el resultado aparece mágicamente en el display físico TM1637.
* **Estudio Pixel Art (Matriz NeoPixel):** Una cuadrícula interactiva de 4x4 en la web que permite pintar y dibujar en tiempo real sobre una matriz física de LEDs WS2812.

## Mapa de Pines (Hardware Pinout)

A continuación se detalla la asignación de pines (GPIO) del ESP32 utilizados en el proyecto:

| Componente | Tipo | Pin (GPIO) | Notas |
| :--- | :--- | :--- | :--- |
| **LED Rojo** | Actuador / Salida | `1` (TX) | Ojo: Su uso desactiva la salida de texto del Monitor Serial. |
| **LED Verde** | Actuador / Salida | `23` | |
| **LED Azul** | Actuador / Salida | `19` | |
| **LED Amarillo** | Actuador / Salida | `3` (RX) | |
| **Relé** | Actuador / Salida | `0` | Control de cargas (escuchar el "clic"). |
| **Buzzer** | Actuador / Salida | `12` | Requiere activar el Switch 1 en la placa. |
| **Trigger (HC-SR04)** | Sensor / Salida | `5` | Pin de disparo ultrasónico. |
| **Echo (HC-SR04)** | Sensor / Entrada| `18` | Pin de eco ultrasónico. |
| **LDR** | Sensor / Entrada Analógica | `34` | Fotorresistencia (medición de Luz). |
| **LM35** | Sensor / Entrada Analógica | `35` | Sensor de temperatura. |
| **CLK (TM1637)** | Actuador / Reloj | `27` | Reloj para el display de 7 segmentos. |
| **DIO (TM1637)** | Actuador / Datos | `14` | Datos para el display de 7 segmentos. |
| **Matriz NeoPixel**| Actuador / Datos | `13` | Control para la Matriz WS2812 de 16 LEDs. |

## Arquitectura de Software

El proyecto se divide claramente en Backend (C++ en ESP32) y Frontend (Web en LittleFS):

### Backend (ESP32 - PlatformIO)
* **Framework:** Arduino Core para ESP32.
* **`ESPAsyncWebServer`:** Maneja las peticiones HTTP de forma asíncrona, permitiendo servir la interfaz web y responder a las APIs REST sin bloquear el ciclo principal del procesador.
* **API REST (`main.cpp`):**
  * `GET /api/sensors`: Devuelve un objeto JSON con los valores actuales de distancia, luz y temperatura.
  * `POST /api/actuators`: Recibe un JSON booleano para encender/apagar de forma independiente los LEDs, el Relé y el Buzzer.
  * `POST /api/display`: Recibe un número para mostrarlo directamente en el módulo TM1637.
  * `POST /api/matrix`: Interfaz avanzada para la matriz NeoPixel. Recibe comandos para limpiar (`{"clear": true}`), pintar todo de un color (`{"r":255, "g":0, "b":0}`), o un JSON array complejo con colores individuales por píxel. Incluye lógica de *buffering* estático y un `DynamicJsonDocument` de 2048 bytes para soportar payloads grandes.

### Frontend (LittleFS)
* **`index.html`:** Estructura semántica dividida en "Tarjetas" (Paneles de Sensores, Actuadores, Taller Mágico, y Pixel Art).
* **`style.css`:** Sistema de diseño basado en variables CSS (`--bg-gradient`, `--card-bg`). Utiliza flexbox, grillas (CSS grid) y animaciones suaves (hover y transiciones) para generar una experiencia *Premium* inspirada en el efecto Glassmorphism.
* **`app.js`:** 
  * Ciclo de *polling* automático (cada 2 segundos) para consultar `GET /api/sensors` y actualizar las barras de progreso.
  * Funciones de envío asíncrono (Fetch API) para controlar cada dispositivo sin recargar la página.
  * Lógica y estructura de datos para el Pixel Art, incluyendo manejo de colores activos y envío del array de píxeles al ESP32.

## Dependencias (Libraries)
Las bibliotecas utilizadas en `platformio.ini` son:
- `me-no-dev/ESP Async WebServer`: Para el servidor web asíncrono.
- `bblanchon/ArduinoJson` (v6): Para serialización y deserialización rápida de datos REST.
- `smougenot/TM1637`: Para el display de números de 4 dígitos.
- `adafruit/Adafruit NeoPixel`: Para el protocolo de la matriz de LEDs WS2812.
