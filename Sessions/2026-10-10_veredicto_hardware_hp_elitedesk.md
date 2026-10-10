# 2026-10-10 — veredicto_hardware_hp_elitedesk

## Tema
Emitir un veredicto sobre si el HP EliteDesk 805 G6 Mini PC (Ryzen 5 PRO 4650GE,
16 GB, SSD 512 GB) sirve para el proyecto ELECTRONICA, y dejarlo como documento
LaTeX infográfico en `docs/PC_PARA_IA/`.

## Contexto
- El usuario puso a consideración el listado de compra `docs/PC_PARA_IA/HP_ELITEDESK.txt`
  ($279,99 + $168,73 de envío/importación a Venezuela = $448,72 puestos en el país)
  y preguntó si servía para el proyecto.
- Insumos de continuidad recuperados: `Sessions/2026-09-26_capacidad_hardware_pc_ml.md`
  (política: entrenamiento SIEMPRE en Colab con TensorFlow; inventario del equipo
  actual Celeron N4020 con solo SSE4.1/4.2, 3,63 GB RAM) y
  `Sessions/2026-10-05_freecad_mcp_proyecto_aplazado.md` (FreeCAD GUI aplazado por RAM,
  no por software).
- Documentos hermanos existentes en la carpeta: `PC_IA.tex` (Ryzen 5 5500, $809) y
  `PC_IA_B650_WORKSTATION.tex` (Ryzen 7 7700X + B650, $995). El veredicto debía leerese
  como un tercer documento de la misma familia y estilo.

## Decisiones (usuario)
1. Preparar el veredicto como documento LaTeX en `docs/PC_PARA_IA/` (el usuario lo
   pidió explícitamente tras el análisis en el chat).
2. No se pidió commit; no se commiteó (regla global: solo con petición explícita).
3. **Compra: se elige la Unidad B** (HP EliteDesk 805 G6, 256 GB, **$340** total en un
   local comercial en Venezuela). Disponible la próxima semana: empezar a trabajar sin
   esperar importación. Contrapartida aceptada: disco de 256 GB (se gestiona con el
   segundo slot del chasis y los datos pesados fuera del disco de sistema).

## Actividades
- Análisis del equipamiento: el Ryzen 5 PRO 4650GE es Zen 2, **6C/12T**, TDP 35 W, con
  **AVX2 + FMA3** (el punto decisivo frente al Celeron actual, que provoca `SIGILL` con
  wheels modernas de TF) y iGPU **Radeon Vega 6** sin ROCm.
- Señalado un error de la ficha de Amazon: declara gráficos "Intel UHD Graphics 630",
  imposible en un Ryzen (mezcla con la variante Intel EliteDesk 800 G6); el caché
  declarado (9 MB) también está inflado (son 8 MB).
- Redactado `docs/PC_PARA_IA/HP_ELITEDESK_VEREDICTO.tex` replicando el preámbulo
  infográfico inline de `PC_IA.tex` (mismo `\bandaTitulo`, `tarjetaDato`, `cajaFortaleza`,
  etc.) para mantener la coherencia de la carpeta. 9 secciones: resumen ejecutivo, la
  oferta, ficha del procesador, comparación con el equipo actual, qué desbloquea,
  limitaciones/advertencias, comparación con las propuestas del repo, veredicto final y
  verificación al recibir el equipo.
- Compilado con `pdflatex` (3 pasadas, `-halt-on-error`) desde `docs/PC_PARA_IA/`:
  exit 0 en las 3. Auxiliares (`.aux/.log/.out/.toc`) eliminados.
- Verificación determinista: `execution/verificar_pdf.py --pdf` →
  `{"status": "ok", "paginas": 6, "errores": [], "overfull": [], "solapes": [], "solapes_total": 0}`.
  El log no tiene errores `!`; solo un `Overfull \hbox` de 3 pt en el banner del título
  (cosmético, según `.agent/latex.md`) y unos `Underfull` en el `lstlisting` de comandos.

## Ampliación: segunda unidad de 256 GB (misma sesión)
- El usuario presentó una **segunda unidad** del mismo modelo: HP EliteDesk 805 G6,
  Ryzen 5 PRO 4650GE, 16 GB, **SSD 256 GB**, **$340**. **Confirmado (usuario):** está en
  un local comercial en Venezuela → **$340 es el total, sin envío ni importación**
  (compra inmediata, sin aduana), frente a los $448,72 de la Unidad A (importación).
- Verificado por web que el 805 G6 Mini admite 4350GE/4650GE/4750GE (todas Zen 2 con
  AVX2) + 1× M.2 2280 PCIe 3.0 y/o bahía 2,5'' SATA3 → el disco de 256 GB **es ampliable**.
- **Decisión (usuario):** ampliar el veredicto existente (no crear doc aparte) y tratar
  ambas variantes como Unidad A (512 GB) y Unidad B (256 GB).
- Ediciones aplicadas a `HP_ELITEDESK_VEREDICTO.tex`: resumen ejecutivo con las dos
  unidades; tabla de la oferta y **tabla comparativa A/B** en §2; fila de almacenamiento
  en §4; bullet "almacenamiento ampliable" en §5; **caveat de disco reforzado** en §6
  (el 256 GB queda al tamaño del disco actual ya al 91 %); dos filas en la comparación del
  repo (§7); veredicto (§8) con recomendación A vs B (mitad de precio casi igual).
- Recompilado (`pdflatex` ×3, exit 0), auxiliares borrados; `verificar_pdf.py` →
  `{"status": "ok", "paginas": 7, "errores": [], "overfull": [], "solapes": [], "solapes_total": 0}`.
- Corregido que el precio de la Unidad B es **total** (sin desglose de envío): el doc
  ahora refleja el canal de compra (local vs importación) en §1, tabla de §2, tabla A/B
  (fila `Disponibilidad`), `cajaConcepto` de §2 y el veredicto de §8.

## Veredicto emitido
- **Sí sirve** como nodo de desbloqueo: corrige la falta de AVX2, cuadruplica la RAM y
  triplica los núcleos a mitad de precio que las builds del repo; habilita la GUI de
  FreeCAD (ruta B aplazada) y la inferencia/prototipos locales con TF.
- **No entrena** (política: Colab) y **no amplía cómputo local** (mini PC sin ranura de
  GPU); 16 GB es el mínimo cómodo, no holgado. Requiere instalar Linux (viene con
  Windows 11 Pro). Equipo renovado.

## Pendientes
- ~~Decisión de compra del usuario~~ → **hecha: Unidad B** (256 GB, $340, local en VE).
- Al recibirla (próxima semana): confirmar en el local que la CPU es la **4650GE** (no
  la 4350GE) antes de cerrar la compra; luego correr `execution/env_diagnostic.py`
  (confirmar AVX2) y `flujo_auditar_sistema.py` (veredicto RAM/servicios) — criterio de
  aceptación anotado en el documento.
- Instalar Linux (el equipo viene con Windows 11 Pro) y replicar el entorno (conda
  `elect_env`, node vía nvm, `.env` recreado — checklist de migración en AGENTS.md).
- Valorar un segundo SSD (M.2 2280 / 2,5'') temprano para el disco de 256 GB y mantener
  modelos/datasets/`chroma_db` fuera del disco de sistema.
- No se commiteó (sin petición explícita). Archivos nuevos sin commitear:
  `docs/PC_PARA_IA/HP_ELITEDESK_VEREDICTO.{tex,pdf}` y esta bitácora.
- Elección A vs B: la Unidad A (512 GB, $448,72) evita la ampliación inmediata; la
  Unidad B (256 GB, $340 local) se eligió por disponibilidad inmediata y cero importación.
