# 2026-08-22 — Migración de chat_id autorizado del Telegram Gateway

**Tema:** Reemplazo del dispositivo autorizado para consultar el bot "Agente IA ELECTRONICA".

## Contexto
- El usuario cambió de celular; el ID antiguo `1315284048` quedó obsoleto.
- Archivo de configuración: `directives/telegram_gateway.yaml` → `configuration.security.allowed_chat_ids`.
- El control de acceso vive en `flujo_telegram.py:28` (`chat_id not in allowed_ids`, pertenencia estricta, **sin comodines**: un `"*"` en la lista denegaría a todos).

## Actividades
1. Revisión de logs: el stdout de Python del servicio (prints "Message from"/"Acceso denegado") no llega al journal por buffering — no sirve para capturar IDs.
2. Se activó el modo descubrimiento nativo (`flujo_telegram.py:24-25`): lista vacía → el bot responde a cualquier remitente solo con su chat_id, sin ejecutar comandos.
3. Usuario obtuvo su nuevo ID desde el celular nuevo y lo reportó.

## Decisión
- `allowed_chat_ids` final: `[8671067338]` (ID viejo eliminado).

## Pendientes
- [x] Usuario: reiniciar servicio (`sudo ./manage_bot.sh` opción 3) y probar `/ping` desde el celular nuevo. **Verificado funcionando por el usuario (2026-08-22).**
