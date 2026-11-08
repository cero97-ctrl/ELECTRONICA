# Infografías del curso — Ciberseguridad Aplicada

Carpeta **local**: contiene infografías en PNG para los estudiantes (varios MB cada
una). No las genera ningún script y no se necesitan para clonar ni compilar el curso,
así que `.gitignore` excluye todo `cursos/*/docs/INFOGRAFIAS/**` salvo este README
(misma pauta que `docs/REFERENCIA/` y `evaluaciones/resultados/`). MEGA sincroniza la
carpeta, de modo que las copias de seguridad no dependen de git.

## Estructura

```
INFOGRAFIAS/
|-- README.md          # esta convención (sí se versiona)
|-- SEM_1/             # una carpeta por semana: SEM_NN
|   |-- *.png          # una infografía por rol o por flujo
```

Nombres de archivo: `<tema> rol <rol>.png` o `<flujo> ciberseguridad.png`, en español
y sin sufijos redundantes. Las de la semana 1 cubren los cuatro papeles del trabajo
en grupo (rojo, azul, púrpura y legal y reporte).

## Reglas

- **Nunca** añadir PNG/JPG/PDF de esta carpeta con `git add -f`: el repositorio es
  público y cada imagen pesa varios MB.
- Si una infografía se corrige, se reemplaza el archivo en local; no hay historial de
  versiones en git, así que conserva la versión anterior si quieres poder volver.
- Para compartirlas con los estudiantes, se suben al aula virtual o se enlazan desde
  el repositorio sin versionarlas.
