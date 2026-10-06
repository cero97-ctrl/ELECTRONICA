# 2026-10-06 — pdf_referencia_terceros

## Tema
Carpeta canónica `docs/REFERENCIA/` para PDFs de terceros descargados de
internet, excluidos de la dimensión `pdf_stale` por ruta.

## Contexto
La dimensión `pdf_stale` (7 nuevas de `flujo_auditar_repo.py`) marcaba como
huérfanos a PDFs de LaTeX sin `.tex` de mismo nombre. El discriminador por
metadatos (`MOTORES_LATEX = pdftex/luatex/xetex`) separa libros y escaneos de
terceros, pero NO distingue un paper de arXiv de un informe propio: ambos son
pdfTeX. Medido en el repo: 29 PDFs de terceros NO-TeX ya ignorados por la
heurística; 0 hechos con TeX (hueco prospectivo); y 3 huérfanos **propios** que
causaban el `aviso` real de `pdf_stale`.

## Decisiones (usuario)
1. Plan aprobado ("procede con el plan"): carpeta `docs/REFERENCIA/`,
   política **gitignore**, **sin migrar** los 29 PDFs de terceros ya dispersos.
2. Sobre los 3 huérfanos propios: primero respondió "No borrar ninguno" vía
   pregunta, y acto seguido cambió a **"borra los 3 PDFs"** (decisión
   final: borrar). Borrados los 3.
3. Commit NO pedido — las 3 borradas y la carpeta nueva quedan en `git status`
   pendientes de la decisión del usuario (flujos `update_repo.sh`).

## Actividades
- `python3 execution/estado_sesion.py check` → ok; bitácora creada con
  `bitacoras.py nueva`.
- **docs/REFERENCIA/README.md** creado: política de la carpeta (git ignorada,
  auditoría cuenta por ruta, RAG sí la indexa, `flujo_disco.py` la trata como
  intocable).
- **.gitignore**: `docs/REFERENCIA/**` + `!docs/REFERENCIA/README.md`
  (verificado con `git check-ignore -v`: solo el README es visible).
- **Capa 3 — `execution/auditar_repo.py`**: `RUTAS_REFERENCIA = ("REFERENCIA",)`;
  helper `_es_referencia(rel)` (match por componente de Path, igual que
  `_es_vendida`); en `comprobar_pdf_stale` la rama de huérfanos excluye esas
  rutas y las cuenta en `evidencia.pdf_referencia`; repo solo-REFERENCIA →
  `no_verificado` (nunca `ok`).
- **Tests**: 10 aserciones nuevas en `test_auditar_repo.py` (exclusión por
  ruta, match por componente, coexistencia con huérfano propio fuera,
  solo-REFERENCIA → no_verificado con conteo). Suite: **175 aserciones, 0
  fallos**.
- **Capa 1 — `directives/auditar_repo.yaml`**: `pdf_stale.que_mide`
  ampliado a sus 3 derivas + exclusión por ruta; edge case
  `pdf_referencia_excluido` (3 guardas: conteo siempre visible, solo aplica a
  huérfanos, referencia ≠ sanidad de entregables). YAML validado con
  `yaml.safe_load`; `comprobar_directivas` sigue en su `aviso` preexistente
  (11 referencias en directivas `planificado`).
- **Verificación completa**: `flujo_auditar_repo.py` → 14 dimensiones,
  157,6 s, veredicto `con_avisos` (ningún cambio de estado), texto y
  entornos en ok.
- **Borrado de los 3 huérfanos** (con visto bueno): `docs/MANUAL/manual-2.pdf`
  (duplicado viejo de `manual.pdf` oct 5), `IoT-con-Aeduino-y-ESP32.pdf`
  (typo, ya existe `IoT-con-Arduino-y-ESP32.{tex,pdf}`), `practica-2.pdf`
  (nombre viejo sin `.tex`; su par real es `practica_11-1.pdf`).
- **Verificación tras borrar**: `flujo_auditar_repo.py --dimension pdf_stale`
  → **ok** — "los 180 pares .tex/.pdf estan al dia", exit 0.

## Pendientes
- Commit de todo esto (bitácora incluida) cuando el usuario lo pida;
  `git status` muestra las 3 borradas + `docs/REFERENCIA/README.md` sin trackear.
- `AGENTS.md` (Commands) aún dice "134 aserciones" para
  `test_auditar_repo.py`; hoy son 175.
