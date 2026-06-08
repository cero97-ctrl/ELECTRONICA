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

---

## 3. Nodo `full diode bridge` Inexistente en Circuitikz

### Síntoma / Mensaje de Error

Al compilar con `pdflatex`, la compilación genera los siguientes errores encadenados:

```text
Package pgfkeys Error: I do not know the key '/tikz/full diode bridge'
  and I am going to ignore it. Perhaps you misspelled it.

Package PGF Math Error: Unknown function `left' (in 'left').
Package PGF Math Error: Unknown function `right' (in 'right').
Package PGF Math Error: Unknown function `top' (in 'top').
Package PGF Math Error: Unknown function `bottom' (in 'bottom').
```

### Causa

La clave `full diode bridge` no existe como tipo de nodo en circuitikz 1.6.6 (TeX Live 2023). Al no reconocer el nodo, los anchors asociados (`br.left`, `br.right`, `br.top`, `br.bottom`) tampoco se resuelven, generando los errores en cascada de `Unknown function`.

### Solución

Reemplazar el nodo inexistente por un puente rectificador dibujado manualmente con 4 diodos individuales usando coordenadas explícitas:

```latex
% Antes (incorrecto):
\node[full diode bridge, scale=1.2] (br) at (14.5,2) {};
\draw (13,4) -| (br.left);
\draw (13,0) -| (br.right);
\draw (br.top) |- (18.5,4);
\draw (br.bottom) |- (18.5,0);

% Después (correcto):
\coordinate (br-left) at (13.5,2);
\coordinate (br-right) at (15.5,2);
\coordinate (br-top) at (14.5,3.5);
\coordinate (br-bottom) at (14.5,0.5);

\draw (br-left) to[D, *-*] (br-top);
\draw (br-top) to[D, *-*] (br-right);
\draw (br-left) to[D, *-*, invert] (br-bottom);
\draw (br-bottom) to[D, *-*, invert] (br-right);

\draw (13,4) |- (br-left);
\draw (13,0) |- (br-right);
\draw (br-top) |- (18.5,4);
\draw (br-bottom) |- (18.5,0);
```

> **Archivos afectados:**
> - `docs/SMPS/SMPS_FUENTE_CONMUTADA_CIRCUITO_DE_ENTRADA.tex`
> - `docs/SMPS/SMPS_ESQUEMA_CIRCUITO_ENTRADA.tex`

---

## 4. Condensador Polar `pC` Deprecado en Circuitikz

### Síntoma / Mensaje de Error

```text
Package circuitikz Warning: polar capacitor has been deprecated;
  change to curved capacitor (see manual).
```

### Causa

El componente `pC` (polar capacitor) fue deprecado a partir de circuitikz ≥ 1.6. Aunque puede generar un PDF, el warning indica que podría eliminarse en versiones futuras.

### Solución

Reemplazar `pC` por `eC` (condensador electrolítico) o `cC` (curved capacitor):

```latex
% Antes (deprecado):
\draw (18.5,4) to[pC, l=$C_{bulk}$, *-*] (18.5,0);

% Después (correcto):
\draw (18.5,4) to[eC, l=$C_{bulk}$, *-*] (18.5,0);
```

> **Archivo afectado:** `docs/SMPS/SMPS_FUENTE_CONMUTADA_CIRCUITO_DE_ENTRADA.tex`

---

## 5. Referencia Adelantada a un Nodo/Coordenada TikZ No Definido Aún (Forward Reference)

### Síntoma / Mensaje de Error

Al compilar con `pdflatex`, la compilación falla con el siguiente error:

```text
Package pgf Error: No shape named `v_out_pos' is known.

See the pgf package documentation for explanation.
Type  H <return>  for immediate help.

l.453     }
```

### Causa

Dentro de un entorno `circuitikz` (o `tikzpicture`), TikZ procesa las instrucciones de dibujo de forma **secuencial**. Si se referencia un nodo o coordenada (por ejemplo, `(v_out_pos)`) en una instrucción `\draw` **antes** de que dicho nodo haya sido definido (mediante `coordinate (v_out_pos)` o `node (v_out_pos)` en una línea posterior), TikZ no puede resolver el nombre y lanza el error `No shape named '...' is known`.

En este caso concreto, la coordenada `v_out_pos` se definía en la línea 430:
```latex
\draw ... (20.5, 5.5) coordinate (v_out_pos);
```
pero se referenciaba **antes**, en la línea 319:
```latex
\draw (11.0, -7.1) -- (11.0, -5.0) -- (21.5, -5.0) |- (v_out_pos) node[circ] {};
```

### Solución

#### Opción A: Reemplazar la referencia por las coordenadas literales (Aplicada)
Sustituir el nombre del nodo por sus coordenadas numéricas explícitas:

```latex
% Antes (incorrecto — referencia adelantada):
\draw (11.0, -7.1) -- (11.0, -5.0) -- (21.5, -5.0) |- (v_out_pos) node[circ] {};

% Después (correcto):
\draw (11.0, -7.1) -- (11.0, -5.0) -- (21.5, -5.0) |- (20.5, 5.5) node[circ] {};
```

#### Opción B: Definir la coordenada al inicio del entorno
Mover la definición de la coordenada al principio del bloque `circuitikz`, antes de cualquier referencia:

```latex
\begin{circuitikz}[...]
    % Definir coordenadas reutilizables al inicio
    \coordinate (v_out_pos) at (20.5, 5.5);

    % ... resto del dibujo ...
    \draw (11.0, -7.1) -- ... |- (v_out_pos) node[circ] {};
\end{circuitikz}
```

> **Archivo afectado:** `docs/SMPS/SMPS_FUENTE_CONMUTADA.tex`

---

## 6. Estilo TikZ Personalizado No Definido (`tp`)

### Síntoma / Mensaje de Error

Al compilar con `pdflatex` o `latexmk`, la compilación genera múltiples errores repetidos:

```text
! Package pgfkeys Error: I do not know the key '/tikz/tp' and I am going to
  ignore it. Perhaps you misspelled it.

See the pgfkeys package documentation for explanation.
Type  H <return>  for immediate help.
 ...

l.279     }
```

Latexmk puede además cachear el error y reportar en ejecuciones posteriores:

```text
Collected error summary (may duplicate other messages):
  pdflatex: gave an error in previous invocation of latexmk.
```

### Causa

Se utilizan nodos con un estilo personalizado (`tp`) para marcar puntos de prueba en un diagrama `circuitikz`, pero dicho estilo nunca fue definido con `\tikzset`. TikZ no reconoce la clave y lanza el error para cada nodo que la usa:

```latex
% Uso sin definición previa (incorrecto):
\node[tp, label={...}] at (8,6) {};  % TP1
\node[tp, label={...}] at (mosfet.S) {};  % TP2
% ... etc.
```

### Solución

Definir el estilo `tp` con `\tikzset` **antes** de utilizarlo, ya sea en el preámbulo del documento o al inicio del entorno `circuitikz`/`tikzpicture`:

```latex
% Dentro del entorno circuitikz, antes de los nodos que usen 'tp':
\tikzset{tp/.style={circle, fill=red, inner sep=1.5pt}}

% Ahora los nodos funcionan correctamente:
\node[tp, label={[label distance=-2pt]270:TP1}] at (8,6) {};
\node[tp, label={[label distance=-2pt]90:TP2}] at (mosfet.S) {};
```

> **Nota:** El estilo es personalizable. Se pueden ajustar `fill` (color), `inner sep` (tamaño) y `draw` (borde) según las necesidades del diagrama.

> **Archivo afectado:** `docs/SMPS/SMPS.tex`
