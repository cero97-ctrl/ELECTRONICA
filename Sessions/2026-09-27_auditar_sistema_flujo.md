# 2026-09-27 — auditar_sistema_flujo

## Tema
auditar_sistema_flujo

## Contexto
- (Por qué se aborda / eventos detectados que motivan la sesión.)

## Decisiones (usuario)
1. (Acuerdos explícitos del usuario. NO inventar; si no hay, anotar qué se
   asumió y por qué.)

## Actividades
- (Qué se hizo: pasos, scripts, salidas, veredictos.)

## Lo que se pidio

`flujo_auditar_sistema.py` para RAM, CPU y servicios. La razon de que la
auditoria de REPO no sirviera aqui es de alcance, no de facilidad: el repo es
nuestro y se puede arreglar; el margen del sistema esta en rutas de root que el
flujo no debe tocar. Mezclarlos haria que arreglar un .tex y redimensionar
particiones pesaran igual.

## Decision de no fusionar

Auditar y mantener separados A PROPOSITO. Si el que audita purga, un `fallo` y
un borrado son el mismo comando, y "arreglarlo" deja de ser una decision
consciente. Purgar sigue en `system_maintenance.yaml` y `flujo_disco.py`.

## El algebra no se duplico: se extrajo

`flujo_auditar_repo.py` tenia `clasificar_salud` definido dentro. El flujo nuevo
necesitaba exactamente el mismo. Copiarlo habria producido dos verdades que
divergen en silencio. Se movio a `execution/veredicto_algebra.py` y
`flujo_auditar_repo.py` lo reexporta, asi que sus 127 tests siguen pasando sin
tocarlos.

## Cuatro bugs de medicion, y los cuatro eran silenciosos

Ninguno habria salido con una ejecucion normal. Salieron porque los tests se
escribieron mirando el contrato, no el resultado.

1. **`indice_load` apuntaba al loadavg de 15 min mientras su comentario decia
   5 min.** El veredicto de CPU salia de la columna equivocada y el resumen
   mientia sobre cual era. Ademas mi primer test afirmaba que "load 2 en 2
   nucleos es saturacion": es exactamente el umbral de aviso, no fallo. El
   segundo bug estaba en el test, que es peor.
2. **Un servicio `loaded`+`inactive` caia en `no_verificado` en vez de `aviso`.**
   Mi regla escrita decia "instalado y parado = aviso" y el codigo decia otra
   cosa. Peor: `LoadState` se evaluaba en un orden que hacia que "no instalado"
   y "instalado y parado" acabaran en el mismo cubo.
3. **`_leer_psi` exigia dos puntos que `/proc/pressure` no tiene.** El formato
   real es `some avg10=... avg60=...`, sin dos puntos. Devolvia `None` SIEMPRE,
   en la maquina real tambien, asi que el guardia de PSI estaba muerto. Y como
   PSI ausente es indistinguible de un kernel sin CONFIG_PSI, nadie lo notaba.
4. **`some` y `full` se pisaban.** `/proc/pressure` trae DOS filas por recurso, y
   al guardarlas con claves planas la segunda (`full`, que suele ir a 0)
   sobreescribia a la primera. La presion de CPU se reportaba como **0.0
   siendo 33.09**: subestimar la presion es peor que no medirla.

El 3 y el 4 los cazo el mismo test. El patron: los dos bugs de parseo estaban en
el MISMO sitio porque los escribi a la vez, y el test que los caza tambien
miraba el mismo sitio. Escribe los parsers por separado de los tests.

## La falsa alarma que el flujo evita por construccion

zram al 88% con compresion 4.5x, y el veredicto dice `ok`. zram es RAM
COMPRIMIDA: llenarse es su estado de diseno. El veredicto lo lleva el swap en
disco (11%), que si es senal de presion. Si se juntaran, o por alarma a un 88%
normal o por falso verde al promediar. El `accion` lo dice explicitamente para
que el numero no se lea sin su contexto.

Igual con los servicios: `not-found` no es estar caido. Sin esa distincion,
instalar el repo en una maquina sin Waydroid daria un `fallo` falso.

## Bug encontrado de paso: `--solo` no acumulaba

`python3 flujo_auditar_repo.py --solo bitacoras --solo texto` ejecutaba **solo
`texto`**. Con `default=""`, la segunda repeticion sobrescribia a la primera y se
perdia trabajo pedido sin decir nada. `argparse` no avisa de eso. Corregido en
los dos flujos (`action="append"`) y con regresion en las dos suites. Actualizar
un test que afirmaba el contrato viejo (que el flag fuera una cadena) tambien
era parte del trabajo: el contrato cambio a proposito y el test tambien.

## El flujo puede medir su propia carga

Una pasada de auditoria no es trivial. Durante el desarrollo, `cpu` salia en
`aviso` con carga 1.7/nucleo porque YO estaba corriendo las suites. Publicar eso
como averia seria mentir. El informe lo dice en sus notas y en la accion del
dimension, en vez de presentar un numero sin contexto.

## Lo que NO se hizo, a proposito

- **No fusionar con la auditoria de repo.** Alcance distinto, riesgo distinto.
- **No purgar, ni reiniciar, ni sudo.** Es lo que hace `fallo` y `borrado` dos
  comandos en vez de uno.
- **No marcar la GPU como `aviso`.** La ausencia de GPU discreta es un HECHO del
  entorno, no un defecto. Marcarla aviso haria que el veredicto global no pudiese
  ser `limpio` nunca en esta maquina, y un veredicto que no distingue "todo bien"
  de "todo bien y sin GPU" no sirve para detectar una degradacion real. El hecho
  y la regla de Colab van en el resumen y en la accion, que se emiten siempre.
- **Umbrales como constantes, no como flags.** Cambiar un umbral es cambiar la
  politica: se commitea. Como flag, el mismo comando en dos maquinas daria dos
  veredictos y el informe no podria decir con cuales se hizo. El informe lleva
  los umbrales DENTRO por eso.

## Un aviso al usuario, y uno al motor

El veredicto que salio al terminar: `con_avisos` (exit 0), con `cpu` en aviso
por carga sostenida y `memoria` llegando al borde del 75% mientras corrian las
suites. Los dos son reales y son reales: en 3.6 GB con 2 nucleos, dos cores y una
suite de tests encima dan para eso. `disco` sigue en `fallo` en la auditoria de
repo, y no lo arregla este flujo.

## El quinto bug lo encontro la auditoria de si misma

`estado_sesion.py check` marco el estado de este flujo como `no_verificable`,
pese a que su log append-only estaba COMPLETO: `flujo/inicio` y `flujo/fin` con
su exit code. El log no era el problema. La vista se llamaba
`run_state_sistema.json` mientras su log se llamaba
`session_log_auditar-sistema-<ts>.jsonl`, y `estado_sesion.py` deriva el
`run_id` del NOMBRE del fichero, no del campo JSON. Nombres distintos, pairing
imposible.

Un log completo con estado huerfano se leeria como "nunca se ejecuto". Es peor
que no haber registrado nada, porque el sistema afirma haber medido.

## Y el sexto: el andamio no debe sobrevivir a la obra

Arreglado el nombre, el estado paso a `huerfano`, que tambien esta mal. Este
flujo es de UNA sola pasada: cuando cierra, una vista de estado puesta es un
huerfano por construccion, y `estado_sesion.py` avisa de que los huerfanos
envenenan las respuestas MCP. O sea: un flujo que deja huerfano en cada
exito, por diseño.

La vista se escribe ahora al empezar (si el proceso muere, se ve hasta donde
llego) y se retira al cerrar. El log append-only es la verdad permanente y
nunca se toca. Se decidio con intencion: la auditoria de higiene mide la frescura
del estado, y un flujo que knowingly lo envenena cada vez que se ejecuta
merece que su propia auditoria lo delate.

## El coste de medir

La corrida final dio `con_avisos` con RAM al 85% y carga 1.96/nucleo sobre 2.
Causa real: `opencode` al 87% de CPU y 22% de RAM, mas el navegador. O sea, el
INSTRUMENTO que audita es parte de la carga que reporta. No es una averia del
equipo y el veredicto no lo disguise: lo declara `aviso` y lo explica. Por eso
el informe lleva esa advertencia en sus notas en vez de presentar el numero
suelto, que es justo lo que hace mal a un numero de carga.

## Pendientes
- (Qué queda abierto; pendientes acordados de otras sesiones que NO se tocaron.)
