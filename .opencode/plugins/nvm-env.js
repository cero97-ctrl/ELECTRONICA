// Antepone la versión de Node gestionada por nvm al PATH de todas las
// ejecuciones de shell de opencode (herramienta bash del agente y
// terminal del usuario) dentro de este workspace.
//
// El hook "shell.env" inyecta el PATH ANTES de cada sesión de shell,
// replicando el efecto de `nvm use v22.23.1` en shells no interactivas
// (que no cargan ~/.bashrc y por tanto resuelven `node` al v18 del
// sistema). El node del sistema queda intacto como reserva.
//
// Robustez: si la versión fijada no existe (nvm la borró/migró), cae a
// la más alta instalada en ~/.nvm/versions/node/; si no hay ninguna,
// no inyecta nada y la shell hereda el PATH del sistema; avisa una vez
// por arranque.
//
// Requiere reiniciar opencode tras cualquier cambio en este archivo:
// los plugins solo se cargan al arrancar.
import { existsSync, readdirSync } from "node:fs"
import { join } from "node:path"

const NVM_ROOT = "/home/cero/.nvm/versions/node"
const NVM_VERSION = "v22.23.1"

const mayorVersion = (a, b) => {
  const pa = a.slice(1).split(".").map(Number)
  const pb = b.slice(1).split(".").map(Number)
  for (let i = 0; i < 3; i++) {
    if (pa[i] !== pb[i]) return pb[i] - pa[i]
  }
  return 0
}

export const NvmEnvPlugin = async () => {
  let nodeBin = null

  if (existsSync(join(NVM_ROOT, NVM_VERSION, "bin", "node"))) {
    nodeBin = `${NVM_ROOT}/${NVM_VERSION}/bin`
  } else if (existsSync(NVM_ROOT)) {
    const instaladas = readdirSync(NVM_ROOT)
      .filter((d) => /^v\d+\.\d+\.\d+$/.test(d))
      .sort(mayorVersion)
    if (instaladas.length > 0) {
      nodeBin = `${NVM_ROOT}/${instaladas[0]}/bin`
      console.warn(
        `[nvm-env] ${NVM_VERSION} no encontrada — usando fallback ${instaladas[0]}.`,
      )
    }
  }

  if (!nodeBin) {
    console.warn(
      `[nvm-env] Sin instalaciones de Node en ${NVM_ROOT} — hook shell.env ` +
        `inactivo; las shells usarán el node del sistema.`,
    )
  }

  return {
    "shell.env": async (input, output) => {
      if (!nodeBin) return
      output.env.PATH = `${nodeBin}:${output.env.PATH || process.env.PATH}`
    },
  }
}
