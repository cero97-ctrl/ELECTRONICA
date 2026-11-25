# 2026-11-25 — diagnostico_entorno

## Tema
diagnostico_entorno

## Contexto
- El usuario pidió "Diagnóstico del entorno" al iniciar la sesión (2026-11-25).
- Se aplicó el protocolo de inicio del repo: check de estado de sesión, lectura de la directiva vigente y recuperación de la bitácora anterior sobre el tema (`2026-09-27_auditar_sistema_flujo.md`) antes de medir.

## Decisiones (usuario)
1. El usuario pidió expresamente el diagnóstico del entorno; no pidió mantenimiento ni purga.
2. Se eligió `flujo_auditar_sistema.py` y NO `flujo_diagnostico.py`: la directiva `directives/auditar_sistema.yaml` aclara que el diagnóstico imprime números ("carga 1.3", "RAM 72%") mientras la auditoría emite veredicto + código de salida enmarcable. Auditar y mantener siguen separados a propósito.
3. No se ejecutó ninguna acción de mantenimiento: este flujo es solo lectura, sin sudo, sin purga, sin reinicio. Los datos del disco al 81.5% se registran como observación, no como orden de trabajo.

## Actividades
- `python3 execution/estado_sesion.py check` → `veredicto_global: ok`, `status: ok`; no hay vistas huérfanas que purgar.
- `python3 execution/bitacoras.py nueva --tema "diagnostico_entorno"` → `Sessions/2026-11-25_diagnostico_entorno.md`.
- `python3 flujo_auditar_sistema.py` → **VEREDICTO: limpio (exit 0)**, 5/5 dimensiones `ok`, 0 huecos de medición, 0.7 s, host `ZETA`, run `auditar-sistema-20261125-071313`:
  - **memoria** `ok`: RAM 70.6% usada de 3808616 kB, 1120724 kB disponibles (MemAvailable); umbrales aviso 75% / fallo 90%.
  - **intercambio** `ok`: swap en disco `/swapfile` al 4.3% de 4200444 kB; zram0 al 65.9% con compresión 4.0x — estado de diseño, NO presión (el veredicto lo lleva el swap en disco).
  - **cpu** `ok`: carga 0.32/núcleo en 5 min sobre 2 núcleos; loadavg [0.47, 0.63, 0.91]; steal 0.0%; PSI CPU `some avg60` 8.05 y `full avg60` 0.0; PSI E/S 4.53% informativo (no verdictiza).
  - **servicios** `ok`: 2/2 en pie, `telegram_gateway.service` y `waydroid-container.service` con `loaded`/`active`/`running` (consulta `systemctl show`, solo lectura).
  - **aceleración** `ok`: sin GPU discreta (Intel GeminiLake UHD Graphics 600); hecho del entorno, no defecto; entrenamiento en Google Colab con TensorFlow, aquí solo inferencia/prototipos/validación.
- `python3 execution/env_diagnostic.py` → complemento CORE/HARDWARE/RED:
  - Linux 6.8.0-151-generic x86_64, Python 3.10.20, conda `elect_env`, UTF-8, uptime 1.7 h.
  - CPU Intel Celeron N4020 @1.10 GHz, 2 núcleos; placa Lenovo LNVNB161216, BIOS DVCN20WW (05/25/2021).
  - RAM total 3.63 GB / disponible 1.03 GB / usada 71.6% (consistente con la auditoría: 70.6% vs 71.6% por el instante de la medición).
  - Disco `/` 233.18 GB, 189.94 GB usados, 31.32 GB libres (81.5%); SSD/NVMe Samsung MZALQ256HAJD-000L2 de 238.5 GB; zram filtrado correctamente como RAM comprimida.
  - Herramientas disponibles: `git`, `curl` y `pdflatex`.
- Informe completo en `.tmp/auditoria_sistema.json`; trazabilidad append-only y estado de la corrida gestionados por el propio flujo.

## Pendientes
- Ningún pendiente acordado en esta sesión. El disco al 81.5% queda como observación: si se quiere actuar, es competencia de `flujo_disco.py` / `directives/mantenimiento_disco.yaml`, no de la auditoría (que es solo lectura).
