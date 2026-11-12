// Lógica pura del Worker de cuestionarios: sin red, sin bindings, testeable con
// `node --test`. Todo lo que decide (validar, calificar, nombrar el archivo) vive
// aquí; `index.js` solo transporta HTTP y GitHub.

export const LETRAS_VALIDAS = ["A", "B", "C", "D", "E"];
export const MAX_CUERPO = 4096;

const NOMBRE = /^[\p{L}\p{M} .'-]+$/u;
const CEDULA = /^([VEJ])?-?(\d{5,9})$/;
const CUESTIONARIO = /^[a-z0-9_]{3,60}$/;

export function normalizarNombre(valor) {
  if (typeof valor !== "string") return null;
  const texto = valor.trim().replace(/\s+/g, " ");
  if (texto.length < 3 || texto.length > 80) return null;
  if (!NOMBRE.test(texto)) return null;
  return texto;
}

export function normalizarCedula(valor) {
  if (typeof valor !== "string") return null;
  const texto = valor.trim().toUpperCase().replace(/[.\s]/g, "");
  const partes = CEDULA.exec(texto);
  if (!partes) return null;
  return (partes[1] || "V") + "-" + partes[2];
}

export function normalizarGrupo(valor, grupos) {
  const numero =
    typeof valor === "number" ? valor : Number(String(valor ?? "").trim());
  if (!Number.isInteger(numero)) return null;
  if (numero < 1 || numero > grupos) return null;
  return numero;
}

export function normalizarRespuestas(valor, total) {
  if (!valor || typeof valor !== "object" || Array.isArray(valor)) return null;
  const respuestas = {};
  for (let numero = 1; numero <= total; numero += 1) {
    const letra = valor[String(numero)];
    if (typeof letra !== "string") return null;
    if (!LETRAS_VALIDAS.includes(letra)) return null;
    respuestas[String(numero)] = letra;
  }
  const sobran = Object.keys(valor).filter((clave) => {
    const numero = Number(clave);
    return !Number.isInteger(numero) || numero < 1 || numero > total;
  });
  if (sobran.length > 0) return null;
  return respuestas;
}

export function validarEntrega(datos, opciones) {
  const { grupos, total, cuestionario } = opciones;
  const problemas = [];
  if (!datos || typeof datos !== "object" || Array.isArray(datos)) {
    return { ok: false, problemas: ["el cuerpo no es un objeto"], entrega: null };
  }
  if (datos.cuestionario !== cuestionario) {
    problemas.push("cuestionario desconocido");
  }
  const nombre = normalizarNombre(datos.nombre);
  if (!nombre) problemas.push("nombre inválido");
  const cedula = normalizarCedula(datos.cedula);
  if (!cedula) problemas.push("cédula inválida");
  const grupo = normalizarGrupo(datos.grupo, grupos);
  if (!grupo) problemas.push(`grupo fuera de 1..${grupos}`);
  const respuestas = normalizarRespuestas(datos.respuestas, total);
  if (!respuestas) {
    problemas.push(`respuestas incompletas o fuera de 1..${total}`);
  }
  if (problemas.length > 0) return { ok: false, problemas, entrega: null };
  return {
    ok: true,
    problemas,
    entrega: { cuestionario, nombre, cedula, grupo, respuestas },
  };
}

export function calificar(respuestas, clave) {
  const numeros = Object.keys(clave).sort((a, b) => Number(a) - Number(b));
  let aciertos = 0;
  for (const numero of numeros) {
    if (respuestas[numero] === clave[numero]) aciertos += 1;
  }
  const total = numeros.length;
  const nota = total === 0 ? 0 : Math.round((10 * aciertos * 100) / total) / 100;
  return { aciertos, total, nota };
}

export function rutaResultado(entrega) {
  const grupo = String(entrega.grupo).padStart(2, "0");
  return `resultados/${entrega.cuestionario}/grupo_${grupo}/${entrega.cedula}.json`;
}

export function contenidoResultado(entrega, calculo, enviadoEn) {
  return (
    JSON.stringify(
      {
        cuestionario: entrega.cuestionario,
        nombre: entrega.nombre,
        cedula: entrega.cedula,
        grupo: entrega.grupo,
        respuestas: entrega.respuestas,
        aciertos: calculo.aciertos,
        total: calculo.total,
        nota: calculo.nota,
        enviado_en: enviadoEn,
      },
      null,
      2
    ) + "\n"
  );
}

export function validarClave(valor) {
  if (!valor || typeof valor !== "object" || Array.isArray(valor)) return null;
  const numeros = Object.keys(valor);
  if (numeros.length === 0) return null;
  const clave = {};
  for (const numero of numeros) {
    if (!/^\d+$/.test(numero)) return null;
    const letra = valor[numero];
    if (typeof letra !== "string" || !LETRAS_VALIDAS.includes(letra)) return null;
    clave[numero] = letra;
  }
  return clave;
}

export function validarCuestionario(valor) {
  if (typeof valor !== "string" || !CUESTIONARIO.test(valor)) return null;
  return valor;
}
