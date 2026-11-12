import test from "node:test";
import assert from "node:assert/strict";

import {
  MAX_CUERPO,
  calificar,
  contenidoResultado,
  normalizarCedula,
  normalizarGrupo,
  normalizarNombre,
  normalizarRespuestas,
  rutaResultado,
  validarClave,
  validarCuestionario,
  validarEntrega,
} from "../src/logica.js";

const CLAVE = { 1: "A", 2: "B", 3: "C", 4: "D", 5: "E", 6: "A", 7: "B", 8: "C", 9: "D", 10: "E" };
const TOTAL = Object.keys(CLAVE).length;

function entregaValida(extra = {}) {
  return {
    cuestionario: "rol_rojo_cuestionario",
    nombre: "Ana María Pérez",
    cedula: "12345678",
    grupo: 2,
    respuestas: Object.fromEntries(
      Object.entries(CLAVE).map(([numero, letra]) => [numero, letra])
    ),
    ...extra,
  };
}

test("nombre: acepta acentos y espacios múltiples", () => {
  assert.equal(normalizarNombre("  Ana   María Pérez "), "Ana María Pérez");
  assert.equal(normalizarNombre("José de la O"), "José de la O");
});

test("nombre: rechaza vacío, corto, dígitos y demasiado largo", () => {
  assert.equal(normalizarNombre(""), null);
  assert.equal(normalizarNombre("Al"), null);
  assert.equal(normalizarNombre("Ana 2"), null);
  assert.equal(normalizarNombre("x".repeat(81)), null);
  assert.equal(normalizarNombre(123), null);
  assert.equal(normalizarNombre("<script>"), null);
});

test("cédula: normaliza prefijo y separadores", () => {
  assert.equal(normalizarCedula("12345678"), "V-12345678");
  assert.equal(normalizarCedula("V-12.345.678"), "V-12345678");
  assert.equal(normalizarCedula(" v 12345678 "), "V-12345678");
  assert.equal(normalizarCedula("E-1234567"), "E-1234567");
  assert.equal(normalizarCedula("J12345678"), "J-12345678");
});

test("cédula: rechaza formatos inválidos", () => {
  assert.equal(normalizarCedula("1234"), null);
  assert.equal(normalizarCedula("1234567890"), null);
  assert.equal(normalizarCedula("V-12A45678"), null);
  assert.equal(normalizarCedula(""), null);
  assert.equal(normalizarCedula(null), null);
});

test("grupo: entero dentro del rango", () => {
  assert.equal(normalizarGrupo(4, 4), 4);
  assert.equal(normalizarGrupo("3", 4), 3);
  assert.equal(normalizarGrupo(0, 4), null);
  assert.equal(normalizarGrupo(5, 4), null);
  assert.equal(normalizarGrupo(1.5, 4), null);
  assert.equal(normalizarGrupo("", 4), null);
});

test("respuestas: exige exactamente 1..total y letras válidas", () => {
  const bien = normalizarRespuestas(
    Object.fromEntries(Array.from({ length: TOTAL }, (_, i) => [String(i + 1), "A"])),
    TOTAL
  );
  assert.equal(Object.keys(bien).length, TOTAL);
  const falta = normalizarRespuestas({ 1: "A" }, TOTAL);
  assert.equal(falta, null);
  const sobran = normalizarRespuestas(
    { ...bien, 11: "A" },
    TOTAL
  );
  assert.equal(sobran, null);
  const letraMala = normalizarRespuestas({ ...bien, 3: "F" }, TOTAL);
  assert.equal(letraMala, null);
  const minuscula = normalizarRespuestas({ ...bien, 3: "a" }, TOTAL);
  assert.equal(minuscula, null);
  assert.equal(normalizarRespuestas([], TOTAL), null);
});

test("validarEntrega: acepta una entrega completa", () => {
  const revision = validarEntrega(entregaValida(), {
    grupos: 4,
    total: TOTAL,
    cuestionario: "rol_rojo_cuestionario",
  });
  assert.equal(revision.ok, true);
  assert.deepEqual(revision.problemas, []);
  assert.equal(revision.entrega.nombre, "Ana María Pérez");
  assert.equal(revision.entrega.cedula, "V-12345678");
  assert.equal(revision.entrega.grupo, 2);
  assert.equal(revision.entrega.cuestionario, "rol_rojo_cuestionario");
});

test("validarEntrega: acumula los problemas sin lanzar", () => {
  const revision = validarEntrega(
    entregaValida({ nombre: "A", cedula: "x", grupo: 9, respuestas: {} }),
    { grupos: 4, total: TOTAL, cuestionario: "rol_rojo_cuestionario" }
  );
  assert.equal(revision.ok, false);
  assert.equal(revision.entrega, null);
  assert.equal(revision.problemas.length, 4);
});

test("validarEntrega: rechaza otro cuestionario", () => {
  const revision = validarEntrega(
    entregaValida({ cuestionario: "otro" }),
    { grupos: 4, total: TOTAL, cuestionario: "rol_rojo_cuestionario" }
  );
  assert.equal(revision.ok, false);
  assert.deepEqual(revision.problemas, ["cuestionario desconocido"]);
});

test("validarEntrega: no muta la entrada", () => {
  const datos = entregaValida();
  const copia = JSON.parse(JSON.stringify(datos));
  validarEntrega(datos, {
    grupos: 4,
    total: TOTAL,
    cuestionario: "rol_rojo_cuestionario",
  });
  assert.deepEqual(datos, copia);
});

test("calificar: todo bien da 10", () => {
  const calculo = calificar(CLAVE, CLAVE);
  assert.deepEqual(calculo, { aciertos: 10, total: 10, nota: 10 });
});

test("calificar: 7 de 10 da 7", () => {
  const respuestas = { ...CLAVE, 3: "A", 7: "A", 9: "A" };
  const calculo = calificar(respuestas, CLAVE);
  assert.equal(calculo.aciertos, 7);
  assert.equal(calculo.nota, 7);
});

test("calificar: normaliza contra el total, no contra 10", () => {
  const clave = { 1: "A", 2: "B", 3: "C" };
  const calculo = calificar({ 1: "A", 2: "B", 3: "A" }, clave);
  assert.equal(calculo.total, 3);
  assert.equal(calculo.nota, 6.67);
});

test("calificar: nada bien da 0", () => {
  const respuestas = Object.fromEntries(
    Object.keys(CLAVE).map((numero) => [numero, "E"])
  );
  const calculo = calificar(respuestas, { ...CLAVE, 5: "A", 10: "A" });
  assert.equal(calculo.nota, 0);
});

test("calificar: una respuesta ausente cuenta como incorrecta", () => {
  const respuestas = { ...CLAVE };
  delete respuestas["1"];
  const calculo = calificar(respuestas, CLAVE);
  assert.equal(calculo.aciertos, 9);
  assert.equal(calculo.nota, 9);
});

test("ruta: determinista y por grupo y cédula", () => {
  const entrega = {
    cuestionario: "rol_rojo_cuestionario",
    cedula: "V-12345678",
    grupo: 2,
  };
  assert.equal(
    rutaResultado(entrega),
    "resultados/rol_rojo_cuestionario/grupo_02/V-12345678.json"
  );
});

test("contenido: JSON válido, con nota y sin la clave", () => {
  const entrega = {
    cuestionario: "rol_rojo_cuestionario",
    nombre: "Ana Pérez",
    cedula: "V-12345678",
    grupo: 2,
    respuestas: { 1: "A" },
  };
  const texto = contenidoResultado(
    entrega,
    { aciertos: 1, total: 1, nota: 10 },
    "2026-11-11T12:00:00.000Z"
  );
  const datos = JSON.parse(texto);
  assert.equal(datos.nota, 10);
  assert.equal(datos.cedula, "V-12345678");
  assert.equal(datos.enviado_en, "2026-11-11T12:00:00.000Z");
  assert.equal(texto.includes("CLAVE"), false);
  assert.equal(texto.endsWith("\n"), true);
});

test("clave: valida el formato del secreto", () => {
  assert.deepEqual(validarClave({ 1: "A", 2: "B" }), { 1: "A", 2: "B" });
  assert.equal(validarClave({}), null);
  assert.equal(validarClave({ 1: "F" }), null);
  assert.equal(validarClave({ uno: "A" }), null);
  assert.equal(validarClave({ 1: 1 }), null);
  assert.equal(validarClave(null), null);
  assert.equal(validarClave([1, 2]), null);
});

test("cuestionario: solo minúsculas, dígitos y guion bajo", () => {
  assert.equal(validarCuestionario("rol_rojo_cuestionario"), "rol_rojo_cuestionario");
  assert.equal(validarCuestionario("ROL"), null);
  assert.equal(validarCuestionario("../x"), null);
  assert.equal(validarCuestionario(""), null);
  assert.equal(validarCuestionario("ab"), null);
});

test("límite de cuerpo: 4 KiB es suficiente para una entrega", () => {
  const texto = JSON.stringify(entregaValida());
  assert.equal(texto.length < MAX_CUERPO, true);
});
