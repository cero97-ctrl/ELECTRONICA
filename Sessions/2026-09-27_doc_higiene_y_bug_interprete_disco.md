# 2026-09-27 — doc_higiene_y_bug_interprete_disco

## Tema
Documentar el procedimiento de evaluación de higiene del repo y corregir un falso
dato que el propio compositor venía publicando.

## Contexto
- El usuario pidió un Markdown en `docs/MATENIMIENTO/` con las instrucciones
  precisas para que cualquier LLM evalúe la higiene "tal cual como lo ha hecho
  este", es decir, de forma reproducible.
- Al recopilar las formas reales de salida de los seis verificadores
  reutilizados (paso previo a documentar el contrato de los intérpretes) se
  detectó que la dimensión `disco` publicaba un **0 MB recuperables falso**.
- Causa raíz: `_interpreta_disco` leía `datos["recuperable"]`, clave que
  `execution/disco_medir.py` nunca ha emitido. Los bytes viven en
  `resumen_catalogo.reclaimable_por_tier.seguro.bytes`. Como la clave no
  existía y el código hacía `or 0`, la ausencia de dato se publicaba como un
  cero afirmado, que es un hecho.
- Por qué sobrevivió a los tests: los fixtures de disco estaban escritos a mano
  y omitían `resumen_catalogo` por completo, así que la rama del recuperable
  nunca se ejecutaba. Los tests demostraban umbrales y no decían nada del número.
- Cifra real: 16.1 MB (tier `seguro`). El total recuperable es 9.2 GB y lo
  merely-medido del tier seguro 452.0 MB; el informe debe leer el tier `seguro`
  de `reclaimable_por_tier`, nunca esas otras dos cifras.

## Decisiones (usuario)
1. Documento en `docs/MATENIMIENTO/como_evaluar_higiene.md`, redactado para que
   sea autocontenido: otro LLM debe poder reproducir el veredicto sin leer esta
   bitácora.
2. Se asume que "higiene del sistema" significa el espacio de trabajo/repo. Por
   eso el documento cubre la higiene del repo y declara explícitamente el hueco
   de sistema (sección 11) en vez de fingir cobertura de RAM/CPU/servicios.
3. No implementar `flujo_auditar_sistema.py` en esta sesión: el encargo es
   documentación. Queda como pendiente con su procedimiento de cierre ya escrito.
4. Ante los dos fallos de directivas y disco, no se repara nada: la auditoría es
   de solo lectura y la reparación es decisión del operador. Esta restricción se
   nervó de la conversación previa y se mantuvo en el documento.

## Actividades
- Inventariadas las 6 dimensiones reutilizadas con script, args, timeout reales y
  `lenta`; capturadas las formas reales de salida de `estado_sesion`,
  `bitacoras` y `disco` (las de `verificar_texto`, `test_barrera_disco` y
  `test_verificar_texto` se resuelven por exit code y línea de aserciones).
- Corregido `_interpreta_disco`: lee `resumen_catalogo.reclaimable_por_tier.seguro.bytes`,
  y si el resumen no viene declara `recuperable no informado` con
  `recuperable_mb: null` en vez de afirmar 0. El estado lo sigue decidiendo
  `filesystem.uso_pct` en ambos casos.
- Corregido un comentario corrupto en el mismo intérprete: decía
  "y no se **knew** antes".
- Añadidas 8 aserciones con un fixture **capturado de la salida real** de
  `disco_medir.py`, incluidas dos que comprueban que el umbral no se confunda con el
  total (9.2 GB) ni con lo merely-medido (452.0 MB), y tres que comprueban que
  la ausencia de dato no produce un cero. Total: 94 → 102 aserciones.
- Escrito `docs/MATENIMIENTO/como_evaluar_higiene.md` (491 líneas, 12
  secciones): regla del peor estado, tres capas, procedimiento en 10 pasos,
  contrato de intérpretes con las formas reales, el error del fixture como
  sección propia, tabla de trampas reales, códigos de salida, rendimiento
  medido, checklist de verificación, restricciones y alcance real.
- **El verificador de texto cazó el documento a mí**: 5 corrupciones CJK que
  introduje al escribirlo, entre ellas dos pares CJK (U+8FD9 U+9879 y
  U+7EF4 U+5EA6). Citadas aqui por codepoint y no pegadas, para que esta
  bitacora no ensucie el escaneo de la dimension `texto`. Corregidas.
- Al corregir una de ellas introduje una sexta ("lo-Foundermo") y una séptima
  ("testsPasaron", palabra pegada). Ambas cazadas por revisión manual, no por el
  verificador: son code-switching, clase que el verificador no cubre.
- Verificación final: `py_compile` OK; 102 + 88 + 22 aserciones OK; YAML de la
  directiva carga; `--flag-malo` y `--dimension no-existe` devuelven 3;
  `git diff --check` limpio; verificador de texto sin hallazgos; escaneo manual
  de la clase no cubierta sin hallazgos reales (solo `LaTeX` y `GitHub`, que son
  nombres legítimos).
- Auditoría completa tras el cambio: veredicto **inalterado**, 2 fallos
  (`directivas` 12 referencias rotas, `disco` 91.3 %), exit 1. Confirmado que
  tocar el intérprete no mueve el veredicto.

## Pendientes
- **P1** Corregir o retirar las 12 referencias a scripts inexistentes en 10
  directivas. Bloquea el verde del repo.
- **P1** Disco al 91.3 % (~20.3 GB libres, 16.1 MB recuperables con borrado
  seguro). Purgar no ayuda: requiere decisión sobre qué eliminar.
- **P2** `docs/MATENIMIENTO/` debería enlazarse desde `AGENTS.md` para que el
  procedimiento se encuentre sin saber que existe.
- **P2** Hueco de cobertura conocido: el verificador de texto no detecta
  code-switching (palabras inglesas dentro de prosa o comentarios en
  castellano). Se detectó a mano en esta sesión, dos veces.
- **P2** Cerrar el hueco de higiene de sistema con un `flujo_auditar_sistema.py`
  de tres capas siguiendo `docs/MATENIMIENTO/como_evaluar_higiene.md`.
- **P3** Tres PDF desfasados; tres `workerd` de 97.4 MB; MP4 de 38.6 MB. Requieren
  decisión explícita (reescribir historia o retirar del índice).
- Sin tocar de sesiones previas: `-halt-on-error` en `execution/compile_latex.py`;
  sobreestimación y targets de `flujo_disco.py`; "5 celdas"→4 en
  `docs/COLAB/entorno_colab.ipynb`; monitoring de saldo OpenRouter; conservar
  `IA` como único entorno TensorFlow funcional; `conda defaults` roto por
  manifiesto `tk` (workaround `--override-channels -c conda-forge`).
