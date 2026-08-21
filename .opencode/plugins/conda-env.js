// Activa automáticamente el entorno conda `elect_env` en todas las
// ejecuciones de shell de opencode (herramienta bash del agente y
// terminal del usuario) dentro de este workspace.
//
// El hook "shell.env" inyecta las variables ANTES de cada sesión de
// shell, replicando el efecto de `conda activate elect_env`
// (PATH prepend + CONDA_PREFIX/CONDA_DEFAULT_ENV/VIRTUAL_ENV).
//
// Robustez: si el prefijo del env no existe (reinstalación/mudanza de
// anaconda), no inyecta nada y la shell hereda el PATH del sistema en
// lugar de romper; avisa una vez por arranque.
//
// Requiere reiniciar opencode tras cualquier cambio en este archivo:
// los plugins solo se cargan al arrancar.
import { existsSync } from "node:fs"

export const CondaEnvPlugin = async () => {
  const prefix = "/home/cero/anaconda3/envs/elect_env"
  const disponible = existsSync(`${prefix}/bin/python`)
  if (!disponible) {
    console.warn(
      `[conda-env] ${prefix}/bin/python no existe — hook shell.env inactivo; ` +
      `las shells usarán el PATH heredado. Revisa la ruta del env.`,
    )
  }
  return {
    "shell.env": async (input, output) => {
      if (!disponible) return
      output.env.PATH = `${prefix}/bin:${output.env.PATH || process.env.PATH}`
      output.env.CONDA_PREFIX = prefix
      output.env.CONDA_DEFAULT_ENV = "elect_env"
      output.env.VIRTUAL_ENV = prefix
    },
  }
}
