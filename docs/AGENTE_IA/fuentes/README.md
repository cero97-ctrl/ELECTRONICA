# docs/AGENTE_IA/fuentes — conversiones de fuentes externas

Carpeta canónica para **conversiones a markdown de material de terceros**
(videos de YouTube, artículos, repos de GitHub, blogs…) que el usuario trae para
analizar en conjunto. **Es material de consulta, NO un entregable del repo ni una
especificación.**

> Distinta de `docs/REFERENCIA/` (PDFs bulky, gitignorada): aquí el material es
> markdown pequeño, útil para analizar, y **se versiona en git** para que el
> análisis sea reproducible en el clone.

## Qué va aquí

- El `.md` que resulta de convertir una fuente externa (transcripción/resumen de
  video, pegado de blog, etc.).
- Un archivo por fuente, con su **cabecera de procedencia** (ver abajo).

## Cabecera de procedencia (obligatoria, se aplica a mano)

Al inicio del `.md`, front-matter YAML:

```yaml
---
origen:          # URL exacta de la fuente (canal/artículo/repo)
fuente_primaria: # fuente real verificable, si el .md es un resumen de segunda mano
tipo_fuente:     # video | paper | blog | repo | docs
fecha_captura:   # YYYY-MM-DD en que se trajo al repo
fecha_fuente:    # YYYY-MM-DD de la fuente, si se conoce
autor_declarado: # lo que afirma el propio texto
autor_verificado: # sí | no  (¿se comprobó contra la fuente primaria?)
citable:         # sí | no    (¿es fuente primaria o resumen de segunda mano?)
estado:          # crudo | analizado | adoptado | descartado
analisis:        # ruta a Sessions/<fecha>_<tema>.md con el análisis crítico
---
```

**Por qué:** la propia fuente suele venir ya resumida (a veces por otro LLM) y
trae errores de atribución o cifras recombinadas (ver el caso CLM). La cabecera
separa *lo que dice la fuente* de *lo verificado*, para no citarla por error.

## Política (acordada 2026-10-10)

| Dimensión | Qué pasa |
|---|---|
| **git** | Versionada (a diferencia de `docs/REFERENCIA/`). Viaja en el clone. |
| **Naturaleza** | Fuente secundaria salvo que `citable: sí`; nunca se trata como especificación. |
| **Análisis** | Chat (resumen crítico + contradicciones) + veredicto en la bitácora; el "gate de determinismo" se aplica a cada hallazgo. |
| **Adopción** | Nada se adopta desde el chat: si algo se aprovecha, se implementa por las 3 capas (directiva + orquestador + script). |

Este protocolo es **ad-hoc** (sin directiva ni validador propios); se aplica caso
por caso.
