# 2026-11-18 — opencode_v2_migracion_plugins

## Tema
opencode_v2_migracion_plugins

## Contexto
- El usuario actualizó OpenCode a la rama 2.x (runtime detectado: **v2.3.2**) y los
  plugins de shell del workspace dejaron de tener efecto: las shells del agente ya no
  activaban `elect_env` ni anteponían el Node de nvm.
- Diagnóstico en `~/.local/share/opencode/log/opencode.log`: OpenCode **sí descubre**
  `.opencode/plugins/conda-env.js` y `.opencode/plugins/nvm-env.js`, pero los rechaza:
  `Plugin must export a default definition with an id and an effect or setup function.
  (cause: SchemaError(Missing key at ["default"]))`.
- Causa raíz: OpenCode 2 cambió la **API de plugins** (breaking change intencional V1→V2,
  documentado en `https://opencode.ai/docs/build/plugins/migrate-v1`). Los plugins estaban
  escritos con el contrato V1: export nombrado que devuelve un objeto de hooks por clave
  string y hook `shell.env(input, output)` mutando `output.env`.
- Secundario: `.opencode/package.json` dependía de `@opencode-ai/plugin@1.18.20` (namespace
  y versión V1), mientras V2 importa `@opencode/plugin` y debe coincidir con el runtime.

## Decisiones (usuario)
1. Tras el diagnóstico, el usuario aprobó migrar los plugins a la API v2 (no mantener una
   implementación dual V1/V2: el workspace usa solo 2.x).
2. Mantener el mismo comportamiento y robustez que la versión V1: prepend de PATH, variables
   `CONDA_*`/`VIRTUAL_ENV`, fallback de nvm a la mayor versión instalada y aviso + hook
   inactivo si el prefijo/versión desaparece.
3. Fijar `@opencode/plugin` en `.opencode/package.json` a la **misma versión del runtime**
   (2.3.2) en vez de `latest`, por reproducibilidad; al subir OpenCode hay que subir el pin.

## Actividades
- Verificación de la API real instalada (`node_modules/@opencode/plugin/dist/promise/*.d.ts`
  tras `npm install`): `Plugin.define` es identidad, el contexto expone `ctx.shell.hook`, y el
  evento `create.before` trae `env: Record<string, string | undefined>` mutable.
- Reescritura de `.opencode/plugins/conda-env.js`: `export default Plugin.define({ id:
  "workspace.conda-env", setup(ctx) { … ctx.shell.hook("create.before", (event) => { … }) } })`.
- Reescritura de `.opencode/plugins/nvm-env.js`: mismo patrón con `id: "workspace.nvm-env"`,
  conservando `mayorVersion()` y el fallback a la mayor instalada.
- `.opencode/package.json`: `@opencode-ai/plugin@1.18.20` → `@opencode/plugin@2.3.2`;
  `npm install` en `.opencode/` (271 paquetes). Ese `package.json` está gitignored por
  `.opencode/.gitignore`, así que el cambio es local a la máquina.
- Prueba funcional determinista sin depender del runtime de OpenCode: copias en
  `/tmp/opencode/plugin_test/` con el import reemplazado por un mock (`Plugin.define = x => x`,
  fiel a la implementación real) y un `ctx` falso que captura el hook. Resultado **13/13 OK**:
  `id`/`setup` presentes, registro de `create.before`, prepend correcto, PATH original
  conservado, `CONDA_PREFIX`/`CONDA_DEFAULT_ENV`/`VIRTUAL_ENV` correctos y fallback nvm.
- Verificación en caliente (sin reiniciar): el log muestra recarga a las 11:21:55 UTC para
  ambos plugins **sin** `failed to load plugin` posterior (los últimos fallos son de 11:15:04,
  antes del arreglo).
- Verificación en shells reales del agente: `CONDA_DEFAULT_ENV=elect_env`,
  `CONDA_PREFIX=/home/cero/anaconda3/envs/elect_env`, `python` → Python 3.10.20 del env,
  `node` → v22.23.1 desde `~/.nvm/versions/node/v22.23.1/bin`.
- `AGENTS.md`: actualizadas las dos viñetas de los plugins (antes decían hook `shell.env` y
  "requiere reinicio"); ahora documentan `Plugin.define`/`create.before`, el pin de versión y
  la recarga en caliente (`/reload` si no).
- `python3 execution/estado_sesion.py check` → veredicto global `ok` (sin huérfanos).
- `python3 execution/bitacoras.py nueva --tema "opencode_v2_migracion_plugins"` → este archivo.

## Notas
- **Orden del PATH:** ahora queda `nvm/bin` antes de `elect_env/bin` (antes la bitácora de
  2026-08-26 registraba el orden inverso). No es funcional: `elect_env/bin` no contiene
  `node`/`npm` y `nvm/bin` no contiene `python`, así que cada herramienta resuelve igual. El
  orden relativo depende del orden de carga/registro de plugins, que es del runtime.
- Los `git status` del repo arrastraban trabajo previo del usuario (SARA, actas, AGENTS.md,
  etc.); esta sesión solo toca los dos plugins, la bitácora y las dos viñetas de `AGENTS.md`.

## Aclaración de los «dos detalles» (verificada, no supuesta)

El usuario preguntó si hacía falta resolverlos. Se comprobó en vez de razonar:

**1. Orden del PATH (`nvm/bin` antes de `elect_env/bin`) — NO hay nada que resolver.**
`ls /home/cero/anaconda3/envs/elect_env/bin | grep -E '^node(js)?$|^npm$|^npx$'` → sin
resultados. No hay solapamiento de binarios: cada herramienta tiene un único proveedor y el
orden relativo es irrelevante. Forzar un orden exigiría acoplar los dos plugins (uno tendría
que conocer al otro), lo que añade fragilidad a cambio de cero efecto.

**2. Pin de `@opencode/plugin` — el diagnóstico inicial era FALSO.** Se creía que hacía
falta `node_modules` local con el paquete en la versión del runtime. Sonda decisiva:
se movió `.opencode/node_modules` fuera y se creó `.opencode/plugins/zz-sonda.js` que importa
`@opencode/plugin` → **cargó sin error** (`loading plugin` + `watcher started`, ningún
`failed to load plugin`). Control negativo con `import … from "este-paquete-no-existe-xyz"`
con `node_modules` igualmente ausente → **sí falló** (`Cannot find package …`), lo que prueba
que la resolución no venía del `node_modules` local y que la sonda era capaz de fallar.
Conclusión: **el runtime v2 provee el módulo**; el `package.json` + `node_modules` local
(434 MB) solo aporta tipos al editor y es opcional.
Corregido en `AGENTS.md`: la viñeta de `conda-env` (ya no menciona el pin como requisito),
la fila «Deps de los plugins locales» de la tabla de migración y el paso 5 del checklist.

## Pendientes
- **Decisión del usuario (resuelta):** `.opencode/node_modules/` (434 MB, gitignored) se
  **borró**; los plugins siguen cargando (verificado en el log tras el borrado: `loading
  plugin` para ambos sin fallo posterior, y `python`/`node` siguen resolviendo al env y a
  nvm). Se conservan `.opencode/package.json` y `package-lock.json` (128 KB) para poder
  reinstalar con `npm install` si algún día se quieren tipos en el editor.
- `AGENTS.md` **no** se commiteó: el archivo traía cambios previos del usuario sin commitear
  (conteos de tests, flujo de Sara) y no corresponde mezclarlos en un commit de plugins.
- La bitácora de 2026-08-21 y la de 2026-08-26 describen el contrato V1 (`shell.env`,
  reinicio obligatorio). Se dejan como registro histórico; la fuente vigente es `AGENTS.md`
  y el propio código de los plugins.
