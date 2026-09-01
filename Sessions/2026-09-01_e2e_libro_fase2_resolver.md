# Sesión: E2E libro completo + Fase 2 (resolver con skill)

Fecha: 2026-09-01
Contexto: Continuación de la sesión 2026-08-30 (síntesis neuro-simbólica). El usuario recargó créditos OpenRouter.

## Actividades

### A. Recalibración de créditos
- `CREDITS_TOTAL_REF` actualizado a 24.7694 (web mostraba $22.44 + usage 3.08).
- Monitor ahora estima correctamente (~$22.44 al inicio de sesión).

### B. Flujo: instalación condicionada a validación
- Añadido `validacion_ok_flag` a `flujo_libro_a_skill.py`: si la validación neuro-simbólica (Paso 4) detecta bloques inválidos, la instalación se OMITE con aviso claro (no se rompe el flujo).
- Flag `--sobrescribir` sigue requerido para reemplazar un skill existente.

### C. E2E libro completo (452 págs, ~$0.75 total)
- Comando: `python3 flujo_libro_a_skill.py --pdf "...Lluis Prat Vinas.pdf" --nombre circuitos_dispositivos_electronicos --tema "Circuitos y Dispositivos Electrónicos" --idioma es --sobrescribir --reflexion 1 --usar-corpus`
- Resultado: **33/33 bloques válidos** (sin necesidad de re-síntesis)
- 7 archivos: SKILL.md + formulas + metodologías + límites + prerrequisitos + tablas + glosario
- LaTeX compilado → PDF en `docs/SKILL/circuitos_dispositivos_electronicos/`
- Instalado globalmente en `~/.config/opencode/skills/circuitos_dispositivos_electronicos`

### D. Bug fix raíz: truncado de ensamblaje
- Causa: el JSON con 6 references para un libro de 400K tokens excedía `max_tokens=8192`
- Solución en `execution/sintetizar_skill.py`:
  - Nuevo flag `--estructura-max-tokens` (default 8192; auto 32768 para deepseek)
  - Nuevo flag `--usar-corpus` para reutilizar destilación persistida sin re-distilar (ahorra ~30 min / ~$0.7)
  - Guardado de respuesta cruda del LLM en `.tmp/sintesis_estructura_*_<ts>.json` para debug
- `flujo_libro_a_skill.py`: pasa ambos flags a `sintetizar_skill.py` en síntesis inicial y reflexión

### E. Fase 2: resolver con skill (3-capas)
- **`execution/resolver_skill.py`** (Layer 3, determinista):
  1. Retrieval por embeddings (HuggingFaceEmbeddings, cosine similarity, top-k, cache en `.tmp/resolver_skill/`)
  2. Formulador LLM (OpenRouter) → análisis paso a paso + bloque SymPy autocontenido
  3. Oráculo (subprocess sandbox con `_escaneo_seguridad` de `validar_skill_formulas.py`)
  4. Reflexión (máx 3 rondas, inyecta traceback real)
- **`flujo_resolver_skill.py`** (Layer 2, orquestador):
  - Enrutowa vía `execution/enrutador.py` (default task calculo_formal → opus)
  - Acepta `--modelo` para override explícito (ahorro con flash para tests)
  - Guarda resultado en `.tmp/resolucion_<ts>.json`
- **`directives/resolver_skill.yaml`** (Layer 1, SOP): 4 pasos, 8 edge cases, retry budget 3

### F. Verificación en vivo de Fase 2
- Problema: punto Q de BJT emisor común con divisor de base (Vcc=12V, R1=100k, R2=50k, Re=1k, Rc=2k, β=100)
- Skill global: 33 bloques SymPy validados (0 inválidos)
- Resultado: retrieval recuperó "Metodología 7: Análisis BJT en DC" (score 0.680) como sección top
- LLM citó explícitamente la metodología del skill en el análisis
- Oráculo confirmó: ICQ = 2.46 mA, VCEQ = 4.61 V (correcto)
- Cero reflexiones necesarias; costo flash: ~$0.005

## Decisiones
- `--estructura-max-tokens 32768` para deepseek (las 6 references del libro completo necesitan ~30-40K tokens de salida)
- Gate de instalación: omitir (no abortar) cuando la validación falla — mejor que el usuario pueda ver el reporte LaTeX con los errores marcados
- Resolver usa flash por defecto (tests baratos); calculo_formal→opus para producción
- `--usar-corpus` para reutilizar destilación cuando la rerun solo necesita re-ensamblar

## Pendiente
- Tests del resolver con más problemas (circuito RC, amplificador, MOSFET)
- Considerar Fase 2b (capa de fidelidad: contrastar claims del LLM con los chunks de origen)
- Revisar si 32K tokens basta para libros aún más largos; si no, particionar ensamblaje por reference
- Actualizar `.agent/enrutamiento.md` tabla "mapa script → nivel" con resolver_skill
