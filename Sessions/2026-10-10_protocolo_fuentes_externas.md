# 2026-10-10 — protocolo_fuentes_externas

## Tema
Convención ad-hoc de **triage de fuentes externas**: carpeta canónica
`docs/AGENTE_IA/fuentes/` y cabecera de procedencia obligatoria, aplicada al doc
CLM (`clm-meta-context-language-model.md`).

## Contexto
- El usuario estableció su forma de trabajar: convierte material de internet
  (YouTube, GitHub, etc.) a markdown para analizarlo en conjunto y decidir si
  algo aporta **sin romper la estructura determinista** del proyecto.
- Ya existía `docs/REFERENCIA/` (PDFs de terceros, **gitignorada**) pero no una
  convención para **markdown pequeño y analizable**. El caso inmediato fue el doc
  CLM (sesión `2026-10-10_analisis_doc_clm_meta`), que se marcó como fuente
  secundaria no citable **sin cabecera de procedencia y sin ubicar**.
- Origen del doc CLM aportado por el usuario:
  `https://youtu.be/9_H3OLNQN-U?si=M-THdri3W42CgOdz` (video de YouTube;
  fuente primaria real: `https://arxiv.org/abs/2609.37725`).

## Decisiones (usuario)
1. **Alcance: ad-hoc** (opción C). **Sin directiva ni validador propios**; el
   protocolo se aplica caso por caso, como con el doc CLM.
2. **Ubicación:** `docs/AGENTE_IA/fuentes/`, **versionada** (viaja en el clone).
3. **Cabecera de procedencia:** introducirla **ya** y **retro-aplicarla** al doc
   CLM ya commiteado.
4. **Reversión explícita:** la decisión previa de la sesión
   `analisis_doc_clm_meta` ("el `.md` queda intacto, sin cabecera") **se revierte**
   en esta sesión: ahora sí se le añade cabecera y se mueve a `fuentes/`.
5. Commit y push al cerrar.

## Actividades
- `docs/AGENTE_IA/fuentes/README.md` creado: naturaleza (conversión de fuente
  externa, no entregable), política (versionada; secundaria salvo `citable: sí`),
  y **plantilla de la cabecera de procedencia**.
- `git mv` del doc CLM a `docs/AGENTE_IA/fuentes/` (preserva historia).
- Cabecera de procedencia (front-matter YAML) añadida al doc CLM con:
  `origen` (URL del video), `fuente_primaria` (arXiv), `tipo_fuente: video`,
  `fecha_captura: 2026-10-10`, `fecha_fuente: 2026-09-29`,
  `autor_declarado: "Rin Xia et al."`, `autor_verificado: no`,
  `citable: no`, `estado: analizado`, `analisis: <bitácora>`. Más un aviso
  textual que corrige la atribución errónea del propio texto.
- Ruta del doc CLM corregida en `Sessions/2026-10-10_analisis_doc_clm_meta.md`
  (de `docs/AGENTE_IA/...` a `docs/AGENTE_IA/fuentes/...`) + nota de reversión.

### Gate de determinismo (checklist de trabajo, ad-hoc)
Al evaluar CUALQUIER hallazgo de una fuente externa, antes de proponer adoptarlo:
1. ¿Mete lógica de decisión en el prompt/chat? → rechazar/adaptar.
2. ¿Rompe reproducibilidad (mismo input ≠ output)? → rechazar.
3. ¿Se salta I/O validadas, retry (máx 3) o la barrera anti-borrado? → rechazar.
4. ¿Introduce estado persistente escribible por el modelo / inyección? → rechazar.
5. ¿Duplica un mecanismo existente? → descartar por redundancia.
6. ¿Viola política de hardware/créditos? → rechazar.
Nada se adopta desde el chat: si algo pasa el gate, se implementa por las **3
capas** (directiva + orquestador + script) y con aprobación del usuario.

## Pendientes
- La parte no determinista de CLM (autoedición del contexto por el modelo)
  **queda descartada** (ver `analisis_doc_clm_meta`); no se implementa nada.
- El protocolo sigue **ad-hoc**: si el volumen de fuentes crece, reevaluar
  formalizarlo como directiva de 3 capas + `execution/validar_fuente.py`.
