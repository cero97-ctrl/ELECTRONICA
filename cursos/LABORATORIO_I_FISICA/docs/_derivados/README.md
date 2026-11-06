# Derivados de `docs/`

Pares `.tex`/`.pdf` que ya no forman parte del curso: su contenido fue
absorbido por `curso.yaml` y por los documentos generados. Se conservan por si
hace falta recompilarlos o rescatar un detalle; nada del flujo los referencia.

- `Teoria_de_Error_v3.0.tex` / `.pdf`: versión LaTeX de
  `../Teoria_de_Error_v3.0.md`. La teoría del curso vive hoy en los fundamentos
  de las diez semanas y en `guia_estudiante.pdf`.
- `Pendulo_Simple_Analisis.tex` / `.pdf`: transcripción de los 21 pares
  `L_H, t, T, T^2` tomados de `../Péndulo Simple (v3.0).pdf` y de los jpeg de
  datos. Esos pares están hoy en la tabla de la semana 9 de `curso.yaml` y su
  análisis en `practica_09.pdf`.

Para recompilar uno, desde la raíz del repositorio:

```bash
cd cursos/LABORATORIO_I_FISICA/docs/_derivados && pdflatex -interaction=nonstopmode Teoria_de_Error_v3.0.tex
```

Son documentos autónomos (preambulo propio), no usan el estilo del curso.
