// Activa automáticamente el entorno conda `elect_env` en todas las
// ejecuciones de shell de opencode (herramienta bash del agente y
// terminal del usuario) dentro de este workspace.
//
// El hook "shell.env" inyecta las variables ANTES de cada sesión de
// shell, replicando el efecto de `conda activate elect_env`
// (PATH prepend + CONDA_PREFIX/CONDA_DEFAULT_ENV/VIRTUAL_ENV).
//
// Requiere reiniciar opencode tras cualquier cambio en este archivo:
// los plugins solo se cargan al arrancar.
export const CondaEnvPlugin = async () => {
  const prefix = "/home/cero/anaconda3/envs/elect_env"
  return {
    "shell.env": async (input, output) => {
      output.env.PATH = `${prefix}/bin:${output.env.PATH || process.env.PATH}`
      output.env.CONDA_PREFIX = prefix
      output.env.CONDA_DEFAULT_ENV = "elect_env"
      output.env.VIRTUAL_ENV = prefix
    },
  }
}
