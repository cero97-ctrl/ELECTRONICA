# Registro de Errores y Soluciones en compilación de LaTeX

Este documento sirve como base de conocimientos y directrices estrictas para la generación de código fuente LaTeX por parte del asistente de IA. **El asistente debe consultar y aplicar estas reglas siempre que se le solicite generar o modificar un archivo `.tex`.**

---

## 1. Problema de codificación UTF-8 con caracteres en español dentro del paquete `listings`

### Descripción del Error
Al utilizar el motor de compilación tradicional `pdflatex`, el paquete `listings` (`lstlisting`) falla y arroja el error `Invalid UTF-8 byte sequence` cuando encuentra caracteres especiales del español (como vocales acentuadas, eñes o signos de interrogación/exclamación de apertura) dentro de los bloques de código o comentarios. `pdflatex` no maneja estos caracteres nativamente dentro de entornos de código formateado sin ayuda explícita.

### Solución Estricta a Implementar
Siempre que se genere un documento LaTeX que incluya el paquete `listings` y se espere contenido en español, se **DEBE** incluir el parámetro `extendedchars=true` y un mapeo exhaustivo mediante `literate` dentro de la configuración de `\lstset`.

**Bloque de código obligatorio a incluir en el preámbulo:**

```latex
\usepackage{listings}

% Configuración obligatoria para soportar UTF-8 en español dentro del código
\lstset{
    extendedchars=true,
    literate={á}{{\'a}}1 {é}{{\'e}}1 {í}{{\'i}}1 {ó}{{\'o}}1 {ú}{{\'u}}1 {Á}{{\'A}}1 {É}{{\'E}}1 {Í}{{\'I}}1 {Ó}{{\'O}}1 {Ú}{{\'U}}1 {ñ}{{\~n}}1 {Ñ}{{\~N}}1 {¿}{{?`}}1 {¡}{{!`}}1
}
```

---

## 2. Incompatibilidades con entornos del paquete `framed`

### Descripción del Error
El uso de entornos como `leftbar` del paquete `framed` para crear entornos personalizados (ej. `\newenvironment{pregunta}`) puede causar fallos de compilación silenciosos o conflictos de formato dependiendo de la versión de la distribución LaTeX o el uso de otros paquetes visuales.

### Solución Estricta a Implementar
Evitar en lo posible definir entornos personalizados complejos usando `framed` a menos que sea estrictamente necesario. Si se requiere resaltar texto, preferir el uso de paquetes más modernos y robustos como `mdframed` o `tcolorbox`, o simplemente usar entornos estándar como `quote` si el impacto visual requerido es menor.

---
*(Añadir futuros errores y soluciones debajo de esta línea)*