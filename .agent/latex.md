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

---

## 7. Caracteres UTF-8 Inválidos Dentro de `lstlisting` (Paquete `listings`)

### Síntoma / Mensaje de Error

Al compilar con `pdflatex` o `latexmk`, la compilación falla con múltiples errores repetidos en las líneas que contienen caracteres acentuados (á, é, í, ó, ú, ñ) dentro de un entorno `lstlisting`:

```text
LaTeX Error: Invalid UTF-8 byte sequence (�\expandafter).
...
l.178 // ================= DEFINICIÓN
                                       DE PINES =================

LaTeX Error: Invalid UTF-8 byte "93.
...
l.181 ...ENSADO = A1; // PB2 - Entrada Analógica
                                                  ADC (Sensado de voltaje)
```

### Causa

El paquete `listings` no soporta nativamente la codificación UTF-8 cuando se compila con `pdflatex`. Los caracteres multibyte del español (tildes, eñe, diéresis) dentro del contenido de un bloque `\begin{lstlisting}...\end{lstlisting}` no son interpretados correctamente por el motor de tipografía, que espera secuencias de un solo byte. Esto ocurre típicamente al incluir código fuente con comentarios en español.

### Solución

Agregar la opción `literate` en la definición del estilo de `listings` para mapear cada carácter UTF-8 problemático a su comando LaTeX equivalente:

```latex
\lstdefinestyle{mystyle}{
    % ... resto de opciones del estilo ...
    tabsize=2,
    literate=
      {á}{{\'a}}1 {é}{{\'e}}1 {í}{{\'i}}1 {ó}{{\'o}}1 {ú}{{\'u}}1
      {Á}{{\'A}}1 {É}{{\'E}}1 {Í}{{\'I}}1 {Ó}{{\'O}}1 {Ú}{{\'U}}1
      {ñ}{{\~n}}1 {Ñ}{{\~N}}1
}
```

Cada entrada `{<carácter>}{{<reemplazo LaTeX>}}<longitud>` le indica a `listings` que al encontrar ese byte UTF-8, lo sustituya por el comando LaTeX correspondiente. El número `1` al final indica que el carácter original ocupa 1 posición de ancho.

> **Nota:** Si el código fuente contiene otros caracteres especiales (ej. `ü`, `ö`), se deben agregar mapeos adicionales al bloque `literate` siguiendo el mismo patrón.

> **Archivo afectado:** `docs/PROTECTOR_120VAC/120VAC_mejorado.tex`

---

## 8. Signo `=` en Etiquetas de Circuitikz Rompe el Parser de Claves

### Síntoma / Mensaje de Error

Al compilar con `pdflatex` o `latexmk`, la compilación falla con una cascada de errores al procesar un componente de circuitikz cuya etiqueta contiene el carácter `=` dentro de modo matemático:

```text
! Extra }, or forgotten $.
\pgf@let@token ...trut \pgf@circ@finallabels {#1}}

l.83               to[nos, l=$t=0$] (2,2)

! Package tikz Error: Giving up on this path. Did you forget a semicolon?.
l.83               to[nos, l=$t=0$] (2,2)
```

Los errores subsiguientes incluyen `Undefined control sequence`, `Missing number`, `Missing } inserted` y `Extra }, or forgotten \endgroup`, que son consecuencia del primer error no resuelto.

### Causa

Circuitikz utiliza el sistema de claves de PGF (`pgfkeys`) para procesar las opciones de componentes como `l=<valor>`. Cuando el valor de la etiqueta contiene un signo `=` (por ejemplo, `l=$t=0$`), el parser interpreta el segundo `=` como un separador clave-valor adicional, rompiendo el análisis sintáctico de la expresión completa y generando una cascada de errores.

### Solución

Envolver el valor completo de la etiqueta entre llaves `{...}` para proteger su contenido del parser de claves:

```latex
% Antes (incorrecto — el '=' interno confunde al parser):
\draw (0,0) to[nos, l=$t=0$] (2,2);

% Después (correcto — las llaves protegen el contenido):
\draw (0,0) to[nos, l={$t=0$}] (2,2);
```

> **Nota:** Esta misma protección con llaves aplica a **cualquier** opción de circuitikz o TikZ cuyo valor contenga caracteres especiales para `pgfkeys`, como `=` o `,`. Ejemplos comunes: `l={$v_{out} = 5\,\text{V}$}`, `v={$v_R = iR$}`.

> **Archivo afectado:** `cursos/INT_ELECTRONICA/ejercicios/03/problemario_sems_4_5.tex`

---

## 9. Formato de Número Inválido en `\SI{}` del Paquete `siunitx`

### Síntoma / Mensaje de Error

Al compilar con `pdflatex` o `latexmk`, la compilación falla con el siguiente error y termina abruptamente:

```text
! Package siunitx Error: Invalid number '10^3'.

For immediate help type H <return>.

l.92 \[ \tau = R \cdot C = (\SI{10^3}{\ohm}
                                           ) \cdot ...

! Emergency stop.
!  ==> Fatal error occurred, no output PDF file produced!
```

### Causa

El paquete `siunitx` tiene su propio parser numérico que **no** reconoce la notación de potencia con `^` de LaTeX (por ejemplo, `10^3`). El parser espera números en formato estándar o en notación científica con `e` (por ejemplo, `1e3`). Al encontrar el carácter `^`, el parser no puede interpretar el número, emite un error y aborta la compilación con un `Emergency stop` porque la lectura del argumento queda incompleta (runaway argument).

### Solución

Usar la notación con `e` que `siunitx` sí reconoce, o escribir el número directamente:

```latex
% Antes (incorrecto — siunitx no acepta '^'):
\SI{10^3}{\ohm}

% Después (correcto — notación científica con 'e'):
\SI{1e3}{\ohm}

% Alternativa (correcto — valor numérico directo):
\SI{1000}{\ohm}
```

> **Nota:** La notación `e` de `siunitx` es equivalente a $\times 10^n$. Por ejemplo, `\SI{4.7e-6}{\farad}` produce "4.7 × 10⁻⁶ F". Si se necesita mostrar explícitamente la potencia de 10 como parte de una expresión matemática, se debe usar modo math puro fuera de `\SI`: `$10^3\,\si{\ohm}$`.

> **Archivo afectado:** `cursos/INT_ELECTRONICA/ejercicios/03/problemario_sems_4_5.tex`

---

## 10. Uso de `\\` Dentro de `\multicolumn` en un Entorno `tabular`

### Síntoma / Mensaje de Error

Al compilar con `pdflatex` o `latexmk`, la compilación falla con una cascada de errores que comienza con:

```text
! Missing \endgroup inserted.
l.78 ...{imagen\_1.jpeg}\\\texttt{imagen\_2.jpeg}}
! Missing } inserted.
l.79 \end
! Missing \cr inserted.
l.79 \end
! Misplaced \cr.
l.79 \end
```

Latexmk puede además cachear el error y reportar en ejecuciones posteriores:

```text
Collected error summary (may duplicate other messages):
  pdflatex: gave an error in previous invocation of latexmk.
```

### Causa

En un entorno `tabular`, el comando `\\` tiene un significado especial: indica el fin de una fila de la tabla. Cuando se utiliza `\\` dentro de un `\multicolumn{...}{...}{...}` para intentar insertar un salto de línea dentro de una celda, LaTeX lo interpreta como un terminador de fila, rompiendo la estructura de la tabla y generando errores en cascada de `Missing \endgroup`, `Missing }` y `Misplaced \cr`.

En este caso, el script generador `execution/generar_informe_imagen.py` unía los nombres de archivos con `\\\\` (que produce `\\` en el LaTeX generado) dentro de un `\multicolumn`:

```python
# Código Python que generaba el error:
archivos_items = "\\\\".join(
    f"\\texttt{{{tex(Path(a).name)}}}" for a in archivos
)
# Producía: \texttt{imagen\_1.jpeg}\\\texttt{imagen\_2.jpeg}
# Dentro de: \multicolumn{3}{l}{...}
```

### Solución

#### Opción A: Separar con comas (Aplicada)

Unir los nombres de archivo con comas en lugar de `\\`:

```python
# Correcto:
archivos_items = ", ".join(
    f"\\texttt{{{tex(Path(a).name)}}}" for a in archivos
)
```

Produce:

```latex
\textbf{Archivos:} & \multicolumn{3}{l}{\texttt{imagen\_1.jpeg}, \texttt{imagen\_2.jpeg}} \\
```

#### Opción B: Usar `\newline` en lugar de `\\`

Si se necesita un archivo por línea dentro de la celda, usar `\newline` que funciona dentro de `\multicolumn`:

```latex
% Correcto con \newline:
\textbf{Archivos:} & \multicolumn{3}{l}{\texttt{imagen\_1.jpeg}\newline\texttt{imagen\_2.jpeg}} \\
```

#### Opción C: Usar una `tabularx` con `p{}`/`m{}` o un `\parbox`

Para listas más largas, envolver en un `\parbox` o usar columnas de ancho fijo:

```latex
\textbf{Archivos:} & \multicolumn{3}{l}{\parbox[t]{10cm}{%
  \texttt{imagen\_1.jpeg}\\
  \texttt{imagen\_2.jpeg}%
}} \\
```

> **Regla general:** Nunca usar `\\` directamente dentro de `\multicolumn` en un `tabular`. Usar `, `, `\newline`, o envolver en `\parbox`.

> **Archivo afectado:** `execution/generar_informe_imagen.py` (generador automático de informes LaTeX)

---

## 11. Líneas que Sobresalen del Margen Derecho por Rutas Windows Largas (`\textbackslash\{\}`)

### Síntoma / Mensaje de Error

Al compilar con `pdflatex` o `latexmk`, el log reporta múltiples advertencias de `Overfull \hbox`:

```text
Overfull \hbox (63.15594pt too wide) in paragraph at lines 96--97
Overfull \hbox (11.99368pt too wide) in paragraph at lines 111--118
Overfull \hbox (127.7444pt too wide) in paragraph at lines 119--127
```

En el PDF resultante, las líneas afectadas sobresalen visiblemente por el margen derecho de la página.

### Causa

Las rutas de archivos Windows se escaparon usando secuencias `\textbackslash\{\}` para representar cada barra invertida. Por ejemplo:

```latex
C:\textbackslash\{\}Users\textbackslash\{\}E550\textbackslash\{\}Desktop\textbackslash\{\}CYBERSEGURIDAD\textbackslash\{\}venv\textbackslash\{\}Lib\textbackslash\{\}site-packages\textbackslash\{\}impacket\textbackslash\{\}spnego.py
```

Esta secuencia produce una cadena monolítica sin puntos de ruptura de línea. LaTeX no puede insertar saltos en ninguna posición dentro de la cadena, por lo que la línea completa se extiende más allá del margen cuando la ruta es suficientemente larga.

El problema se origina en la función `tex()` del script generador `execution/generar_informe_imagen.py`, que escapa la barra invertida `\` a `\textbackslash{}` y las llaves `{` `}` a `\{` `\}`, produciendo la combinación `\textbackslash\{\}` que es correcta semánticamente pero no permite ruptura.

### Solución

#### Opción A: Usar `\path{}` del paquete `url` (Aplicada)

El paquete `url` (incluido con `\usepackage{url}`) proporciona el comando `\path{}` que renderiza rutas de archivo en fuente monoespaciada y permite saltos de línea automáticos en los separadores (`\`, `/`, `.`):

```latex
% En el preámbulo:
\usepackage{url}

% En el cuerpo:
\path{C:\Users\E550\Desktop\CYBERSEGURIDAD\venv\Lib\site-packages\impacket\spnego.py}
```

> **Nota:** Dentro de `\path{}` no se necesita escapar las barras invertidas ni los guiones bajos — el comando los maneja literalmente, similar a `\verb`.

#### Opción B: Agregar `\sloppy` y `\emergencystretch` como medida general

Para dar más flexibilidad al algoritmo de ruptura de líneas en todo el documento:

```latex
% En el preámbulo:
\sloppy
\emergencystretch 3em
```

Esto permite que LaTeX acepte espacios inter-palabra más amplios antes de reportar un overfull, reduciendo los desbordes en párrafos con palabras largas o monoespaciadas. No es una solución específica para rutas, pero ayuda como complemento.

#### Opción C: Envolver en `\seqsplit{}` del paquete `seqsplit`

Para cadenas extremadamente largas sin espacios (como hashes o URLs):

```latex
\usepackage{seqsplit}
\texttt{\seqsplit{C:\textbackslash{}Users\textbackslash{}E550\textbackslash{}...}}
```

> **Regla general para rutas de archivo:** Usar siempre `\path{}` (del paquete `url`) para rutas Windows/Unix en lugar de escaparlas manualmente con `\textbackslash\{\}`. El comando `\path{}` es más legible en el fuente LaTeX y produce saltos de línea automáticos en el PDF.

> **Archivos afectados:**
> - `docs/IMAGENES/informe_imagen/informe_analisis_imagen_1_imagen_2.tex`
> - `execution/generar_informe_imagen.py` (origen del problema — función `tex()`)

---

## 12. `Bad math environment delimiter` por Escapes en f-strings de Python (`\[`)

### Síntoma / Mensaje de Error

Al compilar un documento LaTeX autogenerado por un script Python, la compilación falla repentinamente en líneas de texto o encabezados donde se esperaba un salto de línea con espaciado personalizado (ej. `\\[4pt]`). El error mostrado es:

```text
! LaTeX Error: Bad math environment delimiter.
l.68 ...large Examen de Razonamiento y Cálculo}\[
                                                  8pt]
```

Posteriormente pueden aparecer errores como `Command \end{equation*} invalid in math mode.` debido a que LaTeX cree que se inició un bloque matemático y nunca se cerró.

### Causa

El generador Python usa *f-strings* regulares (`f"..."`) en lugar de *raw f-strings* (`fr"..."`). 
Cuando se desea insertar un salto de línea LaTeX con tamaño (ej. `\\[4pt]`), en un f-string normal de Python las barras invertidas dobles `\\` se escapan y se evalúan como una sola barra `\`. 

Por lo tanto, la secuencia Python `\\[4pt]` se imprime en el archivo `.tex` generado como `\[4pt]`. 
En LaTeX, el comando `\[` es un delimitador de apertura para el entorno de ecuaciones matemáticas sin numeración (`displaymath`). LaTeX interpreta el `\[` como inicio de matemáticas y el `4pt]` como contenido literal de la ecuación, rompiendo la estructura de la página y el compilador.

### Solución

Al utilizar *f-strings* convencionales para generar código LaTeX, se deben agregar **cuatro** barras invertidas consecutivas para producir dos barras reales en el texto de salida.

```python
# Antes (incorrecto, genera `\[4pt]`):
head = f"""
\begin{{center}}
  {{\Large\bfseries\color{{azulTitulo}} ELECTRÓNICA}}\\[4pt]
\end{{center}}
"""

# Después (correcto, genera `\\[4pt]`):
head = f"""
\begin{{center}}
  {{\Large\bfseries\color{{azulTitulo}} ELECTRÓNICA}}\\\\[4pt]
\end{{center}}
"""
```

**Nota:** Si en su lugar usas cadenas raw (`r"..."` o `fr"..."`), no necesitas la doble escapada. `\\[4pt]` en una raw string producirá correctamente `\\[4pt]` en el archivo. Sin embargo, en plantillas grandes con múltiples comandos LaTeX (como `\begin`, `\fancyhead`, etc.), cambiar una cadena normal a raw de golpe puede romper todos los demás comandos donde solo pusiste `\\comando` creyendo que se requería escape.

> **Archivos afectados:**
> - `execution/generar_examen_latex.py` (Líneas donde se define el encabezado y pie de examen/solucionario).

---

## 13. Símbolos Matemáticos Incompatibles en Modo Texto (`\text{...}`)

### Síntoma / Mensaje de Error

Al compilar un documento que contiene notación matemática generada por un LLM, la compilación falla con cientos de errores en cascada indicando la falta de delimitadores matemáticos o llaves de cierre:

```text
! Missing } inserted.
<inserted text>
                }
l.182   \rule{0.6\linewidth}{0.4pt} \\[6pt]

! Missing $ inserted.
<inserted text>
                $
```

Estos errores a menudo apuntan erróneamente al final de un bloque, entorno o ecuación (ej. `\rule...`) en lugar de apuntar a la verdadera línea defectuosa donde inició el desajuste de entornos.

### Causa

El problema ocurre porque el código generado insertó macros que son estrictamente matemáticas (como `\Omega` o `\mu`) dentro del comando `\text{...}`, el cual obliga a LaTeX a procesar su contenido en modo texto. 

```latex
% Incorrecto (Provoca fallos en cascada "Missing $ inserted"):
La resistencia equivalente es $4.7\text{ k\Omega}$
El capacitor de entrada es $1\text{ \mu F}$
```

Cuando LaTeX encuentra `\Omega` en modo texto, intenta forzar la entrada a modo matemático automáticamente, insertando un símbolo `$` que desbalancea el entorno actual, desencadenando múltiples advertencias y deteniendo eventualmente la compilación.

### Solución

Los comandos matemáticos **deben** estar rodeados por el entorno matemático (`$`...`$`). Al utilizar `\text{...}` (proporcionado por `amsmath`), asegúrate de que el texto puro quede dentro y el comando matemático regrese al bloque matemático.

```latex
% Correcto (Cerrando \text{} antes del símbolo matemático):
La resistencia equivalente es $4.7\text{ k}\Omega$
El capacitor de entrada es $1\text{ }\mu\text{F}$
% o mejor aún:
El capacitor de entrada es $1\,\mu\text{F}$
```

**Estrategia automatizada:** En flujos donde el LLM pueda generar frecuentemente errores de sintaxis como `\text{ k\Omega}`, es recomendable aplicar una limpieza (sanitización) mediante expresiones regulares antes de mandar el archivo a compilar con `pdflatex`.

> **Archivos afectados (Históricamente):**
> - Archivos `.tex` generados automáticamente por el modelo `gemini-2.5-flash` y otros LLMs propensos a cometer descuidos con el anidamiento de `\text{}`.

---

## 14. Clave Desconocida en `tcolorbox` (`/tcb/fill`)

### Síntoma / Mensaje de Error

Al compilar un documento que utiliza el paquete `tcolorbox`, la compilación falla con el siguiente error:

```text
! Package pgfkeys Error: I do not know the key '/tcb/fill', to which you passed
 'primary', and I am going to ignore it. Perhaps you misspelled it.
```

### Causa

Se intentó utilizar la clave `fill` dentro de las opciones de un `tcolorbox` o en uno de sus estilos internos (como `boxed title style`). Aunque `fill` es válido en TikZ, las cajas principales y títulos de `tcolorbox` utilizan su propio motor de claves de color de fondo, el cual se define con `colback`.

### Solución

Reemplazar la clave `fill` por `colback` dentro de las opciones de `tcolorbox`.

```latex
% Antes (incorrecto - fill no es una clave de tcolorbox):
boxed title style={
    fill=primary,
    rounded corners,
    arc=2mm
}

% Después (correcto - usando colback):
boxed title style={
    colback=primary,
    rounded corners,
    arc=2mm
}
```

> **Nota:** La clave `fill` sí es válida cuando se usa en estilos puramente de TikZ dentro de `tcolorbox`, como por ejemplo en `interior style={fill=white}`.
