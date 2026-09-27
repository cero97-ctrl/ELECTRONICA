# 2026-09-27 — auditoria_contrato_cli

## Tema
auditoria_contrato_cli

## Contexto
- Pregunta del usuario: "la proxima vez que flujo ejecutamos para evaluar la
  higiene?". Al verificar la respuesta aparecieron tres defectos de contrato en
  el flujo que se acababa de entregar, todos del mismo tipo: el codigo de
  salida y la documentacion no decian lo que el flujo hacia.
- Nota de alcance: el flujo que se preguntaba mide higiene del REPO. La
  higiene del SISTEMA (RAM, CPU, servicios) no tiene ningun flujo con
  veredicto: `flujo_diagnostico.py` genera un PDF sin exit code, y
  `flujo_disco.py` es de mantenimiento. Ese hueco sigue abierto y es otra
  cosa.

## Decisiones (usuario)
1. Cerrar los 4 defectos de contrato (documentacion del flag, unificacion
   `--dimension`/`--solo`, codigo 3 para uso incorrecto, perfilar `--rapido`).
2. El error de uso debe REMAPEARSE a 3, no solo documentarse. Un flag mal
   escrito no es una dimension que no se pudo comprobar.
3. La regla para decidir el futuro de `--rapido` se fijo ANTES de medir:
   mediana de 3 corridas; si lo omitido suma menos del 15% del total, se
   quita el flag. Fijarla antes evita decidir a posteriori lo que conviene.

## Actividades
- Se corrigio la aritmetica de la directive, que decia "6 nuevas mas 7
  reutilizadas" cuando son 7 y 6. Error mio del turno anterior, que se paso
  sin corregir porque la cuenta total (13) si cuadraba.
- `--dimension` no existia en el orquestador: solo estaba documentado, en
  `AGENTS.md`, en la directive y en el diagrama. El diagrama de la sesion
  anterior describia el contrato que el codigo no implementaba, con su nodo D1
  ("`--dimension` nombra algo que no existe") y su nodo T2 ("Salir con codigo
  3"). Documento o codigo, uno de los dos mentia. Ahora coinciden.
- Se anadio `--dimension` (append) al orquestador, conservando `--solo` como
  alias de lista, y ambas formas se unen: `--dimension texto --solo disco`
  restringe a las dos.
- `_Parser` en las dos capas remapea el error de argparse a 3. En la capa 3
  tambien cambio `return 2` a `return 3` para la raiz que no parece repo, que
  era el otro 2 sin sentido.
- Fallo propio al escribir el test: `FA._Parser()` construye un parser VACIO,
  porque los argumentos se anaden dentro de `main()` y no en el constructor.
  Se extrajo `construir_parser()` en las dos capas, lo que ademas deja el
  contrato del CLI inspeccionable sin ejecutar la auditoria entera.
- Se instrumento la duracion por dimension: `_cronometrar` envuelve el dict
  `DIMENSIONES_NUEVAS` (un solo punto de instrumentacion, no siete) y el
  orquestador cronometra cada dimension, nueva y reutilizada.

## Resultados medidos (mediana de 3 corridas)
- Completa: 43.5s. `--rapido`: 24.6s. Ahorro real de 18.9s (43%).
- Lo que `--rapido` omite (texto, barrera_disco, test_texto) son 15.9s de
  43.5s: un 36.6%. Por la regla fijada de antemano, el flag SE CONSERVA.
- Reparto del costo: disco 23.1%, texto 22.6%, secretos 18.8%, logs 15.4%,
  test_texto 11.7%, barrera_disco 3.0%. O sea, las 12 dimensiones restantes se
  llevan el 63.4%: `--rapido` no puede bajar de ~25s sin tocar las estructural.

### Correccion de una conclusion previa
- Mi hipotesis era que `--rapido` era inutil, y la primera medicion (41s con
  `--rapido` contra 39s sin el) la respaldaba. Era ruido de una sola toma. Con
  instrumentacion y mediana de 3, el ahorro es real y grande. Se conserva el
  flag y se documenta la cifra medida.
- Advertencia registrada: la varianza es enorme. `disco` tardo 10s en unas
  corridas y 27.8s en otra, con total de 63.6s. Las cifras de la directive son
  medianas, no garantias; no usarlas como timeout.

## Pendientes
- 12 referencias a scripts inexistentes en 10 directivas, y el detalle por
  fichero, en `2026-09-27_auditoria_higiene_repo.md`. Sin cambios.
- Disco al 91.3%: sin cambios.
- **Hueco de higiene del SISTEMA:** sin flujo con veredicto para RAM, CPU y
  servicios. Es trabajo nuevo de 3 capas, del tamaño del de repo, y quedo
  fuera de esta tanda por decision del usuario.
- `disco` es la dimension mas lenta y mas variable (10s a 27.8s). Si hay que
  ganar tiempo, es ahi: la causa de esa varianza no se investigo.
- Pendientes de otras sesiones, sin tocar: `-halt-on-error` en
  `compile_latex.py`, sobreestimacion del dry-run de disco, targets de purga,
  "5 celdas" a 4 en el canario de Colab, monitoring del saldo de OpenRouter.
