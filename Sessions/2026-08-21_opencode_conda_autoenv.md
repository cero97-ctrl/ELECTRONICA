# Sesión: Auto-activación de entorno conda en opencode (plugin shell.env)

**Fecha:** 2026-08-21
**Agente:** opencode

## Tema tratado
El usuario pregunta si existe una forma de que opencode entre automáticamente en un
entorno conda determinado al iniciar operaciones en un espacio de trabajo, evitando
depender de que el agente recuerde activarlo (o usar `conda run`) en cada sesión.

## Investigación
Se consultó la documentación oficial y el schema de configuración:
- `https://opencode.ai/config.json` — no existe clave `env` global; `shell` solo cambia el binario.
- `https://opencode.ai/docs/plugins` — hook **`shell.env`**: inyecta variables de entorno
  en TODA ejecución de shell (herramienta bash del agente + terminal del usuario).
- Los plugins locales se auto-descubren en `.opencode/plugins/` (o `.opencode/plugin/`)
  al arrancar opencode; no requieren entrada en `opencode.json`.

## Opciones evaluadas
| Opción | Mecanismo | Veredicto |
|---|---|---|
| A: plugin `shell.env` | PATH prepend + CONDA_* vars por hook | Elegida: determinista, por proyecto, sin tocar el shell del sistema |
| B: `"shell"` → wrapper | Script que hace source de conda.sh, activa y exec bash | Más frágil: depende de cómo opencode invoca el binario con argumentos |
| C: instrucción en `.agent/` | Ordenar al agente usar `conda run -n env` | Probabilística (depende del cumplimiento del modelo); choca con el espíritu determinista |

## Implementación
- Creado `.opencode/plugins/conda-env.js`: plugin con hook `shell.env` que antepone
  `/home/cero/anaconda3/envs/elect_env/bin` al PATH y fija `CONDA_PREFIX`,
  `CONDA_DEFAULT_ENV=elect_env` y `VIRTUAL_ENV` — réplica del efecto de
  `conda activate elect_env`.
- Alcance: solo este workspace. Otros proyectos pueden replicar el plugin con su propio env.

## Decisiones
- Enfoque A (plugin) aprobado por el usuario tras comparar las tres alternativas.
- No se modificó `opencode.json` (el plugin se auto-carga por directorio).

## Verificación (post-reinicio) — APROBADA
Sesión posterior al reinicio confirma el hook activo en las shells de opencode:
```
which python          → /home/cero/anaconda3/envs/elect_env/bin/python
python --version      → Python 3.10.20
CONDA_DEFAULT_ENV     → elect_env
CONDA_PREFIX          → /home/cero/anaconda3/envs/elect_env
```

## Nota de rendimiento del primer arranque
El reinicio con el plugin tardó ~31 s extra (ventana config→init del log de
`~/.local/share/opencode/log/opencode.log`, run=0421c769: 14:47:58→14:48:29 UTC).
Causa raíz: al detectar `.opencode/plugins/`, opencode auto-generó
`.opencode/package.json` (dep `@opencode-ai/plugin@1.18.20`), `package-lock.json`
y ejecutó `bun install` → `.opencode/node_modules` (63 MB). Costo único de red;
arranques siguientes reutilizan el caché. Verificado en reentrada (run=cf9b2225,
15:02 UTC): ventana creating-instance→init de ~3.2 s y hook activo
(`which python` → elect_env/bin/python). El scaffolding generado trae su propio
`.gitignore` (excluye node_modules/package*.json/bun.lock), así que solo el plugin
queda rastreable por git. Los WARN "duplicate skill name" (skills duplicadas entre
`~/.claude/skills/` y `~/.config/opencode/skills/`) son preexistentes y ajenos.

## Ajustes de cierre (mismo día)
1. **Robustez del plugin:** guard `existsSync(prefix/bin/python)` evaluado una vez al
   arrancar; si el env no existe (reinstalación/mudanza de anaconda) el hook no inyecta
   nada (shells heredan PATH del sistema) y emite `console.warn` en el arranque.
2. **Documentación:** bullet nuevo en `AGENTS.md` → "Know before you act": las shells de
   opencode de este workspace arrancan en `elect_env` vía el plugin; no re-activar ni
   usar `conda run`; si `CONDA_DEFAULT_ENV` desaparece, revisar el plugin.

## Pendientes
- Ninguno bloqueante. Commits ejecutados al cierre (autorizados por el usuario).
