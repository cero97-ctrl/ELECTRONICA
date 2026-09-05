# Fase 1b — De un repositorio de código a un skill de referencia (API/código)

> Documento de estudio. Complementa `fase1_libro_a_skill.md` (Fase 1: libro→skill con
> perfil de fórmulas) y `fase2_resolver_skill.md` (Fase 2: usar el skill para resolver).
> La Fase 1b **crea** un skill a partir de código fuente; el perfil de salida es
> **referencia_codigo** (cómo el repo resuelve problemas y cómo aplicar esa metodología
> o código en el workspace), NO un libro de fórmulas SymPy.
> Implementado el 2026-09-05.

---

## 1. Qué resuelve

Un LLM que "recuerda" una librería (~/.config/opencode/skills/<nombre>/README.md) alucina
sus APIs. La Fase 1b transforma un **repositorio (GitHub o local)** en un **skill
estructurado de referencia de código/API**:

```
[GitHub URL | dir local] ─▶ extraer_repo_github ─▶ texto_completo.txt ─▶ enrutador
                                                                         │
                                                        ─▶ sintetizar_skill --perfil referencia_codigo
                                                                         │
                                     (destila chunk a chunk ─▶ corpus)  │
                                     (ensambla: api, patrones, ejemplos,│
                                      configuracion, prerrequisitos,    │
                                      glosario)                         ▼
                                                     SKILL.md + references/
                                                                         ▼
                                    [validar_skill_formulas --perfil referencia_codigo]
                                    [generar_latex_skill → reporte PDF]
                                    [instalar_skill → ~/.config/opencode/skills]
```

### Diferencia frente a la Fase 1 (libro)

| | Fase 1 (libro) | Fase 1b (repo) |
| :--- | :--- | :--- |
| Fuente | PDF de texto | Repositorio (URL GitHub o directorio local) |
| Extracción | `extraer_libro_pdf.py` | `extraer_repo_github.py` (clona, filtra, concatena) |
| Perfil de síntesis | `libro` (default) | `referencia_codigo` |
| Esquema de references | `formulas.md`, `metodologias.md`, `limites_aplicabilidad.md`, `tablas.md`, ... | `api.md`, `patrones.md`, `ejemplos.md`, `configuracion.md`, `prerrequisitos.md`, `glosario.md` |
| Código en bloques | SymPy autocontenido (se ejecuta en sandbox) | Snippets/ejemplos reales del repo (`from <paquete> import ...`) |
| Validación | Sintaxis + imports seguros (solo math/sympy/fractions) + ejecución en sandbox | Sintaxis (observación) + bloqueo solo de módulos/funciones de Sistema; NO ejecuta en sandbox |

---

## 2. La arquitectura de 3 capas (obligatoria)

| Capa | Archivo | Rol |
| :--- | :--- | :--- |
| **Directiva** | `directives/repo_a_skill.yaml` | SOP: 8 pasos, 8 edge cases, retry budget |
| **Orquestación** | `flujo_repo_a_skill.py` | Entrevista, orquesta scripts, gate de instalación |
| **Ejecución** | `execution/extraer_repo_github.py`, `sintetizar_skill.py` (perfil `referencia_codigo`), `validar_skill_formulas.py` (perfil `referencia_codigo`), `generar_latex_skill.py`, `instalar_skill.py` | Trabajo determinista |

---

## 3. El orquestador `flujo_repo_a_skill.py`

Pasos (total depende de flags):

1. **Entrevista ligera**: fuente, tema, nombre (snake_case, default derivado del repo),
   idioma, filtros de archivos y confirmación de instalación. Se persiste en
   `.tmp/entrevista_skill_<nombre>.json`.
2. **Extracción** — `execution/extraer_repo_github.py` (determinista, 0 créditos):
   - URL GitHub → `git clone --depth 1` a `.tmp/repo_clone_<owner>-<repo>/`; ruta local → usa el dir tal cual.
   - Filtra por extensión (docs + código fuente) saltando `.git/node_modules/vendor/build/venv/__pycache__`.
   - `--incluir`/`--excluir` globs opcionales, `--max-archivos`/`--max-bytes`.
   - Concatena a `.tmp/repo_<nombre>_texto/texto_completo.txt` con cabeceras `=== ARCHIVO: <ruta> ===` y genera `indice.json` con árbol de estructura.
   - E2E real: `pallets/itsdangerous` → 32 archivos, ~22.5K tokens.
3. **Enrutamiento determinista** — `execution/enrutador.py --task contexto_masivo`: mide
   tokens y decide tier. Para un repo grande → **deepseek** (`deepseek/deepseek-v4-pro`).
4. **Síntesis (créditos)** — `execution/sintetizar_skill.py --perfil referencia_codigo`
   → 7 archivos (SKILL.md + 6 references de API). Prompts adaptados: NO fuerzan SymPy.
5. **Validación (0 créditos)** — `execution/validar_skill_formulas.py --perfil referencia_codigo`.
   Solo bloquea riesgos de Sistema; los snippets de API (firmas incompletas, imports del
   paquete) se marcan `ok`/`observacion`, nunca errores.
6. **Reporte LaTeX (0 créditos)** — `execution/generar_latex_skill.py` → PDF en
   `docs/SKILL/<nombre>/`.
7. **Revisión humana** del skill.
8. **Instalación (si no es --dry-run)** — `execution/instalar_skill.py` → copia a
   `~/.config/opencode/skills/<nombre>/`. Recuerda reiniciar opencode.

---

## 4. El perfil `referencia_codigo` en `sintetizar_skill.py`

`--perfil` (default `libro`) cambia dos cosas:

**a) Prompts de destilación por chunk** (`_prompts_chunk_codigo`): en vez de "fórmulas,
metodologías, tablas", pide "funciones y clases públicas con firmas, patrones de uso,
configuración relevante, ejemplos de código que el lector pueda copiar".

**b) Esquema de references y normas de contenido** (`_normas_contenido_codigo`):

| Archivo | Contenido |
| :--- | :--- |
| `api.md` | Funciones/clases públicas con firma completa (parámetros, retorno) y ejemplo de llamada |
| `patrones.md` | Cómo se combinan funciones/clases para resolver problemas típicos |
| `ejemplos.md` | Código REAL del repo (no inventado), marcado por archivo de origen |
| `configuracion.md` | Opciones, variables de entorno, archivos de config |
| `prerrequisitos.md` | Dependencias, versiones, cómo instalar |
| `glosario.md` | Términos técnicos del proyecto |

**c) El frontmatter**: mismo saneo determinista (`_normalizar_frontmatter`).
**d) `_find_balanced_json`**: aplica igual (robusto a llaves anidadas).

---

## 5. La validación en el perfil `referencia_codigo`

El validador clásico (`validar_skill_formulas.py` perfil `libro`) exige que cada bloque
```python sea un programa SymPy autocontenido (solo `math`/`sympy`/`fractions`) y lo
ejecuta en sandbox. Eso es **incorrecto para un skill de API**: los ejemplos legítimamente
hacen `from <paquete> import ...`, y el paquete no está instalado en el sandbox.

Con `--perfil referencia_codigo`:

1. **Sintaxis** — `ast.parse` de cada bloque. Si falla (firma/documentación incompleta),
   se marca `observacion` (NO bloquea): son snippets ilustrativos, no programas.
2. **Seguridad** — `_escaneo_peligro_sistema`: solo bloquea módulos/funciones de Sistema
   con riesgo real (`os`, `sys`, `subprocess`, `socket`, `ctypes`, `open`, `eval`,
   `exec`, `__import__`, ...). Imports de librería/proyecto (`itsdangerous`, `hashlib`)
   son legítimos. Un bloque con riesgo → estado `peligro` (ÚNICO estado que cuenta como
   error y hace exit 3).
3. **NO se ejecuta en sandbox** — el código depende del paquete del repo.

Esto convierte los 74 falsos positivos del perfil libro en **0 errores**, conservando la
protección real contra snippets maliciosos en el skill.

---

## 6. Costo y créditos

- **0 créditos**: extracción, enrutador (decisión local), validación, LaTeX, tests.
- **Créditos**: síntesis (`openrouter_chat`, default deepseek). Repo pequeño: ~22K tokens
  de entrada ≈ centavos de dólar. Repo grande: avisar antes, acotar con `--incluir`/
  `--excluir`.
- Verificación de saldo puntual: `python3 execution/monitor_saldo_openrouter.py`.

---

## 7. Commandos de ejemplo

```bash
# GitHub público, disponible para resolver:
python3 flujo_repo_a_skill.py --repo https://github.com/pallets/itsdangerous \
    --tema "Firma y autenticación de datos" --nombre pallets_itsdangerous

# Directorio local acotando a código Python:
python3 flujo_repo_a_skill.py --repo /ruta/al/repo --nombre midu_skill \
    --incluir "*.py" "*.md" --excluir "tests/*" --dry-run

# Solo extraer (0 créditos, determinista):
python3 execution/extraer_repo_github.py --fuente https://github.com/psf/requests \
    --salida .tmp/repo_requests_texto
```

---

## 8. Edge cases clave (ver la directiva)

| Caso | Recuperación |
| :--- | :--- |
| Repo privado / 404 | `git clone` falla; ofrecer ruta local o `GITHUB_TOKEN` |
| Repo sin código/docs tras filtrar | Código 2; sugerir `--incluir` |
| Repo enorme / costo alto | Avisar tokens medidos; acotar con globs o límites |
| Snippets no autocontenidos | `observacion` (no bloquea instalación) en perfil código |
| Bloque con riesgo de Sistema | `peligro` → exit 3; con `--validar-estricto` aborta instalación |