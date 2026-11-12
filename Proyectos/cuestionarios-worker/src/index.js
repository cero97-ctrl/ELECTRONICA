// Worker de entregas: valida, califica con la clave del servidor y archiva la
// entrega en un repositorio privado. La clave NUNCA se envía al navegador.

import {
  MAX_CUERPO,
  calificar,
  contenidoResultado,
  rutaResultado,
  validarClave,
  validarCuestionario,
  validarEntrega,
} from "./logica.js";

const CABECERAS_JSON = { "Content-Type": "application/json; charset=utf-8" };

function cors(origen, env) {
  const permitidos = String(env.ORIGENES || "")
    .split(",")
    .map((valor) => valor.trim())
    .filter(Boolean);
  const cabeceras = {
    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  };
  if (origen && permitidos.includes(origen)) {
    cabeceras["Access-Control-Allow-Origin"] = origen;
  }
  return cabeceras;
}

function responder(cuerpo, estado, extra) {
  return new Response(JSON.stringify(cuerpo), {
    status: estado,
    headers: { ...CABECERAS_JSON, "Cache-Control": "no-store", ...extra },
  });
}

function base64(texto) {
  const bytes = new TextEncoder().encode(texto);
  let binario = "";
  for (const byte of bytes) binario += String.fromCharCode(byte);
  return btoa(binario);
}

async function guardarEnRepo(env, ruta, contenido, mensaje) {
  const url = `https://api.github.com/repos/${env.REPO_RESULTADOS}/contents/${ruta}`;
  const cabeceras = {
    Authorization: `Bearer ${env.GITHUB_TOKEN}`,
    Accept: "application/vnd.github+json",
    "User-Agent": "cuestionarios-worker",
    "X-GitHub-Api-Version": "2022-11-28",
  };
  let sha;
  const actual = await fetch(url, { headers: cabeceras });
  if (actual.status === 200) {
    const datos = await actual.json();
    sha = datos.sha;
  } else if (actual.status !== 404) {
    throw new Error(`no se pudo leer el archivo existente (${actual.status})`);
  }
  const cuerpo = {
    message: mensaje,
    content: base64(contenido),
    committer: {
      name: "cuestionarios-worker",
      email: "cuestionarios-worker@users.noreply.github.com",
    },
  };
  if (sha) cuerpo.sha = sha;
  const escritura = await fetch(url, {
    method: "PUT",
    headers: { ...cabeceras, "Content-Type": "application/json" },
    body: JSON.stringify(cuerpo),
  });
  if (!escritura.ok) {
    throw new Error(`no se pudo archivar la entrega (${escritura.status})`);
  }
}

export default {
  async fetch(request, env) {
    const origen = request.headers.get("Origin") || "";
    const cabeceras = cors(origen, env);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cabeceras });
    }

    if (origen && !cabeceras["Access-Control-Allow-Origin"]) {
      return responder({ error: "origen no permitido" }, 403, cabeceras);
    }

    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/salud") {
      return responder({ ok: true }, 200, cabeceras);
    }

    if (request.method !== "POST") {
      return responder({ error: "método no permitido" }, 405, cabeceras);
    }

    const clave = validarClave(
      (() => {
        try {
          return JSON.parse(env.CLAVE_JSON || "");
        } catch {
          return null;
        }
      })()
    );
    const cuestionario = validarCuestionario(env.CUESTIONARIO_ID);
    const grupos = Number(env.GRUPOS);
    if (!clave || !cuestionario || !Number.isInteger(grupos) || grupos < 1) {
      console.error("configuración incompleta: CLAVE_JSON, CUESTIONARIO_ID o GRUPOS");
      return responder({ error: "servicio no configurado" }, 500, cabeceras);
    }

    const texto = await request.text();
    if (texto.length > MAX_CUERPO) {
      return responder({ error: "entrega demasiado grande" }, 413, cabeceras);
    }
    let datos;
    try {
      datos = JSON.parse(texto);
    } catch {
      return responder({ error: "JSON inválido" }, 400, cabeceras);
    }

    const revision = validarEntrega(datos, {
      grupos,
      total: Object.keys(clave).length,
      cuestionario,
    });
    if (!revision.ok) {
      return responder(
        { error: "entrega inválida", detalles: revision.problemas },
        400,
        cabeceras
      );
    }

    const entrega = revision.entrega;
    const calculo = calificar(entrega.respuestas, clave);
    const ruta = rutaResultado(entrega);
    const contenido = contenidoResultado(
      entrega,
      calculo,
      new Date().toISOString()
    );
    try {
      await guardarEnRepo(
        env,
        ruta,
        contenido,
        `entrega ${entrega.cuestionario} ${entrega.cedula}`
      );
    } catch (error) {
      console.error("fallo al archivar:", error.message);
      return responder(
        { error: "no se pudo registrar la entrega; intenta de nuevo" },
        502,
        cabeceras
      );
    }

    return responder(
      { nota: calculo.nota, aciertos: calculo.aciertos, total: calculo.total },
      200,
      cabeceras
    );
  },
};
