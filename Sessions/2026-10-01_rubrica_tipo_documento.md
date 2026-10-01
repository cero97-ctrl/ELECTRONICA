# 2026-10-01 — rubrica_tipo_documento

## Tema
Cerrar la deriva entre lo que la directiva promete y lo que el prompt de evaluación emite. Partir el `SYSTEM_INSTRUCTION` por tipo de documento (`--tipo examen|laboratorio`).

## Contexto
El usuario preguntó qué es una "rúbrica" en este workspace y, al explicar que se
concatena al System Instruction, apareció una incoherencia: el prompt base
`SYSTEM_INSTRUCTION` estaba escrito para **exámenes escritos** ("identificar cada
pregunta"), y las dos rúbricas existentes lo especializaban encima.

La incoherencia era más honda que una impresión. Midiendo los consumidores:

- `directives/evaluar_practica_laboratorio.yaml` prometía dos claves que el prompt
  NUNCA emitió: `observaciones_por_seccion` y `observaciones_montaje`.
- `execution/generar_informe.py` solo leía `observaciones_por_pregunta`, con
  `.get(clave, [])`: si el modelo obedecía a la directiva, la tabla salía vacía
  **sin error**.
- El banner estaba cableado a "Evaluación de Exámenes" y `flujo_evaluar_examen.py`
  escribía siempre en `informe_examen/`. Evaluar una práctica producía un PDF
  titulado como si fuera un examen.

Es decir: la deriva era silenciosa de punta a punta.

## Decisiones (usuario)
1. **Empezar por el test, no por el fix** ("prefiero que empieces por el test para
   ver el fallo primero"). Se escribió `execution/test_evaluar_rubrica.py` y se
   ejecutó contra el código viejo para ver el rojo antes de tocar nada. Esta decisión
   pagó sola: el test cazó la clave fantasma `observaciones_montaje`, que NO se había
   detectado en el análisis previo.
2. **Opción A (partir el prompt) sobre B (schema en el YAML)**, dejada a criterio
   del agente porque "arma un plan con la opción que te parezca mas conveniente".
   Motivo (evidencia, no gusto): B no ahorraba tocar Python. Con el schema en el
   YAML, `generar_informe.py` tendría que entender N formas —incluidas las que un
   YAML mal escrito declarase—, así que la "flexibilidad sin tocar Python" de B se
   evaporaba.
3. **NO partir el contrato de salida JSON.** Los 8 criterios de laboratorio
   (presentación, montaje, mediciones…) mapean 1:1 sobre la misma forma de "lista de
   ítems con puntaje parcial y errores". Partirlo obligaría a `generar_informe.py` a
   ramificar sin ganar nada. Lo único que parte es el *encuadre* de la tarea.

## Actividades
- `execution/evaluar_examen.py`: `SYSTEM_INSTRUCTION` partido en `PERFIL_COMUN` +
  `TAREA_POR_TIPO{tipo}` + `SCHEMA_SALIDA` (único). Nuevas funciones puras
  `componer_system_instruction(tipo, rubrica_texto)` y `leer_rubrica(path)`
  (separadas: componer no toca disco, leer sí). Flag `--tipo` con `choices`.
  `result` ahora incluye `"tipo"`.
- `execution/generar_informe.py`: lee `observaciones_por_item` con alias de la
  grafía vieja; banner, rótulo de columna y texto de tabla vacía siguen a
  `data["tipo"]`.
- `flujo_evaluar_examen.py`: `--tipo` en passthrough; carpeta de salida
  `informe_examen`/`informe_practica` según tipo.
- `mcp_evaluar_server.py`: parámetro `tipo` con validación.
- Directivas v1.1/v1.2 con `historial`, y corregida la lista de claves.
- Test nuevo, 33 aserciones, todas en verde.

### Verificación
- `python3 execution/test_evaluar_rubrica.py` → 33/33, exit 0.
- Suite existente sin regresión: barrera, auditar_repo, auditar_sistema,
  verificar_texto, run_state → todas exit 0.
- Render real de `generar_latex` con el JSON genuine de `.tmp/evaluacion_examen_2.json`
  (que usa la grafía vieja): 5 ítems, llaves balanceadas, **compila a PDF**.
- Compilación de informe en ambos tipos: `success=True` en los dos.
- `py_compile` limpio; las 3 directivas parsean como YAML.

### Dos aserciones que mentían (corregidas antes de dar el test por bueno)
El test inicial daba verde por el motivo equivocado en dos sitios, que es peor que
fallar: `returncode != 0` no distingue "choice inválida" de "flag inexistente"
(azul ahora comprueba `invalid choice` en stderr), y `f" examen" in ayuda` encontraba la palabra
"examen" en la prosa del `--help`.

### Incidente de formato
Un edit añadió `  - tipo:` sin el guion en `evaluar_examen_mcp.yaml` y rompió el
YAML. Se detectó con `yaml.safe_load` (el test no lo cubre: lee prosa, no estructura
completa). Restaurado.

### Verificación adicional
- `flujo_auditar_repo.py --rapido`: `con_avisos` (exit 0), 0 dimensiones con fallo,
  238 s. Ningún aviso es de esta sesión: `directivas` (11 capacidades declaradas sin
  implementar, Status: planificado), `peso_git` (252 MB), `pdf_stale` (3 pares),
  `estado_sesion` (2 sin log), `disco` (85.5 %). Los verdes incluyen `capas`
  (20/20 flujos con capa 3) y `secretos` (730 ficheros).
## Pendientes
- Los artefactos de regresión en `.tmp/` se limpiaron; `.tmp/` es gitignored.
- Las rúbricas siguen siendo texto CRUDO pegado al prompt: una clave mal escrita en
  un YAML no da error, el modelo la ignora. Documentado en el código, no corregido.
- `GOOGLE_API_KEY` marcada como filtrada por Google (`403 leaked key`): el backend
  por defecto (Gemini) está caído hasta que se regenere la clave. No es de este
  trabajo; afecta a todo script del repo que use `--api-backend gemini`.

## Cierre: prueba real con la API (2026-10-01, tarde)

El usuario autorizó gastar. Coste real medido: **$0.0168** (uso mensual pasó de
0 a 0.016831; saldo $20.95 → $20.93). Un solo intento, primer tier de la cadena,
sin reintentos. La estimación previa de $0.011 era del orden correcto.

### El fixture
`.tmp/gen_fixture_lab.py` genera un informe de práctica **sintético** con 8
errores deliberados y documentados. Razón de no usar un PDF real del repo: un
fixture fabricado permite comparar la salida contra la verdad conocida. Con las
12 páginas de una práctica real no se sabe si el modelo acertó o inventó.

Los 8 errores: R2 desconectado y sin valores nominales; tabla sin unidades;
I(0)=0 (físicamente falso en un RC); R_teorico=2.3k cuando debe ser 1.2k;
confusión teórico vs medido; sin gráfica; conclusiones que no relacionan con los
objetivos; tildes ausentes y "Se took la fuente".

### Resultado: acertó 7/7 categorías de error
- 7 ítems generados, uno por sección (la unidad correcta, no "pregunta").
- 2.8/10, nivel Deficiente.
- **Los 3 errores conceptuales son reales y no los oí de ninguna parte**: la
  condición inicial I(0)=0 en un RC (un capacitor descargado es cortocircuito, la
  corriente debe ser máxima), "saturarse" en vez de estado estacionario, y
  `tau = R*C` sin la equivalente de Thévenin con dos resistencias. Eso es
  física correcta sobre un circuito que el modelo nunca vio resuelto.
- Detectó la falta de valores nominales y la tildes.
- Puntajes por ítem respetan los pesos de la rúbrica (marco teórico 0.5/1.5,
  mediciones 0.4/2.0, sintaxis 0.2/0.5).

### Un defecto que la prueba real encontró y el test no
El encabezado de cada página seguía diciendo "Informe de Evaluación" para una
práctica. El título de portada sí decía "Informes de Práctica" (eso ya lo hice
antes), así que un test que buscara `"Práctica" in informe` daba **verde por el
motivo equivocado** — la tercera vez que un test de esta sesión pasaba mentiroso.
Se aisló la línea con un regex anclado en `--- Electrónica}` y se comprobó que
falla al revertir el fix y al colar el rótulo de práctica en la rama de examen.
`generar_informe.py` ahora deriva `etiqueta_fancyshort` del tipo. 33 → 38
aserciones.

Detalle del regex: `[^}]*` trunca porque el interior lleva `\color{azulNoche}`,
que ya tiene llaves. Anclar en el final del rótulo es lo que funciona.