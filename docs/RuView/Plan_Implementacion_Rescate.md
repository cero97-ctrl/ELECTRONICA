# RuView Rescue - Plan de Implementación

Este plan detalla el desarrollo de las dos primeras fases del proyecto RuView aplicado a la búsqueda y rescate, manteniendo estrictamente la **arquitectura de 3 capas** (Directives → Orchestration → Execution) de este espacio de trabajo.

## 1. Fase del ESP32-S3 (Firmware de Captura)

Se desarrollará el código en C/C++ (basado en ESP-IDF / Arduino) para el ESP32-S3, que actuará como nodo recolector.

**Ubicación propuesta:** `Proyectos/RuView_Rescue/esp32_node/`

**Funcionalidades del Firmware:**
- Configuración del módulo WiFi en modo promiscuo para capturar el CSI (Channel State Information).
- Lectura del acelerómetro (ej. MPU6050) vía bus I2C a una frecuencia constante.
- Empaquetado de los datos (CSI + Aceleración X, Y, Z) en una estructura binaria o JSON.
- Transmisión de los paquetes vía UDP hacia la Raspberry Pi (o PC de control) para minimizar la latencia.

## 2. Fase del Script de Filtrado y Motor Central (Arquitectura de 3 Capas)

Para la recepción y procesamiento de datos en el servidor local (Raspberry Pi/PC), se implementará la lógica siguiendo el modelo de 3 capas del espacio de trabajo:

### Capa 1: Directives (SOP)
- **Ubicación:** `directives/ruview_rescue.yaml`
- **Propósito:** Definirá el procedimiento operativo estándar (SOP) para el flujo de rescate. Incluirá parámetros de configuración como umbrales de vibración, puertos UDP, frecuencias de corte para la respiración (0.2 a 0.5 Hz) y los pasos que debe seguir el orquestador al procesar los datos.

### Capa 2: Orchestration (Agente / Orquestador)
- **Ubicación:** `flujo_ruview_rescue.py` (Directorio raíz)
- **Propósito:** Será el script principal que orquesta el sistema.
- **Acciones:**
  - Iniciará un servidor UDP para escuchar los paquetes entrantes de los nodos ESP32.
  - Delegará el procesamiento matemático y el filtrado a la Capa 3.
  - Manejará alertas y mostrará los resultados (o enviará las coordenadas a una interfaz).
  - Gestionará las excepciones si los sensores reportan "vibración crítica" (exceso de ruido de maquinaria).

### Capa 3: Execution (Scripts Deterministas)
- **Ubicación:** `execution/ruview_signal_processing.py`
- **Propósito:** Script determinista (en Python usando `numpy`/`scipy`) con una única responsabilidad: el filtrado matemático.
- **Acciones:**
  - Implementará el filtro adaptativo (ej. NLMS) para restar la firma de vibración mecánica (Acelerómetro) de las perturbaciones del CSI.
  - Aplicará la Transformada Rápida de Fourier (FFT) al residuo de la señal para buscar picos en el rango de respiración (0.2 - 0.5 Hz).

> **Nota de Implementación Inicial:**
> Para las primeras pruebas, el motor de ejecución se construirá en **Python** (como v1) para validar las matemáticas de los filtros adaptativos rápidamente con NumPy/SciPy. Una vez validada la lógica con el hardware real, este script en Capa 3 se reescribirá en **Rust** (v2) para maximizar el rendimiento en la Raspberry Pi.

## 3. Fase de Diseño de Hardware (KiCAD)
El diseño en KiCAD del PCB del nodo, que incluirá el ESP32-S3 y el acelerómetro con su debida protección contra ruidos de alimentación e interferencias mecánicas directas, se desarrollará como la fase final del proyecto.

## 4. Fase de Inteligencia Artificial (Edge AI y Escalado a Rust)
Una vez validada la recolección de datos en Python (v1), el flujo de IA se estructurará de la siguiente manera:
1. **Recolección y Entrenamiento (Python / Nube):** Se utilizará el orquestador en Python para grabar grandes volúmenes de datos CSI. Estos datasets se procesarán en la nube usando PyTorch/TensorFlow para entrenar las redes neuronales (ej. reconocimiento de posturas, aislamiento de respiración).
2. **Exportación (TFLite):** El modelo pesado se cuantizará y exportará a un formato ultraligero (como `.tflite`).
3. **Inferencia Local (Edge AI):** La Raspberry Pi cargará este modelo ligero para ejecutar predicciones en milisegundos sin necesidad de internet.
4. **Transición a Rust (v2):** Para maximizar la eficiencia en la zona de desastre, el script de ejecución (Capa 3) se reescribirá en Rust, el cual se encargará de cargar el modelo `.tflite` y procesar el flujo UDP con un mínimo consumo de CPU y RAM.
