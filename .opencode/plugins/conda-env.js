// Activa automáticamente el entorno conda `elect_env` en todas las
// ejecuciones de shell de opencode (herramienta bash del agente y
// terminal del usuario) dentro de este workspace.
//
// API de plugins de OpenCode v2 (Plugin.define + setup). El hook
// ctx.shell.hook("create.before") inyecta las variables ANTES de cada
// sesión de shell, replicando el efecto de `conda activate elect_env`
// (PATH prepend + CONDA_PREFIX/CONDA_DEFAULT_ENV/VIRTUAL_ENV).
//
// Robustez: si el prefijo del env no existe (reinstalación/mudanza de
// anaconda), no registra el hook y la shell hereda el PATH del sistema en
// lugar de romper; avisa una vez por carga del plugin.
//
// OpenCode v2 recarga plugins al cambiar este archivo; si no se recarga,
// basta `/reload` en la TUI.
import { existsSync } from "node:fs"
import { Plugin } from "@opencode/plugin"

export default Plugin.define({
  id: "workspace.conda-env",
  async setup(ctx) {
    const prefix = "/home/cero/anaconda3/envs/elect_env"
    const disponible = existsSync(`${prefix}/bin/python`)

    if (!disponible) {
      console.warn(
        `[conda-env] ${prefix}/bin/python no existe — hook inactivo; ` +
          `las shells usarán el PATH heredado. Revisa la ruta del env.`,
      )
      return
    }

    await ctx.shell.hook("create.before", (event) => {
      event.env.PATH = `${prefix}/bin:${event.env.PATH || process.env.PATH || ""}`
      event.env.CONDA_PREFIX = prefix
      event.env.CONDA_DEFAULT_ENV = "elect_env"
      event.env.VIRTUAL_ENV = prefix
    })
  },
})
