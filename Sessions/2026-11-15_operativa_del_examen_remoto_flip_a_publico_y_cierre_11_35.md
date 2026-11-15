# 2026-11-15 — operativa del examen remoto: flip a publico y cierre 11:35

## Tema
Decidir y probar la operativa del día del examen (16-nov): cuándo se abre la
página, qué pasa si se va la luz antes de la hora, y cómo se comunica a los
alumnos.

## Contexto
- El examen se rinde desde casa el lunes 16-nov, 10:40 (UTC−4), con el repo de
  Pages oculto (privado, 404) hasta ese momento.
- Pregunta del usuario: qué ocurre si a un alumno se le va el fluido eléctrico
  **antes** de las 10:40. Al revisar el código aparecieron cuatro huecos:
  1. `inicio` se sella al cargar la página (`md_a_html.py:1003`), no al abrir la
     ventana → un borrador abierto antes de las 10:40 infla `duracion_s`, que es
     columna del acta (`descargar_resultados.py:381`).
  2. La ventana solo se valida en el POST (`index.js:118`): la página es estática
     y funciona antes de las 10:40, así que se podían leer y responder las
     preguntas con antelación.
  3. Si la luz se va **durante** el envío y la petición llegó, el reintento da
     409 «duplicada» y la página lo muestra como un problema de conexión.
  4. El aviso no mencionaba la hora de inicio.
- Ventana desplegada hasta hoy: 10:40–11:30 (50 min). El usuario aclaró que el
  examen dura 45 min, así que los 5 restantes son holgura.

## Decisiones (usuario)
1. **Abrir la página el lunes a las 10:40**, avisando por WhatsApp que Pages
   puede tardar unos minutos en servirla.
2. **Cierre a las 11:35** (45 min de examen + 5 de holgura). Cierre común para
   todos, no se mueve por retrasos: un cierre por alumno exigiría un endpoint de
   inicio que no existe (el Worker solo ve el POST).
3. **Probar hoy el flip a público en un repo desechable**, sin exponer preguntas.
4. **Arreglar el bug del `--push`** (`--push --visibilidad public` dejaba el repo
   público pero sin Pages, porque `privado` se calculaba antes del cambio).
5. **Redactar el mensaje de WhatsApp** para los alumnos.
6. Dejar los cambios de SARA/HECTOR y la bitácora del 11-12 para su sesión.
7. **Contingencia por corte eléctrico**: el alumno avisa por WhatsApp; se verifica
   con el reporte de una app Android que registra **inicio y fin del corte
   eléctrico, no del internet**; solo a los verificados se les da recuperación.
8. **Un examen nuevo por grupo (hasta 4), al día siguiente (17-nov), por la
   mañana, en el mismo sitio**, con preguntas **distintas** escritas por el
   docente. No se reabre la ventana del examen regular: las preguntas ya se
   conocieron y el acta recalcularía las entregas regulares con la clave nueva.
9. **Fusionar las actas** (regular + recuperación) con un script determinista de
   3 capas, en vez de editar el CSV a mano.
10. **Archivar los HTML regulares en local** antes de publicar la recuperación,
    para poder reutilizarlos si hiciera falta.

## Actividades
- **Bug del `--push` corregido** en `execution/publicar_cuestionario.py`: las dos
  ramas (solo visibilidad y `--push`) pasan por una única
  `_transicion_visibilidad()`, que cambia la visibilidad y **después** habilita
  Pages si el repo quedó público. Se eliminó la duplicación que hacía divergir
  las ramas. Test nuevo `test_transicion_visibilidad` (23 → **36 aserciones**).
- Mismo bug corregido en `execution/publicar_material_sara.py` (reordenado igual;
  el archivo sigue untracked, es de la sesión de Sara). Sus 29 aserciones pasan.
- **Ventana a 11:35 en los 4 Workers**: `--inicio 2026-11-16T14:40:00Z --fin
  2026-11-16T15:35:00Z` con la fuente de cada rol. Los 4 devuelven `salud: true`,
  `inscritas: 8`, `abierta: false`. `CEDULAS` no se tocó (el flujo salta los
  secretos vacíos).
- **Flip a público probado en dos repos desechables** (privados, con un
  `index.html` de prueba, borrado del examen fuera):
  - repo sin 404 previo: `--visibilidad public` → 200 en **43 s**;
  - repo con el 404 ya cacheado por el borde (3 peticiones previas): 200 en
    **50 s**; el 404 no se queda pegado.
  - Sentido inverso: `--visibilidad private` → repo privado y `has_pages: false`
    en 3 s, pero la URL siguió sirviendo 200 (caché `max-age=600`), como ya
    documentaba la directiva.
- Directivas actualizadas: `entregar_respuestas_worker.yaml` (fin 15:35 y por qué
  lleva 5 min de holgura) y `publicar_cuestionario.yaml` (rutina del día del
  examen con los tiempos medidos y el caso del 404 cacheado).
- **Mensaje de WhatsApp redactado** (abajo), con URL, aviso de que puede tardar,
  «si sale 404 espera y recarga», reglas del borrador y hora de cierre.
- **Contingencia documentada** en `directives/entregar_respuestas_worker.yaml`:
  disparador, protocolo de verificación (la app mide el corte eléctrico, no el
  internet; el intervalo debe solaparse con 10:40–11:35), examen por grupo al día
  siguiente, nombres de entorno/Worker/HTML, archivado de los HTML regulares,
  cierre y casos límite. YAML validado con `yaml.safe_load`.
- **Script de fusión de actas** (3 capas): `execution/fusionar_actas.py` (unión
  por cédula normalizada con `normalizar_cedula`, conflicto = código 3, columna
  `origen`, salida solo en rutas ignoradas por git), `directives/fusionar_actas.yaml`,
  `flujo_fusionar_actas.py` (verifica `filas == regular + recuperación`) y
  `execution/test_fusionar_actas.py` (**23 aserciones**). Probado a mano con
  actas sintéticas: unión, conflicto y JSON.

## Mensaje de WhatsApp (para enviar a las 10:40)

> Buenos días. Ya está abierto el cuestionario de hoy.
>
> Enlace: https://cero97-ctrl.github.io/cuestionarios/
>
> Entra por ese enlace y elige el cuestionario de tu grupo. Tienen hasta las
> **11:35**; el cierre es el mismo para todos y no se mueve.
>
> Es posible que durante el primer minuto la página todavía no cargue. Si te
> sale un error **404**, espera un minuto y recarga: no es que el examen se cayó,
> es que GitHub está tardando en publicarlo.
>
> Si un problema técnico te impide presentar, escríbeme de inmediato con la
> captura del reporte de la app.
>
> Antes de empezar, lean el recuadro amarillo. En resumen:
> - Abran el repositorio de su grupo en **otra pestaña** (es privado: necesitan
>   su sesión de GitHub). No naveguen fuera de la página del examen en la misma
>   pestaña.
> - **No usen incógnito** ni otro navegador: ahí el borrador no se guarda.
> - La página guarda un borrador: si se va la luz o se cierra el navegador,
>   vuelvan al enlace y lo retoman donde iban (vale hasta 24 horas).
> - Pueden copiar y pegar su evidencia; queda anotado en el acta, pero **no
>   invalida** la entrega.
> - Consulten el repositorio **antes** de marcar: una vez que marcan, la
>   respuesta queda fija.
>
> Cuando terminen, pulsen «Enviar mis respuestas» y esperen el mensaje de
> confirmación. La nota no se muestra: se publica en el acta.

## Pendientes
- **Lunes 10:40**: `python3 flujo_publicar_cuestionario.py --visibilidad public`;
  a los 60 s, `curl` de las 4 URLs; enviar el WhatsApp. A las **11:35**,
  `--visibilidad private` (el contenido deja de servirse cuando expira la caché,
  hasta ~10 min después).
- **P1 y P3 no implementados** (el usuario no los pidió): recortar `duracion_s`
  contra `VENTANA_INICIO` y tratar el 409 como «ya entregaste». Con la apertura a
  las 10:40, P1 pierde su motivo principal; P3 sigue valiendo para el corte de
  luz durante el envío.
- **Borrar los dos repos de prueba**: el token de `gh` no tiene `delete_repo`
  (401/scope). `gh auth refresh -h github.com -s delete_repo` y luego
  `gh repo delete cero97-ctrl/prueba-pages-desechable --yes` y
  `gh repo delete cero97-ctrl/prueba-pages-cache404 --yes`. Son privados y solo
  contienen un `index.html` de prueba.
- **Fase C (16-nov tarde)**: con las cédulas verificadas, escribir los 4 canónicos
  de recuperación, `barajar` + `dividir`, añadir los 4 entornos a
  `wrangler.jsonc`, desplegar cerrados (ventana 17-nov 13:00–13:45Z) y generar el
  HTML sin publicar.
- **Fase D (17-nov mañana)**: archivar los HTML regulares, publicar a las 08:50,
  ventana 09:00–09:45, ocultar a las 09:45, 4 actas de recuperación y fusión.
- **Hora del 17 fijada**: 09:00–09:45 local (13:00–13:45Z), decidida por el
  usuario; es un `--inicio/--fin`, no un cambio de código.
- Sin commitear todavía: `execution/publicar_cuestionario.py`,
  `execution/test_publicar_cuestionario.py`, `execution/fusionar_actas.py`,
  `execution/test_fusionar_actas.py`, `flujo_fusionar_actas.py`, las tres
  directivas y esta bitácora. `execution/publicar_material_sara.py` sigue
  untracked (sesión de Sara).
