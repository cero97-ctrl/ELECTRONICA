# cuestionarios-worker

Recibe la entrega de un cuestionario desde la página pública, la **califica en el
servidor** y archiva el resultado en el repositorio privado
`cero97-ctrl/cuestionarios-resultados`.

La clave de respuestas vive en el secreto `CLAVE_JSON` y **nunca** se envía al
navegador. El alumno solo recibe su nota, el número de aciertos y el total.

## Contrato

`POST /` con `Content-Type: application/json`:

```json
{
  "cuestionario": "rol_rojo_cuestionario",
  "nombre": "Ana María Pérez",
  "cedula": "V-12345678",
  "grupo": 2,
  "respuestas": { "1": "A", "2": "B" }
}
```

Respuesta `200`:

```json
{ "nota": 8.0, "aciertos": 8, "total": 10 }
```

Errores: `400` entrega inválida · `403` origen no permitido · `405` método ·
`413` cuerpo mayor de 4 KiB · `500` configuración incompleta · `502` no se pudo
archivar. `GET /salud` responde `{"ok":true}` y no toca la clave.

El archivo se escribe en
`resultados/<cuestionario>/grupo_<NN>/<cedula>.json` (misma cédula → mismo
archivo, así que un reenvío es idempotente).

## Configuración

Variables (`wrangler.jsonc`): `REPO_RESULTADOS`, `CUESTIONARIO_ID`, `GRUPOS`,
`ORIGENES` (lista separada por comas; sin ella el navegador no puede enviar).

Secretos:

| Secreto | Contenido |
|---|---|
| `CLAVE_JSON` | `{"1":"A","2":"B",...}`, generado desde `*_respuestas.md` |
| `GITHUB_TOKEN` | PAT fine-grained con `Contents: Read and write` **solo** en `cuestionarios-resultados` |

```bash
wrangler secret put CLAVE_JSON < .tmp/clave_rol_rojo.json
wrangler secret put GITHUB_TOKEN   # pegado en el prompt, nunca en un argumento
wrangler secret list
```

## Desarrollo

```bash
npm test                       # lógica pura, sin red ni cuenta
wrangler deploy --dry-run      # valida el bundle sin desplegar
wrangler dev                   # local en http://localhost:8787
```

`.dev.vars` (ignorado por git) con `CLAVE_JSON=...` y `GITHUB_TOKEN=...` para
probar el flujo completo en local; `ORIGENES` debe incluir el origen de la página
de prueba.

## Riesgos conocidos

- El endpoint es público: cualquiera puede enviar. La mitigación es validación
  estricta, cuerpo acotado y reescritura idempotente por cédula; el repositorio
  privado permite auditar y limpiar. No hay rate limiting (requiere KV o la
  función de pago).
- La nota se devuelve al alumno, pero no qué preguntas falló: eso evita que un
  reenvío sirva para aprender la clave.
