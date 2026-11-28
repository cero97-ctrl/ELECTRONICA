# 2026-11-28 — publicar_cuestionarios_telegram

## Tema
Publicación de los cuestionarios SEMANA_02 de Ciberseguridad ordenada desde la cuenta Telegram del usuario, mediante `agente_electronica_bot`.

## Contexto
- El sitio `cero97-ctrl/cuestionarios-ciberseguridad-s02` quedó **oculto** al cierre de la sesión anterior (repo `private`, Pages `false`, HTTP 404).
- El usuario pidió publicar desde su Telegram. El gateway `flujo_telegram.py` ya estaba activo (`/ping` → «Pong! El Gateway está activo y escuchando») y sólo reconocía `/start`, `/help`, `/ping`, `/diagnostico` y `/latex`.
- Se aplicó el guardrail determinista: NO meter la decisión en el chat. Se alertó al usuario y éste eligió **comando fijo** y **doble confirmación**.

## Decisiones (usuario)
1. La instrucción llega como **`/publicar`** (comando fijo), no como lenguaje natural interpretado por el asistente.
2. La publicación exige **dos pasos**: `/publicar s02` prepara y muestra el dry-run; `/confirmar s02 <token>` ejecuta el push y el cambio de visibilidad. Un `/confirmar` aislado no publica.
3. Alcance: los cuatro roles de SEMANA_02; se reutiliza el repo y el publicador existentes, sin duplicar la barrera anti-fuga.
4. Se mantiene el sitio oculto hasta que el usuario envíe personalmente los comandos desde su Telegram.

## Actividades
- **Capa 3** `execution/telegram_publicar.py`: vocabulario cerrado (`s02` → `web_dir`/`repo` fijos), validación de `chat_id` contra `allowed_chat_ids`, token HMAC-SHA256(`chat_id|curso|nonce`) de 16 hex con ventana de 900 s y `compare_digest`, construcción del argv sin shell y delegación en `flujo_publicar_cuestionario.py`. Códigos: 0 ok · 2 comando/token inválido · 3 chat no autorizado · 4 fallo del publicador.
- **Capa 2** `flujo_telegram.py`: nuevos comandos `/publicar` y `/confirmar` que solo analizan y delegan; `/help` actualizado. Los comandos existentes quedan intactos.
- **Capa 1** `directives/telegram_publicar_cuestionario.yaml` (SOP nuevo) y extensión de `directives/telegram_gateway.yaml` con `confirm_window_seconds: 900` y el mapeo de los comandos.
- **Barrera de reinicio**: el offset de Telegram se guardaba sólo en memoria, así que reiniciar el servicio podía reprocesar un `/confirmar` antiguo. Añadidas `leer_offset()`/`guardar_offset()` en `execution/telegram_api.py` (escritura atómica en `.tmp/telegram_offset.txt`) y persistencia antes de procesar cada update. Los updates pendientes se drenaron (0) antes de reiniciar; systemd relanzó el servicio con `Restart=always` (sin sudo interactivo) y quedó `active`.
- **Verificación**: `execution/test_telegram_publicar.py` 11/11 sin red (chat, texto libre, ruta inyectada, token caducado, token de otro chat, argv sin shell, resumen sin clave ni rutas, persistencia del offset); YAML y gateway importan bien; dry-run real devolvió los 4 `*_alumno.html` con los SHAs ya conocidos (`fe6d8c8…`, `323ee39…`, `3b91f6b…`, `d35cb16…`) y `publicado: false`; `/confirmar s02 tokenmalo123456` se rechazó con código 2 y sin efectos.
- El bot ya corre con el código nuevo; falta que el usuario pruebe `/ping` y `/publicar s02` desde su Telegram.
- **Incidente de commit corregido**: `update_repo.sh` hace `git add -A` y metió en el primer commit (`ae6f3dc`) los archivos ajenos del usuario (`cursos/LABORATORIO_I_FISICA/practicas/web/` y `publicar_lab1_practicas_web.sh`), aunque no se tocaron en disco. Se corrigió con `git reset --soft HEAD~1` + `git restore --staged` de esas rutas + nuevo commit (`0170908`) + `git push --force-with-lease`. Aprendizaje: con trabajo ajeno untracked en el árbol, **no usar `update_repo.sh` sin revisar**: hacer `git add` explícito y `git commit` directo (la divergencia ya era `0 0`).

## Pendientes
- Usuario: enviar `/ping` y `/publicar s02` desde su cuenta autorizada; revisar el resumen del dry-run; si decide publicar, enviar `/confirmar s02 <token>` recibido.
- Tras publicar: verificar visibilidad y URL, y volver a ocultar con `flujo_publicar_cuestionario.py --visibilidad private`.
- Tests finales, `bitacoras.py check`, commit y push.
- NO tocar `cursos/LABORATORIO_I_FISICA/practicas/web/` ni `publicar_lab1_practicas_web.sh`: son trabajo ajeno del usuario, sin versionar.
