# docs/REFERENCIA — material de terceros

Carpeta canónica para **PDF descargados de internet** (papers, libros, datasheets,
apuntes, slides): material de consulta que **no es un entregable de este repo**.

## Qué va aquí

- Cualquier PDF de terceros que se quiera conservar como fuente de consulta.
- Subcarpetas por tema permitidas (`docs/REFERENCIA/<TEMA>/libro.pdf`).

## Qué NO va aquí

- PDFs generados por el proyecto: esos viven **junto a su `.tex`** en
  `docs/<TEMA>/` (la auditoría `pdf_stale` exige que el par exista y esté al día).
- Escaneos de entregas de alumnos (`ELECTRONICA_ENTREGAS/`) ni prácticas de curso.

## Política (decidida 2026-10-06)

| Dimensión | Qué pasa con esta carpeta |
|---|---|
| **git** | Gitignorada (`docs/REFERENCIA/**`, excepto este README): no viaja en el clone, no engorda `.git` ni dispara `peso_git`. Son re-descargables. |
| **Auditoría `pdf_stale`** | Los PDF de aquí se **excluyen por ruta** (`RUTAS_REFERENCIA` en `execution/auditar_repo.py`) y se reportan como conteo aparte (`evidencia.pdf_referencia`), nunca escondidos. Para que la exclusión funcione, la ruta debe contener el componente exacto `REFERENCIA`. |
| **RAG** | `rag_system.py` **sí** los indexa a propósito (`**/*.pdf`); el material de consulta entra en la base vectorial local (`chroma_db/`, gitignorada). |
| **Disco** | `docs/` es ruta estructural en `flujo_disco.py`: nunca se purga. |

## Migración a otra PC

Al clonar el repo esta carpeta llega **vacía** (solo el README). Copiarla a mano
desde la máquina origen o re-descargar los PDF según convenga.
