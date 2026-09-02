# Fase 1 — De un libro PDF a un skill estructurado (destilación neuro-simbólica)

> Documento de estudio. Complementa `docs/AGENTE_IA/fase2_resolver_skill.md` (Fase 2:
> resolver problemas con el skill). La Fase 1 **crea** el skill; la Fase 2 lo **usa**.
> Implementado inicialmente el 2026-08-30; robustecido (ensamblaje masivo) el 2026-09-01.
> Coste del E2E completo de un libro de 452 págs: ~$0.75.

---

## 1. Qué resuelve

Un LLM que "respondiera preguntas sobre un libro" alucina y no razona con fundamento
teórico. La Fase 1 transforma un **PDF de texto técnico** en un **skill estructurado** que
un LLM puede usar para *razonar y resolver* problemas: conserva teoría, metodologías de
resolución paso a paso, límites de aplicabilidad y prerrequisitos, todo con las fórmulas
representadas como **código SymPy ejecutable** (validable determinísticamente).

```
[PDF] ─▶ extraer_libro_pdf → texto_completo.txt ─▶ enrutador ─▶ sintetizar_skill
                                                                     │
                                             (destila chunk a chunk  │  → corpus)
                                             (ensambla 7 archivos)   │
                                                                     ▼
                                              SKILL.md + references/ (formulas,
                                              metodologías, límites, prerrequisitos,
                                              tablas, glosario)
                                                                     ▼
                                        [validar_skill_formulas → guarda/instala si OK]
                                        [generar_latex_skill → reporte PDF]
                                        [instalar_skill → ~/.config/opencode/skills]
```

---

## 2. La arquitectura de 3 capas (obligatoria)

| Capa | Archivo | Rol |
| :--- | :--- | :--- |
| **Directiva** | `directives/libro_a_skill.yaml` | SOP: 8 pasos, 13 edge cases, retry budget |
| **Orquestación** | `flujo_libro_a_skill.py` | Entrevista, orquesta scripts, gate de instalación |
| **Ejecución** | `execution/sintetizar_skill.py` (+ `extraer_libro_pdf.py`, `validar_skill_formulas.py`, `generar_latex_skill.py`, `instalar_skill.py`) | Trabajo determinista |

---

## 3. El orquestador `flujo_libro_a_skill.py`

Pasos (total depende de flags):

1. **Entrevista ligera**: tema, nombre (snake_case), idioma, alcance y confirmación de
   instalación. Se persiste en `.tmp/entrevista_skill_<nombre>.json`.
2. **Extracción** — `execution/extraer_libro_pdf.py` (determinista, 0 créditos):
   lee el PDF y produce `.tmp/libro_<nombre>_texto/texto_completo.txt`. En el E2E real:
   452 páginas, 1.6M chars, ~400K tokens.
3. **Enrutamiento determinista** — `execution/enrutador.py --task contexto_masivo`: mide
   tokens y decide tier. Para un libro completo → **deepseek** (`deepseek/deepseek-v4-pro`).
4. **Síntesis (créditos)** — `execution/sintetizar_skill.py` → 7 archivos (ver §4).
5. **Validación neuro-simbólica (0 créditos)** — `execution/validar_skill_formulas.py`
   (ver §5). Si hay bloques inválidos y `--reflexion N`, re-sintetiza con feedback.
6. **Reporte LaTeX (0 créditos)** — `execution/generar_latex_skill.py` → PDF en
   `docs/SKILL/<nombre>/`.
7. **Instalación (0 créditos)** — `execution/instalar_skill.py` → copia a
   `~/.config/opencode/skills/<nombre>/`. Requiere `--sobrescribir` si ya existe.
8. **Alerta** — `execution/alert_user.py` + aviso de reiniciar opencode.

**Gate de instalación (2026-09-01):** si la validación del paso 5 deja bloques inválidos,
la instalación **se omite** (no se rompe el flujo) con un aviso claro. Así nunca se instala
un skill con fórmulas rotas, pero sí se genera el reporte LaTeX para revisarlo.

### Chunking (determinista)
`_repartir_chunks(texto, max_tokens)` parte por **párrafos** (`\n\n`) hasta `max_chars =
max_tokens * 4`; los párrafos más grandes que el límite se parten por página. Default
`--max-chunk-tokens 16000` → para 400K tokens ≈ 27 chunks.

---

## 4. `execution/sintetizar_skill.py` — el motor

### 4.1 Dos fases internas

**Fase A — Destilación chunk a chunk (créditos, deepseek).**
Cada chunk del libro se envía a `_llm_chunk` con un prompt que pide un resumen *denso y
estructurado* en markdown (conceptos, definiciones, fórmulas en `$...$`, tablas, ejemplos),
sin frontmatter. Si el fragmento no aporta, devuelve `[sin contenido relevante]` (se filtra).
Retry por chunk (máx 3). Resultado: el **corpus destilado** (concatenación de todas las
notas), persisted en `.tmp/skill_<nombre>_destilado.txt` como intermedio.

**Fase B — Ensamblaje (créditos, deepseek).**
`_llm_estructura` pide al LLM un **único objeto JSON** con:
```json
{ "skilL_md": "frontmatter + cuerpo del SKILL.md",
  "references": [ {"archivo": "...", "contenido": "..."} ] }
```
Las 6 references que se solicitan explícitamente (las de nivel crítico son
`_ESTRUCTURAS_REQUERIDAS` del validador):
1. `formulas.md` — cada fórmula con notación `$...$`, representación formal en bloque
   `python` con sympy (variables simbólicas y dominio), y nota "Validez:".
2. `metodologias.md` — plantillas de razonamiento: procedimiento paso a paso numerado
   que el autor emplea (método, no solo teoría).
3. `limites_aplicabilidad.md` — condiciones de borde: cuándo NO aplicar ("NUNCA aplicar si
   ..."), supuestos y qué usar en su lugar.
4. `prerrequisitos.md` — grafo de dependencias: por concepto, "requiere: [A, B]".
5. `tablas.md`, `glosario.md` — de costumbre.

### 4.2 Saneo determinista del JSON del LLM (clave para robustez)
El LLM produce JSON imperfecto; `extract_json_from_response` + `_sanear_json` + `_find_balanced_json`
lo reparan:
- **`_sanear_json`**: quita trailing commas (`,` → `}`/`]`) y escapa barras LaTeX crudas
  (`\Omega` → `\\Omega`) sin tocar escapes válidos (`\n`, `\\`, `\u`). (python.md #4)
- **`_find_balanced_json`**: escaneo por llaves balanceadas respetando strings y escapes —
  nunca regex non-greedy (python.md #6).
- **`_normalizar_frontmatter` + `_yaml_q`**: re-emite `name`/`description` del frontmatter
  como scalars YAML entre **comillas dobles**, inyectando `name` si falta. Evita que la
  `:` de la description rompa el scalar plano YAML.
- **`_validar_frontmatter`**: garantiza frontmatter YAML válido, `name` no vacío y
  coincidente con la carpeta, y `description` ≥ 20 chars.

### 4.3 Presupuesto de ensamblaje (bug raíz 2026-09-01)
Para un libro grande, el JSON de 6 references supera los `max_tokens` de salida por defecto
(8192) y **se trunca** → fallo de extracción que, tras 3 reintentos, abortaba la síntesis.
Solución:
- `--estructura-max-tokens` (default 8192; el flujo auto-usa **32768** en tier deepseek).
- `--usar-corpus`: si el corpus destilado ya existe, lo **reutiliza** sin re-distilar los
  chunks (ahorra ~30 min y ~$0.7 en el relanzamiento).
- Guardado de la **respuesta cruda** del LLM en `.tmp/sintesis_estructura_<nombre>_<ts>.json`
  para depuración.

---

## 5. `execution/validar_skill_formulas.py` — validación neuro-simbólica (0 créditos)

- Escanea `SKILL.md` y `references/*.md` extrayendo los bloques de código (fences).
- Para cada bloque:
  1. **Sintaxis** (AST parse).
  2. **Seguridad** (`_escaneo_seguridad`): veta `os`, `subprocess`, `eval`, `exec`, dunders.
  3. **Ejecución** en sandbox aislado `subprocess.run([sys.executable, -c, src], timeout)`.
- Estados por bloque: `ok|sintaxis_error|import_inseguro|ejecucion_error`.
- Verifica además que estén presentes las `_ESTRUCTURAS_REQUERIDAS`:
  `metodologias.md`, `limites_aplicabilidad.md`, `prerrequisitos.md` (warning si faltan).
- Exit codes: 0 ok / 1 args / 2 sin SKILL.md / 3 bloques inválidos.
- El oráculo (sympy) es **solo sympy**; si z3 no está instalado se omite con aviso.

**Bucle de reflexión**: con `--reflexion N` (≤3), los errores del validador se vuelcan a
`.tmp/errores_skill_<nombre>.json` y se re-sintetiza la **estructura** con `--feedback`
(sin re-distilar: el corpus ya está persistido) hasta que la validación quede en 0.

---

## 6. Resultados reales (E2E libro "Circuitos y Dispositivos Electrónicos", 2026-09-01)

| Métrica | Valor |
| :--- | :--- |
| Páginas / texto | 452 págs / 1.6M chars / ~400K tokens |
| Tier | deepseek (`deepseek/deepseek-v4-pro`) |
| Bloques Python/SymPy validados | **33/33 OK** (oráculo sympy 1.14.0) |
| Re-síntesis necesaria | 0 (validación correcta a la primera) |
| Archivos generados | 7 (SKILL.md + 6 references) |
| Reporte LaTeX | `docs/SKILL/circuitos_dispositivos_electronicos/*.pdf` |
| Instalación global | `~/.config/opencode/skills/circuitos_dispositivos_electronicos` |
| Coste sesión completa (con Fase 2) | ~$0.75 |

---

## 7. Coste: dónde va el dinero y cómo no desperdiciarlo

- **0 créditos**: extracción de PDF, chunking, enrutamiento, validación sympy, reporte LaTeX,
  instalación, reflexión local.
- **Créditos (deepseek, tier barato de contexto masivo)**:
  - Destilación de cada chunk (`max_tokens=2048` por chunk).
  - Ensamblaje del JSON completo (`estructura-max-tokens 32768`).
- Mitigación clave: el **corpus destilado persistido** hace que re-ensamblar (p. ej. tras un
  cambio del prompt de estructura) **no re-cueste la destilación** (`--usar-corpus`).
- Por ello un libro de 452 págs costó ~$0.75: la destilación es el grueso, y se paga **una vez**.

---

## 8. Comandos útiles

```bash
# Flujo completo (instala en global al final si la validación está limpia)
python3 flujo_libro_a_skill.py --pdf "libro.pdf" --nombre mi_skill --tema "Mi Tema" \
    --idioma es --sobrescribir --reflexion 1

# Sin instalar (solo generar + validar + reporte)
python3 flujo_libro_a_skill.py --pdf "libro.pdf" --nombre mi_skill --tema "Mi Tema" --dry-run

# Re-ensamblar un skill ya destilado sin re-distilar (ahorra créditos)
python3 flujo_libro_a_skill.py --pdf "libro.pdf" --nombre mi_skill --tema "Mi Tema" \
    --sobrescribir --usar-corpus --estructura-max-tokens 32768

# Validar manualmente un skill (cero créditos)
python3 execution/validar_skill_formulas.py --skill ~/.config/opencode/skills/mi_skill
```

---

## 9. Archivos relacionados

- `flujo_libro_a_skill.py` — orquestador (3-capas) + gate de instalación
- `directives/libro_a_skill.yaml` — SOP de la Fase 1
- `execution/sintetizar_skill.py` — destilación + ensamblaje + saneo JSON/frontmatter
- `execution/extraer_libro_pdf.py` — extracción del texto del PDF
- `execution/validar_skill_formulas.py` — validación neuro-simbólica + `_ESTRUCTURAS_REQUERIDAS`
- `execution/generar_latex_skill.py` — reporte LaTeX del skill
- `execution/instalar_skill.py` — instalación global
- `execution/enrutador.py` — decisión determinista del modelo
- `docs/AGENTE_IA/fase2_resolver_skill.md` — Fase 2 (el skill ya creado, en uso)
- `Sessions/2026-08-30_sintesis_neurosimbólica_skills.md`, `Sessions/2026-09-01_e2e_libro_fase2_resolver.md` — logs
