# 2026-11-09 — evaluacion_teorica_por_grupo

## Tema
Evaluación teórica semanal por grupo sobre el trabajo reportado en GitHub (CYBERSEGURIDAD).

## Contexto
- El curso ya tenía controles de fase comunes (semanas 3, 5 y 7, 15 %), pero nada evaluaba
  lo que cada grupo desarrolló y reportó en su repositorio: el entregable semanal quedaba
  revisado por el docente sin instrumento propio, y cuatro grupos que hacen tareas distintas
  (roles Rojo, Azul, Púrpura, Legal) no pueden rendir la misma prueba.
- El repo es público y los enunciados viven en el banco privado desde v1.2, así que un
  instrumento nuevo por grupo y por semana tenía que seguir el mismo contrato: calendario
  público, enunciado privado.
- Se parte del material ya verificado en la sesión anterior (`Sessions/2026-11-09_variante_2_banco_preguntas.md`).

## Decisiones (usuario)
1. **Cadencia semanal, semanas 2 a 9**: una prueba por semana y por grupo = 4 × 8 = **32 instrumentos**.
2. **Peso dentro del 15 % de controles**: 10 % control común + 5 % teóricas; reparto igual entre
   las 8 semanas → **0,625 % por prueba** (cada control común pasa a 3,33 %).
3. **Condiciones**: individual, 30 minutos, con el repositorio del grupo abierto y sin apuntes;
   **4 preguntas de 2,5 / 3,0 / 2,5 / 2,0 pt** (suman la escala 10).
4. **Privacidad y corrección**: enunciados en el banco privado con variantes; **corrección manual
   con rúbrica pública** (el criterio se conoce, el enunciado no).
5. «ok, procede con la implementación del plan», con la autoría de las 32 teóricas por lotes
   semanales para su revisión.
6. Sigue vigente: **no commitear sin revisión previa** del usuario.

## Actividades
- **Capa 3** (`execution/generar_material_curso.py`): artefacto `teoricas`; `PREGUNTAS_TEORICA = 4`
  y `CRITERIOS_TEORICA` (lectura_del_entregable 2.5, justificacion_tecnica 3.0,
  trazabilidad_con_la_evidencia 2.5, limites_y_riesgo_residual 2.0); `cargar_banco` acepta
  `variantes` o `teoricas`; `_normalizar_variantes` + `_elegir_variante` comparten el ciclo de vida
  entre secciones (`seleccionar_variante`, `seleccionar_variante_teoricas`); `_cantidad_grupos`,
  `semanas_teoricas`, `_ejemplo_de_semana`, `_rol_de`, `componer_teoricas`, `validar_teoricas`,
  `tex_teorica`, `yaml_rubrica_teorica`; `generar(..., grupo=None)` y `--grupo N`; `validar()`
  comprueba `evaluacion.teorica_semanas` (lista, sin duplicados, semana existente, tarea para todos
  los grupos); `main()` compone controles y teóricas con un solo `cargar_banco` e `info_banco`
  anidado que conserva `variante`/`estado` arriba (los imprime el flujo).
- **Descriptor** (`cursos/CYBERSEGURIDAD/curso.yaml`): `Controles de fase` 15 → **10**, nuevo
  `Evaluación teórica del trabajo de grupo (semanas 2-9)` **5** (suma 100) y
  `evaluacion.teorica_semanas: [2..9]`.
- **Capa 2** (`flujo_disenar_curso.py`): reenvía `--grupo`, etiqueta la variante por sección y
  muestra la variante de teóricas por separado.
- **Capa 1** (`directives/disenar_curso.yaml` → **v1.3**): bloque `evaluacion_teorica_grupo`
  (esquema del banco, reglas de cobertura exacta, rúbrica pública, rol derivado de la misma
  rotación, salidas, protección) y 3 edge cases nuevos.
- **Banco privado**: sección `teoricas` con variante 1 `utilizable` y los **32 exámenes**
  (4 preguntas cada uno, suma 10), derivados del `ejemplo` real de esa semana y grupo.
- **Verificación**: 32 `.tex` + **32 PDF con 0 errores y 0 overfull**; `--grupo 3` emite 8;
  `--grupo 9` falla con código 1 (fuera de rango); roles derivados correctos (S2G1 Rojo,
  S4G1 Azul, S6G3 Rojo, S9G4 Púrpura, coherentes con los `intro` del descriptor); determinismo
  (md5 de los 32 `.tex` idéntico en dos corridas); sin fuga (`git grep` de frases del banco = 0
  en ficheros versionados) y `git check-ignore` confirma banco (`.gitignore:74`), `.tex` (:67) y
  `.pdf` (:68) ignorados; rúbrica pública parsea y suma 10; sílabo y guía regenerados con los
  nuevos pesos (tabla 35 / 10 / 5 / 15 / 25 / 10 = 100).
- **Tests**: `execution/test_generar_material_curso.py` pasa de 103 a **124 aserciones** (6 pruebas
  nuevas: cobertura exacta, faltante/sobrante, puntajes y forma, calendario público, LaTeX y
  rúbrica, matemática inválida). Sin fallos.
- **Redacción**: 8 correcciones gramaticales y 1 reescritura para no calcar una frase que ya está
  en el material público (`grupo_3_02.tex`); los enunciados evitan `_` fuera de `$...$`
  (`_validar_matematica` lo rechaza con código 6).

## Pendientes
- **Revisión del usuario de los 32 enunciados** (el banco es editable por semana; cualquier lote
  puede reescribirse y regenerarse con `--solo teoricas --grupo N`).
- **Commit + push** de: `curso.yaml`, `generar_material_curso.py`, `flujo_disenar_curso.py`,
  `directives/disenar_curso.yaml`, `test_generar_material_curso.py`, `rubrica_teorica.yaml` (nueva,
  pública), sílabo/guía regenerados y las dos bitácoras de hoy. Solo tras el visto bueno.
- Carga de corrección: 32 pruebas individuales por semestre, sin automatizar. `evaluar_examen.py`
  ya consume `rubrica_teorica.yaml` si se quiere escanear y corregir con el flujo existente.
- Los otros dos cursos (`LABORATORIO_I_FISICA`, `LABORATORIO_II_FISICA`) no declaran
  `teorica_semanas`: el artefacto queda inactivo ahí hasta que se decida.
- Sigue aplazada la dimensión `examen_filtrado` en `flujo_auditar_repo.py` (de sesiones anteriores).
