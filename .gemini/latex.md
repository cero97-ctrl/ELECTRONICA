# Registro de Errores de Compilación en LaTeX

Este archivo documenta errores de compilación comunes encontrados en el desarrollo de documentos de LaTeX en este espacio de trabajo, junto con sus respectivas soluciones para evitar regresiones.

---

## 1. Conflicto de Comillas Dobles con `spanish` de `babel` en `\texttt`

### Síntoma / Mensaje de Error
Al compilar el documento (por ejemplo, con `pdflatex` o `latexmk`), la compilación falla con el siguiente error al procesar texto que contiene comillas dobles (`"`) dentro de un bloque monoespaciado (`\texttt{...}`):

```text
! Bad character code (-1).
\es@chf ->\char \hyphenchar \font 
                                  
l.207 ...{<meta http-equiv="refresh" content="1">}
```

### Causa
El paquete `babel` cargado con la opción `spanish` (`\usepackage[spanish]{babel}`) activa de manera predeterminada atajos tipográficos (shorthands), haciendo que el carácter de comillas dobles (`"`) sea un carácter activo. Cuando se utiliza dentro de comandos de cambio de fuente como `\texttt` (especialmente si va seguido de ciertas letras como la `r` de `refresh`), la macro interna de Babel `\es@chf` no logra resolver el código de carácter adecuado de la tipografía y arroja un error de código de carácter inválido.

### Solución

#### Opción A: Desactivar los shorthands globalmente (Recomendada)
Si el documento está codificado en UTF-8 y se escriben caracteres con acento o la eñe (`ñ`, `á`, `ó`, etc.) directamente desde el teclado, no se necesitan los atajos tradicionales de Babel. Se pueden desactivar de manera segura agregando la opción `es-noshorthands` al paquete:

```latex
\usepackage[spanish,es-noshorthands]{babel}
```

#### Opción B: Desactivar y activar localmente
Si por algún motivo se requieren los shorthands en el resto del documento, se pueden desactivar únicamente alrededor de la instrucción conflictiva:

```latex
\shorthandoff{"}
\texttt{<meta http-equiv="refresh" content="1">}
\shorthandon{"}
```

---

## 2. Comando `\text{}` Indefinido por Falta del Paquete `amsmath`

### Síntoma / Mensaje de Error

Al compilar con `pdflatex` o `latexmk`, la compilación falla con el siguiente error en las líneas donde se usa `\text{...}` dentro de un entorno matemático:

```text
! Undefined control sequence.
l.16 ...fluye por $R_2$ y $R_3$ será de $0\,\text
                                                  {A}$.
```

### Causa

El comando `\text{...}` es provisto por el paquete `amsmath`. Si este paquete no está incluido en el preámbulo del documento, LaTeX no reconoce `\text` y lanza un error de secuencia de control indefinida.

### Solución

Agregar `\usepackage{amsmath}` en el preámbulo del documento:

```latex
\usepackage{amsmath}
```

**Ejemplo de uso correcto** (para escribir texto o unidades dentro de modo matemático):

```latex
$0\,\text{A}$
$i_x = 0\,\text{A}$
```

> **Nota:** Alternativamente, el paquete `siunitx` ofrece el comando `\SI{0}{A}` para unidades físicas, que maneja automáticamente el espaciado y el formato.
