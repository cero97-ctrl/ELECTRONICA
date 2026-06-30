# Firmware ESP32-S3 (RuView Rescue Node)

Este directorio contendrá el código fuente en C/C++ (ESP-IDF o Arduino) para el microcontrolador ESP32-S3.

## Funcionalidad Esperada:
1.  **Captura CSI:** Configurar el chip WiFi en modo promiscuo para recolectar tramas CSI (Channel State Information).
2.  **Sensores Inerciales:** Leer datos del acelerómetro (ej. MPU6050) vía bus I2C.
3.  **Empaquetado:** Estructurar los datos (CSI + Aceleración X, Y, Z).
4.  **Transmisión:** Enviar el paquete vía UDP al servidor central (Raspberry Pi/PC) para procesamiento matemático con baja latencia.

*Nota: La implementación detallada del firmware se realizará cuando se disponga del hardware físico.*
