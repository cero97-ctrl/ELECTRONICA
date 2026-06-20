# Directrices para Proyectos de Internet de las Cosas (IoT)

- **Stack Tecnológico:** Python, Raspberry Pi, frameworks web (Flask), servicios en la nube (AWS EC2) y plataformas en tiempo real (PubNub).
- **Protocolos de Comunicación:** Priorizar protocolos en tiempo real, ligeros y bidireccionales como MQTT y WebSockets por encima de técnicas como AJAX *long-polling*. Seguir el modelo Publicar/Suscribir.
- **Arquitectura de Hardware:** Enfoque en la interacción entre el mundo físico y digital a través de sensores (ej. PIR) y actuadores (ej. Zumbadores), integrando conversores y buses como SPI cuando sea necesario.
- **Seguridad (Crítico):** 
  - Es obligatorio el uso de conexiones seguras (HTTPS, certificados SSL/TLS vía Let's Encrypt).
  - Garantizar comunicación cifrada de extremo a extremo.
  - Implementar login seguro y gestión de accesos basada en roles (Usuarios Administradores vs. No Administradores) persistiendo la información en bases de datos integradas.
- **Enfoque de Solución:** Los proyectos deben apuntar a resolver problemas del mundo real (ej. Telemedicina, seguridad del hogar, monitoreo atmosférico) manteniendo un equilibrio entre el hardware y el backend/cloud.