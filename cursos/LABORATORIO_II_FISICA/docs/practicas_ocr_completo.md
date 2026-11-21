# OCR de practicas.pdf


<!-- pagina 1 -->

## Página 1

UNIVERSIDAD DE ORIENTE
NÚCLEO DE SUCRE
ESCUELA DE CIENCIAS
DEPARTAMENTO DE FÍSICA

[ILEGIBLE]
PROF. CÉSAR RODRÍGUEZ
C.I.: 3.701.716

LABORATORIO II DE FÍSICA

CUMANÁ, ABRIL 2011

<!-- pagina 2 -->

## Página 2

CONTENIDO

Prefacio.................................................................................................................... 1
Práctica 1 Manejo del instrumental eléctrico y determinación de la característica I -V
de a algunos dispositivos................................................................................ 4
Práctica 2 Determinación de una resistencia eléctrica................................................ 11
Práctica 3 Determinación de la resistencia interna de un voltímetro, un amperímetro
y una fuente.................................................................................................. 16
Práctica 4 Circuitos eléctricos.................................................................................... 21
Práctica 5 Elementos no lineales. Diodo Semiconductor............................................ 27
Práctica 6 Respuesta de los elementos básicos R, L y C a la tensión senoidal........... 34
Práctica 7 Circuitos Resonantes................................................................................ 41
Práctica 8 Carga y descarga de un capacitor............................................................. 46
Tablas con valores de capacitancias e inductancias................................................ 54
Datos técnicos de los instrumentos......................................................................... 56
Bibliografía.............................................................................................................. 58

3

<!-- pagina 3 -->

## Página 3

PRÁCTICA 1
MANEJO DEL INSTRUMENTAL ELÉCTRICO Y DETERMINACIÓN DE
LA CARACTERÍSTICA CORRIENTE-VOLTAJE (I-V) DE ALGUNOS
DISPOSITIVOS.
1. OBJETIVOS.
* Lograr que el estudiante aprenda a utilizar los instrumentos eléctricos de medida y
a realizar montaje de circuitos sencillos.
* Obtener la característica i-v de algunos dispositivos y determinar si cumplen o no
la ley de Ohm.

2. PARTE TEÓRICA.
Esta teoría es común para las prácticas "Determinación de una resistencia eléctrica"
y "Determinación de la resistencia interna de un Voltímetro, un Amperímetro y una
Fuente".

2.1. RESISTENCIA, RESISTIVIDAD Y CONDUCTIVIDAD.
La resistencia eléctrica es la propiedad de un material que caracteriza su
oposición al paso de una corriente eléctrica. En términos de la diferencia de
potencial V, aplicada a sus extremos y de la intensidad de corriente I, que
circula a través del conductor, la resistencia R, la definimos así:
\[R = \frac{V}{I}\]
(1)
La unidad en el S.I. de resistencia es el ohm, que se representa por la letra
griega $\Omega$. Según [1], $1\Omega = \frac{1V}{1A}$.

Una cantidad relacionada con R es la resistividad $\rho$, o resistencia específica, la
cual es la característica de un material y no de una muestra específica del
mismo. Para materiales isótropos, la resistividad se define como:
\[\rho = \frac{E}{J}\]
(2)
donde E es el campo eléctrico y J es la densidad de corriente o corriente por
unidad de área de la sección transversal del conductor es decir:

4

<!-- pagina 4 -->

## Página 4

\[J = \frac{I}{A}\]
(3)
Con el fin de expresar la resistencia R, en términos de la naturaleza del material
(resistividad) y de la geometría del conductor, consideremos un conductor
cilíndrico de longitud $l$ y sección transversal de área A por el cual circula una
corriente I al aplicarse entre sus extremos una diferencia de potencial V, tal
como se muestra en la figura 1.
Si suponemos el campo eléctrico constante debe cumplirse que:
\[E = \frac{V}{l}\]
(4)
Sustituyendo los valores de [3] y [4] en [2], obtenemos que:
\[\rho = \frac{RA}{l}\]
(5)
Esta relación nos lleva a una expresión para R dada por:
\[R = \frac{\rho l}{A}\]
(6)
Según la cual R depende de la naturaleza y de la geometría del conductor.
[FIGURA: Diagrama de un conductor cilíndrico con longitud $l$ y sección transversal A, mostrando el flujo de corriente I y la diferencia de potencial V.]

Figura 1. Tramo de conductor de longitud $l$ y sección transversal
de área A, a través del cual circula una corriente I.

De (5) se define la unidad en el S.I. de resistividad como: $\Omega$.m.
La conductividad es un parámetro relacionado con el inverso de la resistividad.
Generalmente se denota con la letra griega $\sigma$ y se define como:

5

<!-- pagina 5 -->

## Página 5

\[\sigma = \frac{1}{\rho} = \frac{J}{E}\]
(7)
En término de esta cantidad, la densidad de corriente se define también como:
\[J = \sigma E\]
(8)
De [8] se deduce que J es un vector definido como el producto de un escalar $\sigma$
por el vector intensidad de campo eléctrico (E), esto es:
| | | | |
|---|---|---|---|
| | 2000.0 | $J = \sigma E$ | |
| | 1000.0 | $\sigma^{01} - \sigma^{10}$ | |
(9)
2.2. LEY DE OHM:
En 1820 George Simon Ohm (1787-1854), demostró experimentalmente que la
resistencia R de ciertos conductores (los metales) bajo condiciones de
temperatura constante, es independiente de la diferencia de potencial V
aplicada en sus extremos y de la intensidad de corriente I que circula a través
de ellos. En forma de ecuación, lo anterior se expresa así:
\[R = \frac{V}{I} = \text{constante}\]
(10)
Debido a que esta ley sólo se cumple para los metales, se dice que la misma
no describe una propiedad general de la materia, sino una característica
particular de ciertas sustancias.
Los conductores que cumplen la ley de Ohm se denominan óhmicos o lineales
(su característica I-V es una recta), mientras que los que no la obedecen se
denominan no lineales. Como ejemplo de estos últimos tenemos los materiales
semiconductores.

2.3. RESISTORES.
Un resistor es un componente de cualquier circuito, cuyo propósito es el de
tener resistencia. Los materiales usados como resistores se caracterizan por
tener un coeficiente de temperatura (CT) pequeño; o sea, la variación
porcentual de la resistencia por grado de temperatura es pequeña. Los valores
de la resistencia, del coeficiente de temperatura y la máxima potencia permitida

6

<!-- pagina 6 -->

## Página 6

en un resistor de algunos de los conductores más comunes, se muestran en la
tabla 1.
| TIPO | RANGO DE VALORES | C. T. (%/°C) | POTENCIA MÁXIMA |
|---|---|---|---|
| CARBÓN | $1\Omega - 22M\Omega$ | 0.1 | $2W$ |
| ALAMBRE | $1\Omega - 100K\Omega$ | 0.0005 | $200W$ |
| PELÍCULA METÁLICA | $0.1\Omega - 10^{10}\Omega$ | 0.0001 | $1W$ |
| PELÍCULA DE CARBÓN | $1\Omega - 100M\Omega$ | Entre 0.015 - 0.05 | $2W$ |
TABLA 1

En el caso de los resistores de carbón, existe un código de colores y una clave
para determinar el valor de la resistencia. La clave consiste en leer los anillos o
bandas de colores de izquierda a derecha (el extremo es el más próximo a la
primera banda) de tal manera que las dos primeras bandas, AB, definen las dos
primeras cifras del valor de la resistencia; la tercera banda, C, es un
multiplicador y la cuarta banda, D, indica la tolerancia o error en la
determinación de R. Así pues, el valor de la resistencia del resistor se especifica
como:
\[R = AB. 10^C \pm D\]

Para determinar el valor del resistor debemos identificar los colores según lo
indica la tabla 2.

7

<!-- pagina 7 -->

## Página 7

| COLOR | VALOR | POTENCIA DE 10 | TOLERANCIA |
|---|---|---|---|
| NEGRO | 0 | $10^0$ | $\pm 20 \%$ |
| MARRÓN | 1 | $10^1$ | $\pm 1 \%$ |
| ROJO | 2 | $10^2$ | $\pm 2 \%$ |
| ANARANJADO | 3 | $10^3$ | $\pm 3 \%$ |
| AMARILLO | 4 | $10^4$ | |
| VERDE | 5 | $10^5$ | $\pm 5 \%$ |
| AZUL | 6 | $10^6$ | |
| VIOLETA | 7 | $10^7$ | |
| GRIS | 8 | $10^8$ | |
| BLANCO | 9 | $10^9$ | |
| PLATA | | $10^{-2}$ | $\pm 10 \%$ |
| ORO | | $10^{-1}$ | $\pm 5 \%$ |
| NINGUNO | | | $\pm 20 \%$ |

TABLA 2

A manera de ejemplo, supongamos que nos dan dos resistores con la siguiente secuencia de colores:

a. Amarillo, Violeta, Marrón, Plata; $47 \times 10^1 = 470 \Omega \pm 10 \%$
b. Marrón, Negro, Rojo, Ninguno; $10 \times 10^2 = 1 K \Omega \pm 20 \%$

De acuerdo con el código de colores de la tabla 2, los resistores tendrían valores:

a. $(470 \pm 10 \%) \Omega$.
b. $(1000 \pm 20 \%) \Omega$.

2.4. POTENCIA MÁXIMA DE UN RESISTOR:
Siempre que una corriente eléctrica de intensidad $i$ circula por un resistor R, se disipa energía en forma de calor (efecto Joule) en el resistor. La tasa de

8

<!-- pagina 8 -->

## Página 8

producción de calor o potencia disipada es $P=Ri^2$. Esto hace que suba la temperatura en el resistor y si no se evita sobrepasar el límite de temperatura máxima, se puede destruir el resistor. Por lo tanto, es muy importante tener presente la potencia máxima, $P_{máx}$, que pueden soportar los resistores de carbón cuando se le va ha conectar en un circuito. A partir de este valor máximo de P, se puede determinar la máxima corriente $I_{máx}$, o la máxima caída de potencial $V_{máx}$ que puede soportar el resistor sin dañarse empleando la relación:
\[ P_{máx} = Ri_{máx}^2 = \frac{V_{máx}^2}{R} \]
(11)

2.5. AMPERÍMETROS, VOLTÍMETROS Y OHMÍMETROS:
Las cantidades $V, R$, e $I$ son cantidades macroscópicas de interés fundamental cuando se trabaja efectuando medidas eléctricas en conductores reales. Por lo tanto, son las cantidades que normalmente se miden con instrumentos debidamente calibrados. Estos instrumentos son: el amperímetro, para medir la intensidad de corriente $i$; el voltímetro, para medir la diferencia de potencia $V$ y el ohmímetro, para medir la resistencia $R$.

3. PARTE EXPERIMENTAL.
3.1 MATERIAL
* 1 fuente de poder de $0-30$ v, 6 A
* 2 multimedidores Keithley (179, 175 ó 175-A)
* 1 diodo semiconductor
* 1 Resistencia (Variable o de carbón)

3.2. PROCEDIMIENTO
Lea detalladamente el material de instrucción de los multimedidores digitales Keithley 179 y 175 en cada uno de los rangos como amperímetro, voltímetro (para medida en DC y AC) y ohmímetro.

3.2.1 CARACTERÍSTICA I-V DE UN RESISTOR.
* Realice el montaje del circuito mostrado en la figura 2.

9

<!-- pagina 9 -->

## Página 9

* Variando la salida de la fuente, para un valor fijo en el resistor R, obtenga una serie de valores (20 mínimos) de V e I.

[FIGURA: Diagrama de circuito con una fuente de voltaje E, un amperímetro A, un voltímetro V y un resistor R.]

Figura 2. Circuito para el experimento 3.2.1

3.2.2 CARACTERÍSTICA I-V DE UN DIODO SEMICONDUCTOR.
* Realice el montaje del circuito mostrado en la figura 3.
* Variando la salida de la fuente o variando el resistor R, obtenga una serie de valores (20 mínimos) de V e I.

[FIGURA: Diagrama de circuito con una fuente de voltaje E, un amperímetro A, un voltímetro V y un diodo con un resistor R en serie.]

Figura 3. Circuito para el experimento 3.2.2

4. ACTIVIDADES
* Para cada experimento construya la gráfica I Vs V, y escriba la conclusión respectiva.

10

<!-- pagina 10 -->

## Página 10

PRÁCTICA 2
DETERMINACIÓN DE UNA RESISTENCIA ELÉCTRICA

1. OBJETIVOS
* Conocer los diferentes métodos experimentales que permiten determinar una resistencia eléctrica.
* Escoger entre estos métodos, aquel que permita determinar una resistencia de la manera más práctica y precisa.

2. PARTE TEÓRICA
Ver sección 2 de la primera práctica.

3. PARTE EXPERIMENTAL
En esta parte del laboratorio, Ud. podrá determinar el valor de una resistencia eléctrica utilizando dos métodos experimentales, uno de medida indirecta y otro de medida directa.

3.1. MATERIAL
* 1 fuente de poder de $0-30$ v, 6 A
* 2 multimedidores Keithley (179, 175 ó 175-A)
* 1 Resistencia de carbón.
* 3 Resistencias variable del tipo décadas.
* 1 fuente estabilizada electrónicamente (Pila tipo D).
* Cables de conexión.

3.2. MÉTODO DE MEDIDA INDIRECTA DE UNA RESISTENCIA ELÉCTRICA.
3.2.1 AMPERÍMETRO Y VOLTÍMETRO.
* Arme el circuito mostrado en la figura 1a.
* Variando la salida de la fuente, obtenga 20 valores de corriente y voltaje.

11

<!-- pagina 11 -->

## Página 11

El análisis de este circuito nos indica que la corriente $I$ que pasa por el
amperímetro es la suma de la corriente $I_R$ que circula por el resistor R, más la
corriente $I_V$, que circula por la resistencia interna del voltímetro $R_V$, por lo que:
$I = I_R + I_V$ (1)

Como $I_R = \frac{V}{R}$, de la misma forma que $I_V = \frac{V}{R_V}$ se tiene que $I = \frac{V}{R} + \frac{V}{R_V}$
Si $R_V >> R$, prácticamente toda la corriente pasa a través de R. Por lo tanto, $V/R_V$
$\approx 0$ por lo que se puede determinar el valor de R a partir de la relación,
$R = \frac{V}{I}$ (2)

- Arme el circuito de la figura 1b.
- Variando la salida de la fuente, obtenga 20 valores de corriente y voltaje.

En este caso, la caída de tensión V es la suma de la caída de tensión en el
amperímetro $V_A$ más la caída de tensión en la resistencia $V_R$. Esto es:
$V = IR_A + IR$ (3)
Si $R_A << R$, toda la caída de potencial se debe a la resistencia R, por lo tanto $IR_A$
$\approx 0$, lo cual conduce nuevamente a la relación [2]:
$R = \frac{V}{I}$ (4)

[FIGURA: Diagrama de circuito con amperímetro, voltímetro y resistencia en dos configuraciones (1.a y 1.b)]

Figura 1. Circuito para determinar la resistencia R.
12

<!-- pagina 12 -->

## Página 12

3.2.2 PUENTE DE RESISTENCIAS:
El puente de resistencia o puente Wheatstone, se utiliza para determinar el valor
de un resistor desconocido por comparación con tres resistores cuyas
resistencias se pueden modificar. El circuito de este puente, mostrado en la
figura 2, básicamente consta de f.e.m, tres resistores de precisión [$R_1$, $R_2$ y $R_C$],
un detector V sensible a pequeñas diferencias de potencial y el resistor $R_X$ cuyo
valor de resistencia se va a determinar.
El método consiste en balancear el puente variando las resistencias $R_1$, $R_2$ y $R_C$
hasta que el detector indique cero potencial. En estas condiciones los puntos b y
d están a un mismo potencial. Por lo tanto, la caída de potencial a través de $R_X$
debe ser igual a la caída de potencial a través de $R_1$, esto es:
$I_X R_X = I_1 R_1$
De la misma forma, la caída de potencial a través de $R_C$ debe ser igual a la caída
de potencial a través de $R_2$, es decir:
$I_C R_C = I_2 R_2$
Si dividimos miembro a miembro ambas ecuaciones obtenemos para la
resistencia desconocida el valor dado por:
$R_X = R_C \frac{R_1}{R_2}$ (5)

[FIGURA: Diagrama de un puente de Wheatstone con resistencias $R_X$, $R_1$, $R_C$, $R_2$ y un voltímetro V]

Figura 2. Puente de Wheatstone.
13

<!-- pagina 13 -->

## Página 13

- Arme el circuito mostrado en la figura 2.
- Empezando con la sensibilidad mínima (rango máximo) del detector
(voltímetro), ajuste los valores $R_1$, $R_2$ y $R_C$ hasta obtener una indicación
mínima en el detector (V = 0).
- Aumente la sensibilidad del detector y repita el paso anterior.
- Ajuste cada vez más hasta obtener la indicación cero con la máxima
sensibilidad, (mínimo rango).
- Anote los valores de $R_1$, $R_2$ y $R_C$.
RECOMENDACIÓN: A pesar de que el ajuste a cero en el detector se logra
moviendo los selectores de $R_1$, $R_2$ y $R_C$, siempre es recomendable elegir una
relación $R_1/R_2$ a valores como $10^3$, $10^2$, $10^{-1}$, $1$, $10$, $10^2$, ó $10^3$. Las resistencias
$R_1$, $R_2$ y $R_C$ están constituidas por resistores variables en cuatro décadas que
permiten estimar un error del 1% del valor ajustado. Como f.e.m. puede utilizarse
una pila y como resistor $R_X$ el resistor desconocido que le suministre el profesor.

3.3. MÉTODO DE MEDIDA DIRECTA DE UNA RESISTENCIA ELÉCTRICA.
3.3.1. OHMÍMETRO
Existen multímedidores analógicos y digitales que, además de medir corriente y
voltaje, están calibrados para indicar valores de resistencia eléctrica. Esto
constituye el llamado ohmímetro.
Utilice la resistencia empleada por usted en los métodos anteriores (amperímetro
y voltímetro, puente de Wheatstone) y determine el valor con su error, utilizando
el multímedidor Keithley 175 ó 179.
14

<!-- pagina 14 -->

## Página 14

4. ACTIVIDADES:
4.1. LA PRECISIÓN DEL RESULTADO:
Los valores de R obtenidos mediante los métodos descritos anteriormente están
afectados por un error. En las mediciones donde se empleó el método expuesto
en la parte 3.2.1, el error depende de los errores con que son afectados los
valores de V e I según las especificaciones de los multímetros utilizados y el
rango empleado en las medidas correspondientes. Las mediciones donde se
empleó el método desarrollado en la parte 3.2.2, partiendo del supuesto de que
los cables de conexión carecen de resistencia y de que hay buenos contactos
eléctricos en los diferentes puntos de interconexión, las fuentes de error
provienen de las resistencias empleadas para el balanceo del puente, cuyo
valor es de $\pm 1\%$ del valor ajustado. Finalmente, el error que se comete con el
empleo del método expresado en 3.3.1, proviene del instrumento y el rango
empleado, según especificaciones del manual de instrucciones.

4.2. ACTIVIDADES ADICIONALES PREVIAS Y POSTERIORES A LA
REALIZACIÓN DE LA PRÁCTICA.
- Revise, en la bibliografía recomendada, lo relacionado con métodos
experimentales para medir resistencias eléctricas y amplíe la información
teórica que se ha dado aquí como introducción.
- Para el método 3.2.1, construya la gráfica I Vs V, aplique mínimo cuadrado y
a partir de la pendiente y su error; determine el valor, con su error, de la
resistencia suministrada.
- Para el método 3.2.2, determine el valor de $R_X$ con su error, usando la
ecuación 5.
- Para el método 3.3.1, determine el valor de $R_X$ con su error.
- Examine, analice y discuta, en términos de precisión, los métodos
experimentales utilizados.
- En base a la discusión anterior y a los resultados obtenidos, concluya acerca
del método que introduce menos error en la determinación de una resistencia
eléctrica.

15

<!-- pagina 15 -->

## Página 15

PRÁCTICA 3
DETERMINACIÓN DE LA RESISTENCIA INTERNA DE UN
VOLTÍMETRO, UN AMPERÍMETRO Y UNA FUENTE.

1. OBJETIVO
• Determinar experimentalmente la resistencia interna de un voltímetro, un
amperímetro y una fuente no estabilizada electrónicamente.

2. PARTE TEÓRICA
Ver sección 2 de la primera práctica
Los instrumentos de medidas, por razones intrínsecas a los mismos, tienden a
ofrecer una resistencia al paso de la corriente eléctrica. Esta resistencia es, en
general, variable de acuerdo a las posibilidades de medidas del instrumento, así
como el tipo de corriente, (continua o variable), a la cual se conecta.
Una fuente de f.e.m., también posee una resistencia interna que determina una caída
de tensión entre sus bornes. Aunque esta resistencia por lo general es muy pequeña,
puede ser calculada mediante un montaje experimental adecuado.

3. PARTE EXPERIMENTAL
3.1. MATERIAL
• 1 multímedidor Keithley (179, 175 ó 175-A)
• 1 Resistencia variable del tipo décadas.
• 1 fuente estabilizada electrónicamente (Pila tipo D).
• Cables de conexión.

3.2. PROCEDIMIENTO
3.2.1 RESISTENCIA INTERNA DE UN VOLTÍMETRO:
Puede demostrarse que la señal detectada por el voltímetro de la figura 1
es:
$V_m = \frac{R_v E}{R + R_v}$ (1)

16

<!-- pagina 16 -->

## Página 16

Donde: R es un resistor ajustado de tal manera que no se exceda el rango
del voltímetro; Rv corresponde a la resistencia interna del voltímetro y E la
salida de la fuente, la cual se determina con R=0. Así, conocidos R, E y
Vm, se puede calcular Rv para el rango respectivo del voltímetro.
• Mida la salida de la fuente (E)
• Arme el circuito mostrado en la figura 1.
• Seleccione el rango de 2 V en el voltímetro (179 ,175 ó 175-A).
• Ajuste un valor de R (puede ser en el orden de los MΩ) y mida Vm.
• En una tabla ordene los valores de E, Vm y R.
• Cambie el modelo del multimedidor y repita los pasos anteriores.

[FIGURA: Diagrama de circuito con una fuente de voltaje, una resistencia R y un voltímetro Vm en paralelo.]

Figura 1. Montaje experimental para determinar
la resistencia interna (Rv) de un voltímetro.

3.2.2 RESISTENCIA INTERNA DE UN AMPERÍMETRO:
Puede demostrarse que la corriente, Im detectada por el amperímetro de la
figura 2 es:
$I_m = \frac{E}{R + R_a}$ (2)

Donde: R es un resistor, ajustado de tal manera que no se exceda el
rango del amperímetro; Ra corresponde a la resistencia interna del
medidor y E es la salida de la fuente.

17

<!-- pagina 17 -->

## Página 17

• Así conociendo E, R, e Im, se puede determinar el valor de Ra, para el
rango respectivo del amperímetro.
• Mida la salida de la fuente (E)
• Arme el circuito mostrado en la figura 2.
• Seleccione el rango de 200 µA en el amperímetro.
• Ajuste un valor de R, tal que no exceda el rango del amperímetro y mida
Im.
• En una tabla ordene los valores de E, Im y R.
• Cambie el modelo del multimedidor y repita los pasos anteriores.

[FIGURA: Diagrama de circuito con una fuente de voltaje, una resistencia R y un amperímetro Im en serie.]

Figura 2. Montaje experimental para determinar
la resistencia interna Ra, de un amperímetro.

3.2.3 DETERMINACIÓN DE LA RESISTENCIA INTERNA DE UNA FUENTE:
El voltaje Vm registrado por el voltímetro de la figura 3, está dado por la
ecuación:
$V_m = \frac{ER_v}{R_s + R_v}$ (3)

Donde: Rs representa la resistencia equivalente, para el conjunto formado
por R y Rv (resistencia interna el voltímetro), las cuales se encuentran
conectadas en paralelo. Por tanto,
$R_s = \frac{RR_v}{R + R_v}$ (4)

18

<!-- pagina 18 -->

## Página 18

La ecuación (3) puede reescribirse para observar la relación lineal que hay
entre $R_s/V_m$ y $R_s$; o sea,
$\frac{R_s}{V_m} = \frac{1}{E} R_s + \frac{R_f}{E}$ (5)

• Mida la salida de la fuente (E)
• Arme el circuito mostrado en la figura 3.
• Variando la resistencia obtenga 20 valores de Vm y R (Ordénelos en una
tabla)

[FIGURA: Diagrama de circuito con una fuente de voltaje, una resistencia Rs y un voltímetro V en paralelo.]

Figura 3. Montaje experimental para determinar
la resistencia interna $R_f$, de una fuente.

4. ACTIVIDADES
4.1. RESISTENCIA INTERNA DE UN VOLTÍMETRO
• Deduzca la expresión (1)
• Determine, con su error, la resistencia interna de los voltímetros digitales 179 y
175 en el rango de 2V.
• Determine la desviación porcentual del valor medido por Ud., Rv, respecto al
valor indicado por el fabricante $R_f$ (10MΩ para 179 y 11MΩ para 175),
mediante la expresión:
$E\% = \frac{|R_f - R_v|}{R_f} \times 100$ (6)

19

<!-- pagina 19 -->

## Página 19

**4.2. RESISTENCIA INTERNA DE UN AMPERÍMETRO**
* Deduza la expresión (2)
* Determine el valor con su error, de la resistencia interna $R_a$ de los
  multimedidores Keithley 179 ó 175 en los rangos de 200µA, y 2mA.
* Determine la desviación porcentual del valor medido por Ud. $R_a$, con respecto
  al valor indicado por el fabricante $R_i$ (1kΩ para 200µA y 100Ω para 2 mA),
  mediante la ecuación (6).

**4.3. RESISTENCIA INTERNA DE UNA FUENTE**
* Deduzca las ecuaciones (3), (4) Y (5).
* Para cada valor de $R_L$ determine $R_f$, usando la ecuación (4).
* Grafique $R_f$ Vs $R_L$. Aplique mínimo cuadrado y determine la pendiente y el
  corte con sus respectivos errores.
* A partir del valor del corte, determine el valor con su error, de la resistencia
  interna de la fuente suministrada.

[FIGURA: Diagrama de un circuito con dos resistencias en serie, con voltajes V1 y V2, y corrientes I1 y I2.]

20

<!-- pagina 20 -->

## Página 20

**PRÁCTICA 4**

**CIRCUITOS ELÉCTRICOS**

**1. OBJETIVOS**
* Medir corrientes y voltajes en circuitos conectados en serie, paralelo y mixto.
* Aplicar las leyes de Kirchhoff en redes eléctricas.

**2. METODOLOGÍA**

Se usa una red en la cual hay conectadas varias baterías y cajas de resistencias. Se
determinan las intensidades de corriente utilizando valores conocidos de las
resistencias y de los voltajes de las baterías.

**3. PARTE TEORICA:**
Dos o más resistencias conectadas de modo que la misma carga fluya a través de
cada una de ellas se dice que están conectadas en serie; por ella debe circular la
misma corriente $i$.

[FIGURA: Diagrama de un circuito con dos resistencias en serie, R1 y R2, con voltajes V1 y V2, y corrientes I1 y I2.]

**Figura 1. Dos resistencias conectadas en serie por las cuales circula**
**una corriente de intensidad I.**

Para este tipo de conexión deben cumplirse las siguientes ecuaciones:

| Corriente: | $I = I_1 = I_2$ | (1.a) |
|---|---|---|
| Voltaje: | $V_{ab} = V_1 + V_2$ | (1.b) |
| Resistencia: | $R_{eq} = R_1 + R_2$ | (1.c) |

21

<!-- pagina 21 -->

## Página 21

Dos resistencias unidas como en la figura 2 se dice que están conectadas en
paralelo. Sea $i$ la corriente que va desde "a" hasta "b". En el punto "a", la corriente
se divide en dos, $i_1$ que circula por $R_1$ e $i_2$ por $R_2$.

[FIGURA: Diagrama de un circuito con dos resistencias en paralelo, R1 y R2, con voltajes V1 y V2, y corrientes I1 y I2.]

**Figura 2. Dos resistencias conectadas en paralelo, por las cuales circulan**
**las corrientes $I_1$ e $I_2$.**

Para este tipo de conexión deben cumplirse las siguientes ecuaciones:

| Corriente: | $I = I_1 + I_2$ | (2.a) |
|---|---|---|
| Voltaje: | $V_{ab} = V_1 = V_2$ | (2.b) |
| Resistencia: | $R_{eq} = \frac{R_1 R_2}{R_1 + R_2}$ | (2.c) |

A veces no es posible reducir muchas de las redes importantes de electrónica a
simples combinaciones serie-paralelo, por lo que deben utilizarse métodos
analíticos más avanzados. A tal fin, resultan muy útiles las conocidas leyes de
Kirchhoff. Estas leyes pueden ser enunciadas de la siguiente manera:

**Primera ley:** En cualquier nodo de un circuito, la suma de las corrientes que llegan
a él es igual a la suma de las corrientes que salen del mismo, es decir, la suma
algebraica de las corrientes en un nodo es igual a cero.
\[ \sum I_i = 0 \] (3)
**Segunda ley:** En una malla, la suma algebraica de los productos IR y de las f.e.m
que se encuentran en un recorrido es igual a cero.
\[ \sum IR + \sum \epsilon_i = 0 \] (4)

22

<!-- pagina 22 -->

## Página 22

Para aplicar esta Ley es necesario definir:
* **Nodo:** punto donde se unen tres o más conductores.
* **Malla:** Cualquier recorrido seguido de un circuito cerrado.
* **Signos algebraicos e intensidades:** se acostumbra tomar como positivas
  las corrientes que llegan a un nodo y negativas las que salen de él.
* **Signos algebraicos de voltajes:** Al recorrer una malla en cualquier
  dirección se encontrarán resistencias y baterías. En las resistencias las
  diferencias de potencial son positivas si se atraviesan de los puntos de mayor
  a menor potencial y negativas si se atraviesan de menor a mayor potencial.
* La f.e.m. batería o pila: es positiva si se recorre del borne (-) al borne (+) y
  negativa si se recorre de (+) a (-).

Estos arreglos son convencionales, pero una vez que se haga la selección de una
convención de signos determinada ésta debe seguirse a través de todo el
problema.

**Reglas para la aplicación correcta de las leyes de Kirchhoff:**
* Dibuje un diagrama de la red, claro y de tamaño suficiente. Use letras y
  símbolos para cada corriente, resistencia o voltaje desconocido.
* Indique el sentido de cada corriente con una flecha. Si el sentido no lo conoce,
  suponga momentáneamente un sentido en cualquier dirección. Si supone
  errado el sentido, la corriente le aparecerá con signo (-) al resolver las
  ecuaciones.
* Coloque un signo (+) al terminal positivo de cada batería y al extremo de cada
  resistencia por donde usted supone que la corriente entra.
* Si tiene "n" nodos entonces habrá (n-1) ecuaciones independientes.
* Si "m" es el número de mallas, entonces usted tendrá (m-1) ecuaciones
  independientes.

23

<!-- pagina 23 -->

## Página 23

4. PARTE EXPERIMENTAL
4.1. MATERIAL
* 1 Tablero para redes.
* 6 pilas tipo D.
* 3 Resistencias de carbón.
* 1 multimedidor Keithley modelo 179 o 175.

4.2. PROCEDIMIENTO
4.2.1. RESISTENCIAS EN SERIE
* Mida con el voltímetro la f.e.m. y con el Ohmmétro los valores de R$_{1}$ y R$_{2}$. Organice estos datos en una tabla.
* Arme el circuito mostrado en la figura 3.
* Mida las corrientes (I, I$_{1}$ e I$_{2}$) con el amperímetro.
* Mida la diferencia de potencial entre los extremos de cada resistencia.

[FIGURA: Diagrama de circuito con una fuente de voltaje (Int.) y dos resistencias (R1, R2) en serie, con voltímetros (V1, V2) y amperímetros (I, I1, I2) midiendo los valores.]
Figura 3. Circuito experimental.

4.2.2. RESISTENCIAS EN PARALELO
* Mida con el voltímetro la f.e.m. $\epsilon$ y con el Ohmmétro los valores de R$_{1}$ y R$_{2}$. Organice estos datos en una tabla.
* Arme el circuito mostrado en la figura 4.
* Mida la corriente total (I) la que circula por cada resistencia (I$_{1}$ e I$_{2}$).
* Mida la diferencia de potencial entre los extremos de cada resistencia.

24

<!-- pagina 24 -->

## Página 24

[FIGURA: Diagrama de circuito con una fuente de voltaje (Int.) y dos resistencias (R1, R2) en paralelo, con voltímetros (V1, V2) y amperímetros (I, I1, I2) midiendo los valores.]
Figura 4. Circuito experimental.

4.2.3. RED ELÉCTRICA
* Disponga las resistencias y pilas en el tablero tal como se muestra en la figura 5.
* Mida con su error los valores de $\epsilon_{1}$, $\epsilon_{2}$, $\epsilon_{3}$, R$_{1}$, R$_{2}$ y R$_{3}$.
* Arme el correspondiente circuito.
* Mida la corriente de cada rama (i$_{1}$, i$_{2}$, e i$_{3}$); para esto, rompa una rama del circuito e intercale el amperímetro (en serie). Haga revisar las conexiones por el profesor.
* Mida para cada malla, la diferencia de potencial entre los extremos de cada resistencia

[FIGURA: Diagrama de circuito con tres fuentes de voltaje (E1, E2, E3) y tres resistencias (R1, R2, R3) interconectadas en una red, con amperímetros (I1, I2, I3) midiendo las corrientes.]
Fig. 5. Circuito experimental de una red eléctrica

5. ACTIVIDADES
5.1. RESISTENCIAS EN SERIE
* Calcule la corriente que circula por el circuito y compárela con el valor medido.
* Verifique si se cumple la ecuación [1.b].

25

<!-- pagina 25 -->

## Página 25

5.2. RESISTENCIAS EN PARALELOS
* Calcule la corriente total que circula por el circuito y las corrientes i$_{1}$ e i$_{2}$. Compárelas con el valor medido.
* Verifique si se cumple la ecuación (2.-a).
* Verifique si se cumple la ecuación (2-b).

5.3. RED ELÉCTRICA
* Aplique las leyes de Kirchhoff. Resuelva las ecuaciones en las incógnitas i$_{1}$, i$_{2}$, e i$_{3}$. (Debe traerlo resuelto antes de entrar al laboratorio).
* Con los valores medidos de $\epsilon_{1}$, $\epsilon_{2}$, $\epsilon_{3}$, R$_{1}$, R$_{2}$ y R$_{3}$. Calcule los valores de i$_{1}$, i$_{2}$, e i$_{3}$
* Calcule el porcentaje de error entre los valores experimentales obtenidos para las corrientes y los calculados por las leyes de Kirchhoff.
* Verifique si se cumple la ecuación (3).
* Verifique si se cumple la ecuación (4)

26

<!-- pagina 26 -->

## Página 26

PRACTICA 5
ELEMENTOS NO LINEALES. DIODO SEMICONDUCTOR

1. OBJETIVOS

* Aplicar el método de los mínimos cuadrados en sistemas de datos que se pueden representar por medio de una función lineal.
* Determinar el factor de idealidad (n) y la corriente de saturación inversa ($I_0$) de un diodo semiconductor.

2. PARTE TEÓRICA
La resistencia eléctrica de un elemento se define por:
\[R = \frac{V}{I}\]
Donde, V es la caída de potencial e I la corriente que circula por el elemento.
Si esta razón es constante, a temperatura constante se dice que el elemento obedece a la ley de Ohm.

Un experimento interesante consiste en estudiar aquellos elementos cuya resistencia varía con la intensidad o con el voltaje (elementos no lineales). Uno de estos elementos es el diodo semiconductor. La palabra diodo significa dos electrodos.

La fabricación de un diodo semiconductor exige una muestra muy pura de un elemento semiconductor, en cuyo seno se ha introducido uniformemente una cantidad, cuidadosamente controlada y muy pequeña, de otro elemento. El material básico normal es el Silicio (Si). Este es un semiconductor, por lo que a la temperatura ambiente posee relativamente pocas cargas libres (comparado con el número de cargas libres en un conductor como el cobre). El elemento que se introduce en el silicio debe estar cerca de éste en la tabla periódica pero ha de tener un electrón de valencia mayor o menor que él mismo. Por ejemplo el boro (valencia 3) y el arsénico (valencia 5) con silicio (valencia 4). La adición de boro produce un material que actúa como si el silicio tuviera un número grande de cargas positivas

27

<!-- pagina 27 -->

## Página 27

libres. Este material se denomina semiconductor tipo p. Análogamente, la adición de arsénico produce un material que actúa como si el silicio tuviese un número grande de cargas negativas libres. Este material se denomina semiconductor tipo n. La figura (1.a), muestra un pedazo de un semiconductor tipo p y un pedazo de semiconductor tipo n, separados. La figura (1.b) muestra la formación de un diodo semiconductor cuando los dos pedazos de semiconductor (tipo p y tipo n) se unen. En el proceso de formación del diodo semiconductor ocurre una difusión de cargas positivas del lado p hacia el lado n y una difusión de cargas negativas desde el lado n hacia el lado p. estas cargas se cancelan mutuamente dejando un dipolo en la región de la unión, cuyo campo eléctrico crece hasta que contrarresta la difusión de las cargas.

[FIGURA: Tabla con tres secciones: Zona neutra, Zona de cargas, Zona neutra. Cada sección tiene dos columnas: p y n. Cada columna tiene una serie de símbolos de más y menos.]

a.- Antes de la formación
b.- Después de la formación

Figura N° 1 Diodo.

Este diodo aún cuando no está polarizado, (lo cual significa que no tiene voltaje externo aplicado) tiene un campo eléctrico en la zona de carga, el cual se manifiesta por una diferencia de potencial entre el lado p y el lado n.

Un diodo puede ser polarizado de dos maneras:
1. **Polarizacion Directa:** Cuando el terminal positivo de la fuente está conectado al material tipo p y el terminal negativo al material tipo n, tal como se muestra en la figura 2.a. en ésta, la diferencia de potencial aplicada disminuye el campo eléctrico de la zona de carga, por lo que la difusión de cargas aumenta, produciéndose una corriente eléctrica.

28

<!-- pagina 28 -->

## Página 28

2. **Polarizacion Inversa:** Cuando el terminal negativo de la fuente está conectado al material tipo p y el terminal positivo al material tipo n, tal como se muestra en la figura 2.b. En este caso, la diferencia de potencial aplicada aumenta el campo eléctrico de la zona, por lo que la difusión de cargas disminuye, no observándose ningún aumento de corriente.

[FIGURA: Diagrama de un diodo con polarización directa (a) y polarización inversa (b). Muestra la conexión de una fuente de voltaje a un diodo, con símbolos de cargas positivas y negativas en las regiones p y n, y la dirección del campo eléctrico.]

a. Polarización directa
b. Polarización inversa

Figura N° 2. Polarización de un diodo.

La figura 3 muestra el símbolo esquemático de un diodo rectificador; la flecha del símbolo del diodo indica la dirección más común de la corriente.

[FIGURA: Símbolo esquemático de un diodo rectificador con una flecha indicando la dirección de la corriente.]

Figura N° 3. Símbolo esquemático del diodo.

Si se analiza teóricamente el diodo semiconductor, se encuentra que la relación entre la corriente y el voltaje (característica I-V) para este elemento viene dada por la ecuación:
\[I = I_0 \exp \left[ \frac{eV}{nKT} - 1 \right] \quad (2)\]

29

<!-- pagina 29 -->

## Página 29

Donde:
$I_0$: Corriente de saturación inversa (En el orden de los $\mu$A para germanio y los nA para el silicio)
$V$: Caída de potencial
$e$: Carga del electrón ($1,602 \times 10^{-19}$ C)
$K$: Constante de Boltzmann ($1,38 \times 10^{-23}$ J/K)
$T$: Temperatura ambiente (300 K)
$n$: Factor de idealidad, $1 < n < 2$, (n=1 Germanio, n=2 Silicio)

Si $T \approx 300$ K y $V \ge 0$, (polarización directa) entonces: $\exp \left( \frac{eV}{nKT} \right) >> 1$; de aquí que podemos reducir (2) a:
\[I = I_0 \exp \left( \frac{eV}{nKT} \right) \quad (3)\]

La figura 4 muestra la característica I-V de un diodo.

[FIGURA: Gráfica de la característica I-V de un diodo, mostrando la corriente (I) en función del voltaje (V) para polarización directa e inversa. Se indican las regiones de polarización directa e inversa, y los valores de corriente y voltaje.]

Figura N° 4. Características I v de los diodos (Ge) y (Si)

En la región de polarización inversa se origina una corriente muy pequeña llamada corriente de saturación inversa y se le designa con $I_0$. El nombre de saturación nos recuerda que no puede obtenerse más de esta corriente en polarización inversa. En otras palabras, aumentando el voltaje inverso no se aumenta la corriente inversa. Para obtener los valores de $I_0$ y $n$ es necesario transformar la ecuación (3) a una relación lineal. Para ello se toma el logaritmo natural a dicha ecuación:

30

<!-- pagina 30 -->

## Página 30

\[
\ln I = \ln I_0 + \frac{eV}{nKT}
\]
(4)

Si los valores de $\ln I$ están afectados con un error porcentual más grande que los
valores de $V$, se pueden tomar los valores de $\ln I$ como ordenadas y $V$ como
abscisa de tal manera que la gráfica $\ln I$ en función de $V$ debe determinar una recta
cuya pendiente, m, y cuyo corte con eje ordenadas, b, están representados por las
siguientes ecuaciones, respectivamente:

\[
m = \frac{e}{nKT}
\]
(5)

\[
b = \ln I_0
\]
(6)
La recta que mejor se ajusta a estos datos, se obtiene por medio del método de los
mínimos cuadrados al regresar los "$\ln I$" sobre los "$V$" (teniendo $\ln I$ mayor error
porcentual que $V$). Mediante este método se obtiene la pendiente "m" y así n
mediante la relación (5). Como error de "m" se toma $\Delta m$. El error de "n" se obtiene
de $\Delta m$ por medio de propagación de errores.

**3. PARTE EXPERIMENTAL**
**3.1. MATERIAL**
* 1 fuente de poder de $0 - 30$ v, $6$ A
* 2 multímedidores Keithley ($175$ ó $175$-A)
* 1 diodo semiconductor
* 1 Resistencia

**3.2. PROCEDIMIENTO**
* Arme el circuito que se muestra en la figura 5. (El diodo debe estar polarizado
directamente).
* Variar la tensión de la fuente y/o variar la resistencia R, para obtener los
valores de $i_m$ y los correspondientes valores de $V$. (mínimo 20 valores)

31

<!-- pagina 31 -->

## Página 31

[FIGURA: Diagrama de un circuito con un diodo, un amperímetro, un voltímetro y una resistencia.]

**Figura Nº 5. Esquema experimental para determinar las características i-V de un
diodo**

**OBSERVACIÓN:**
El voltímetro mide directamente el voltaje del diodo (V), sin embargo, el
amperímetro mide la suma $i_m$ de las corrientes que pasan por el voltímetro $i_v$ y por
el diodo $i$, es decir,
\[
i_m = i_v + i
\]
La corriente que pasa por el voltímetro está dada por:
\[
i_v = \frac{V}{R_v}
\]
Donde: V, voltaje medio en el voltímetro (voltaje aplicado al diodo) y $R_v$,
Resistencia interna del voltímetro.
Por lo que:
\[
i_m = \frac{V}{R_v} + i
\]
Si se utiliza un multímedidor de alta resistencia de entrada (Keithley 175), se puede
asegurar que:
\[
\frac{V}{R_v} << i_m
\]
Entonces se puede hacer la siguiente aproximación:
\[
i \approx i_m
\]

32

<!-- pagina 32 -->

## Página 32

**4. ACTIVIDADES**
* Graficar $\ln I$ vs $V$
* Utilizar el método de los mínimos cuadrados para ajustar la ecuación (3) a los
datos experimentales.
* De la pendiente, hallar el factor de idealidad n usando la ecuación (5), con su
respectivo error.
* Del corte con el eje de ordenada b, hallar la corriente de saturación inversa $i_0$,
usando la ecuación (6), con su respectivo error.

33

<!-- pagina 33 -->

## Página 33

**PRÁCTICA 6**
**RESPUESTA DE LOS ELEMENTOS BÁSICOS R, L Y C A LA TENSIÓN
SENOIDAL**

**1. OBJETIVOS**
* Introducir a los estudiantes en el estudio de los circuitos en régimen senoidal.
* Estudiar al comportamiento de los circuitos RL y RC con la corriente o tensión
senoidal.
* Utilizar los circuitos RC y RL para determinar la capacitancia de un condensador y
la inductancia de una bobina, respectivamente.

**2. PARTE TEÓRICA**
Mediante la ley de Ohm y las ecuaciones básicas para el capacitor y el inductor,
podemos estudiar el comportamiento de los circuitos RL y RC en presencia de una
corriente, o la tensión senoidal.

**RESISTOR:** Para las frecuencias de líneas de potencia y frecuencias hasta de
unos cuantos kHz, el resistor, para los fines prácticos, no se ve afectado por la
frecuencia de la corriente o tensión senoidal que se aplica. Para este rango de
frecuencias, el resistor $R$ se puede considerar como una constante; es decir, cumple
con la ley de Ohm.
\[
V_R = RI
\]
(1)
Así, si se gráfica $V_R$ vs $i$ deberíamos obtener una recta cuya pendiente debe ser
numéricamente igual a la resistencia del resistor $R$.

**CAPACITOR:** a diferencia de los resistores, los capacitores son elementos que
manifiestan sus características sólo cuando se hace un cambio en la tensión o en la
corriente del circuito en que se encuentra. Además, si consideramos la situación
ideal, no disipan energía como los resistores, sino que la almacenan en una forma
que puede regresar al circuito, siempre que lo requiera su diseño. Un elemento

34

<!-- pagina 34 -->

## Página 34

construido simplemente con dos placas conductoras paralelas, separadas por un
material aislante, se denomina capacitor. La capacitancia es una medida de la
eficiencia de un capacitor para almacenar carga entre sus placas; en otras palabras,
su capacidad de almacenamiento. Un capacitor tiene capacitancia de un faradio si se
deposita en las placas una carga de un coulomb mediante una diferencia de
potencial de un voltio. Si se expresa en forma de ecuación, la capacitancia se
determina así:

\[C = \frac{q}{V_c}\]
(2)

donde: C es la capacitancia, $q$ la carga almacenada y $V_c$ = diferencia de potencial
entre las placas.

La capacitancia C es un parámetro que depende exclusivamente de la geometría del
capacitor y de la naturaleza de los materiales que se utilizan para su construcción;
especialmente, del material dieléctrico que se utiliza como material aislante. Así la
capacitancia C, es una constante. De la ecuación 2, se obtiene:

\[q = C.V_c\]

\[i = \frac{dq}{dt} = C \frac{dV_c}{dt}\]
(3)

Esta última ecuación significa que cuanto mayor sea la rapidez de cambio de la
tensión del capacitor, tanto mayor será la corriente capacitiva. Los capacitores, como
los resistores pueden ser fijos o variables. En la figura 1 se ilustran los símbolos
utilizados en cada caso.

[FIGURA: Dos símbolos de capacitor, uno fijo y otro variable]

Capacitor fijo Capacitor variable

Fig. 1. Representación simbólica de un capacitor.

35

<!-- pagina 35 -->

## Página 35

INDUCTOR: Son bobinas de varias dimensiones, diseñadas para introducir al circuito
cantidades de inductancia específicas, la inductancia de una bobina es una medida
del cambio instantáneo del flujo o de enlace de la bobina, debido a un cambio
instantáneo de la corriente que pasa por el devanado; es decir:

\[L = N \frac{d\phi}{di}\]
(4)

Donde: N es el número de vueltas del alambre, $\phi$ el flujo en webers e $i$ la corriente
eléctrica que pasa por la bobina en amperes.

Como la inductancia L de la bobina varía directamente con el flujo que enlaza el
devanado, se utilizan con frecuencia materiales ferromagnéticos para incrementar la
inductancia al hacer aumentar el flujo.

El voltaje entre los extremos del inductor se determina por la ley de Faraday,

\[V_L = L \frac{d\phi}{dt}\]
(5)

De las ecuaciones 4 y 5, se obtiene:

\[V_L = L \frac{di}{dt}\]
(6)

A cada inductor se le asocia una resistencia igual a la de las vueltas del alambre y
una capacitancia dispersa debida a la capacitancia entre las vueltas de la bobina.
Para incluir esos efectos, se muestra en la figura 2 el circuito equivalente para el
inductor. Sin embargo, la función primaria del inductor es introducir inductancia (no
resistencia o capacitancia) en la red; por esa razón se construyen los inductores de
tal manera que $R_o$ y $C_o$ sean pequeños.

[FIGURA: Circuito equivalente del inductor con resistencia y capacitancia]

Figura 2. Circuito equivalente del inductor

$R_o$ resistencia de las vueltas del alambre, $C_o$ capacitancia distribuida y L la
inductancia de la bobina.

36

<!-- pagina 36 -->

## Página 36

Los símbolos utilizados para los inductores son como ilustran la figura 3.

[FIGURA: Tres símbolos de inductor: inductor fijo con núcleo de aire, inductor fijo con núcleo de hierro, inductor variable]

Inductor fijo con Inductor fijo con Inductor variable
núcleo de aire núcleo de hierro

Figura 3. Representación simbólica de un inductor

REACTANCIA DEL CAPACITOR Y DEL INDUCTOR

[FIGURA: Dos circuitos, uno RC y otro RL]

(8) Figura 4a. Circuito RC. (8) Figura 4b. Circuito RL.

En los circuitos de las figuras 4a. y 4b, se utiliza como fuente un generador de
señales que puede suministrar un voltaje senoidal igual a:

\[V = V_o \text{sen}(\omega t)\]
(7)

Esta fuente genera en el circuito respectivo una corriente de la forma:

\[i = I_o \text{sen}(\omega t - \theta)\]
(8)

donde: $V_o$ es la amplitud del voltaje, $I_o$ la amplitud de la corriente, $\omega = (2\pi f)$
frecuencia angular y $\theta$ diferencia de fase entre la corriente y el voltaje.

La corriente $i$ causa en el resistor R una caída de voltaje $V_R$ dada por la ecuación 1;
en el capacitor de la figura 4.a, una diferencia de potencial dada por:

\[V_c = \frac{1}{C} \int i dt\]
(9)

37

<!-- pagina 37 -->

## Página 37

y en el inductor del circuito de la figura 4.b, una diferencia de potencial igual a:

\[V_L = L \frac{di}{dt}\]

La oposición del resistor a la corriente $i$ se mide por la resistencia:

\[R = \frac{V_R}{I}\]
(10)

En el mismo sentido se define la reactancia del capacitor como:

\[X_C = \frac{V_C}{I}\]
(11)

Y la reactancia del inductor, como:

\[X_L = \frac{V_L}{I}\]
(12)

Se puede demostrar, en base a las ecuaciones 9, 6, 11 y 12, que los módulos de las
reactancias instantáneas $X_C$ y $X_L$ están dadas por las ecuaciones:

\[|X_C| = \frac{1}{\omega C}\]
\[|X_L| = \omega L\]
(13)

3. PARTE EXPERIMENTAL
3.1. MATERIAL
* Un generador de funciones (senoidal)
* Un resistor variable del tipo décadas.
* Un capacitor.
* Una bobina.
* 2 multimedidores digitales Keithley mod. 175 o 175 A.

3.2. PROCEDIMIENTO

3.2.1. EXPERIMENTO 1: Determinación de la reactancia capacitiva $X_C$.
* Arme el circuito que se muestra en la figura 5.a.
* Fije la frecuencia, del generador de funciones, alrededor de 200 Hz.
* Fije un valor de resistencia.
* Proceda a tomar una serie de 20 datos de corriente, $I$ y de voltaje, $V_C$
moviendo el control de amplitud en su generador.

38

<!-- pagina 38 -->

## Página 38

3.2.2. EXPERIMENTO 2: Determinación de la reactancia inductiva $X_L$.
* Arme el circuito que se muestra en la figura 5.b.
* Repita los pasos 2, 3 y 4 del experimento 1.

[FIGURA: Diagrama de circuito RC (a) y RL (b) con fuentes de voltaje, resistencias, capacitores e inductores.]

Figura 5. Circuitos RC (a) y RL (b) para determinar las reactancias capacitiva, $X_C$ e
inductiva, $X_L$, con una frecuencia fija.

3.2.3. EXPERIMENTO 3: Determinación de la capacitancia C.
* Arme el circuito que se muestra en la figura 6.a.
* Fije un valor e el resistor.
* Varíe la frecuencia 20 veces en un rango comprendido entre 200Hz y
1200Hz, midiendo para cada frecuencia los correspondientes valores de
voltaje en el capacitor, $V_C$ y en el resistor, $V_R$.

3.2.4. EXPERIMENTO 4: Determinación de la inductancia L.
* Arme el circuito mostrado en la figura 6.b.
* Repita los pasos 2 y 3 del experimento 3 (Para cada frecuencia se mide $V_L$
y $V_R$)

[FIGURA: Diagrama de circuitos RC (a) y RL (b) para determinar los valores de C y L, respectivamente.]

Figura 6. Circuitos RC (a) y RL (b) para determinar los valores de C y L,
respectivamente.

38
39

<!-- pagina 39 -->

## Página 39

4. ACTIVIDADES

4.1. EXPERIMENTO 1

* Demostrar $|X_C| = \frac{1}{C\omega}$.

* Grafique $V_C$ en función de I.

* Aplique mínimo cuadrado para ajustar la recta y determine los valores de la
pendiente (m) y corte (b).

* Determine el valor de $X_C$ con su respectivo error, mediante el valor de la
pendiente.

* Compare con el valor teórico.

4.2. EXPERIMENTO 2

* Demostrar $|X_L| = L\omega$

* Grafique $V_L$ en función de I.

* Aplique mínimo cuadrado para ajustar la recta y determine los valores de la
pendiente (m) y corte (b).

* Determine el valor de $X_L$ con su respectivo error, mediante el valor de la
pendiente.

* Compare con el valor teórico.

4.3. EXPERIMENTO 3

* Para cada valor de $V_R$ y $V_C$. Calcule el valor de $X_C$, usando la ec. 11.

* Grafique $X_C$ en función de $1/\omega$.

* Aplique mínimo cuadrado para ajustar la recta, determine m y b.

* Determine el valor de C con su respectivo error, mediante la pendiente.

* Calcule la desviación porcentual, utilizando el valor teórico (ver tabla N°1).

4.4. EXPERIMENTO 4

* Para cada valor de $V_R$ y $V_L$. Calcule el valor de $X_L$, usando la ec. 12.

* Grafique $X_L$ en función de $\omega$.

* Aplique mínimo cuadrado para ajustar la recta, determine m y b.

* Determine el valor de L con su respectivo error, mediante la pendiente.

* Calcule la desviación porcentual, utilizando el valor teórico (ver tabla N° 2 y 3).

40

<!-- pagina 40 -->

## Página 40

PRÁCTICA 7
CIRCUITOS RESONANTES

1. OBJETIVOS.

* Determinar el valor de la frecuencia de resonancia de un circuito con L y C en
serie.

* Determinar el valor de la inductancia L de una bobina cuando ésta se conecta en
serie con una capacitancia C conocida en circuito resonante.

* Determinar el valor de la frecuencia de resonancia de un circuito con L y C en
paralelo.

2. PARTE TEÓRICA.

Para entender el fenómeno de la resonancia, debemos, en primer lugar tener claro el
concepto de vibraciones forzadas o simplemente oscilaciones. Las vibraciones
forzadas constituyen un movimiento producido cuando a un sistema vibratorio se le
aplica una fuerza externa vibratoria, cuyas vibraciones resultantes se caracterizan
por tener dos componentes; una, llamada transientes, cuya frecuencia es la
frecuencia natural del sistema y otra llamada componente estacionaria en la cual la
frecuencia es igual a la de la fuerza aplicada.

La amplitud de la vibración estacionaria es máxima cuando la frecuencia de la fuerza
aplicada es igual a la frecuencia natural del sistema, si no hay amortiguamiento. A
esta condición se le llama resonancia y se dice que el sistema resuena bajo los
efectos de la fuerza aplicada.

Los circuitos eléctricos en los cuales están presentes inductancias (bobinas) y
capacitancias (condensadores) a la vez, también pueden experimentar el fenómeno
de resonancia y por eso se les llama circuitos resonantes.

41

<!-- pagina 41 -->

## Página 41

Gran parte de la importancia práctica de los circuitos R-L-C en serie surge de la
manera en que estos circuitos responden ante fuentes de diferente frecuencia
angular $\omega$. Por ejemplo, un tipo de circuito sintonizador que se utiliza en los
radiorreceptores es simplemente un circuito R-L-C en serie. Una señal de radio de
frecuencia determinada genera una corriente de la misma frecuencia en el circuito
receptor, pero la amplitud de la corriente es máxima si la frecuencia de la señal es la
misma que la frecuencia a la que el circuito receptor está sintonizado. Este efecto se
llama resonancia. Por lo tanto, en los circuitos resonantes, la magnitud física que
entra en resonancia es la corriente eléctrica (I).

Si conectamos una fuente de corriente alterna de amplitud de voltaje constante E y
frecuencia angular ajustable $\omega$ entre los extremos de un circuito R-L-C en serie.
La amplitud de corriente es:

$I = \frac{E}{Z}$ (1)

Donde Z es la impedancia del circuito, la cual está dada por la siguiente expresión:

$Z = \sqrt{R^2 + (X_L - X_C)^2}$ (2)

Conforme se modifica la frecuencia angular de la fuente, la amplitud de corriente
varía como se muestra en la figura 1, el valor máximo de I se presenta a la
frecuencia a la que z es mínima ($X_L = X_C$). La frecuencia angular $\omega_0$ a la que se
presenta el máximo de I se conoce como frecuencia angular de resonancia. Se
trata de la frecuencia angular a la cual las reactancias inductiva y capacitiva son
iguales,

$\omega_0 L = \frac{1}{\omega_0 C}$ (3)

Despejando $\omega_0$ y sabiendo que es igual a $2\pi f_0$. Se obtiene la frecuencia de
resonancia, cuya expresión es:

$f_0 = \frac{1}{2\pi\sqrt{LC}}$ (4)

42

<!-- pagina 42 -->

## Página 42

Los circuitos con R-L-C en paralelo también presentan el efecto de resonancia y
ocurre cuando la corriente es mínima, obteniéndose la misma frecuencia de
resonancia que la de los circuitos con R-L-C en serie.

[FIGURA: Gráfico de corriente vs frecuencia con $I_{máx}$ y 0.707 $I_{máx}$ marcados.]

Figura 1. Curva características de un circuito resonante con L y C en serie.

3. PARTE EXPERIMENTAL.

3.1 MATERIAL
* Un generador de funciones (senoidal)
* Un resistor variable del tipo décadas.
* Un capacitor o condensador.
* Una bobina o inductor.
* Un multímedidor digital Keithley mod.175.A
* Un voltímetro analógico.

3.2 PROCEDIMIENTO

3.2.1. EXPERIMENTO 1: L y C en serie.
* Determine el valor de $f_o$ mediante la ec. 4. Usando los valores de L y C
  indicados en la guía.
* Arme el circuito que se muestra en la figura 2.a. Hágalo revisar por su
  profesor.

43

<!-- pagina 43 -->

## Página 43

* Varíe la frecuencia, desde $f_1$ hasta $f_2$, mediante el generador (G). Para
  cada valor de f anote el correspondiente a la intensidad de corriente, i,
  manteniendo el voltaje constante utilizando el control de amplitud del
  generador.
  NOTA: $f_1 < f_o < f_2$

3.2.2. EXPERIMENTO 2: L y C en paralelo.
* Repetir los pasos anteriores pero para el circuito mostrado en la figura 2.b.

[FIGURA: Diagrama de dos circuitos. (a) Circuito serie RLC con voltímetro y amperímetro. (b) Circuito paralelo RLC con voltímetro y amperímetro.]

Figura 2. Circuitos resonantes (a) L y C en serie, (b) L y C en paralelo.

4. ACTIVIDADES

4.1. EXPERIMENTO 1
* Grafique i vs f.
* De la gráfica determine el valor extremo de i, ($I_{máx}$). Con este valor se obtiene
  $f_o$.
* Conocidos los valores de C y $f_o$, determine el valor de L aplicando la ec. 4.

4.2. EXPERIMENTO 2
* Grafique i vs f.
* De la gráfica determine el valor extremo de i, ($I_{mín}$). Con este valor se obtiene
  $f_o$.

44

<!-- pagina 44 -->

## Página 44

RECOMENDACIONES.

* Es recomendable realizar la gráfica i vs. f. sin desmontar los equipos para poder
  incrementar el número de datos en ciertas regiones de la curva (si es necesario).

* La selección del amperímetro y el voltímetro implica tomar en cuenta la limitación en
  el rango de frecuencia de los mismos.

* Se define el ancho de banda de frecuencia al intervalo comprendido entre las
  frecuencias $f_1$ y $f_2$, ($f_1 - f_2$) obtenidas de la gráfica i vs. f con L y C en serie, tal como
  se indica en la figura 1.

[FIGURA: Diagrama de dos circuitos. (a) Circuito serie RLC con voltímetro y amperímetro. (b) Circuito paralelo RLC con voltímetro y amperímetro.]

45

<!-- pagina 45 -->

## Página 45

PRÁCTICA 8

CARGA Y DESCARGA DE UN CAPACITOR

1. OBJETIVOS
* Familiarizar al estudiante con el uso del osciloscopio.
* Visualizar en el osciloscopio las curvas de carga y descarga de un capacitor.
* Determinar la capacitancia de un capacitor, mediante medidas realizadas con el
  osciloscopio en las curvas de carga o de descarga.

2. PARTE TEÓRICA

2.1. CAPACIDAD DE UN CONDUCTOR.

Se denomina capacidad C de un conductor aislado al cociente entre la carga
que posee y el potencial V (diferencia de potencial relativo a un cero de
potencial infinito) al cual se encuentra el mismo. Esto es:
\[ C = \frac{q}{V} \]
Debido a que el potencial es siempre proporcional a la carga, la capacidad
definida por [1] no depende de V ni de Q, sino del tamaño y la forma del
conductor. Esto se demuestra fácilmente para un conductor esférico. De radio
R, en cuyo caso el potencial esta dado por:
\[ V = \frac{1}{4\pi\epsilon_o} \frac{q}{R} \]
Que sustituido en [1] conduce a la relación:
\[ C = 4\pi\epsilon_o R \] (2)

La ecuación [2] nos dice que la capacidad de un conductor no depende de V ni
de q, como se dijo antes, sino del tamaño y la forma del conductor. Así, para
una esfera, observamos que la capacidad es proporcional al radio R de la
misma.

La unidad de capacidad se deduce de [1] y para el sistema M.K.S. se denomina
Faradio (1), es decir:

46

<!-- pagina 46 -->

## Página 46

\[
1 \text { Faradio }(F)=\frac{I C}{I V}
\]
Debido a que el Faradio es una unidad muy grande, en la práctica se usan sub-múltiplos de ella, tales como:
microfaradio, $\mu \mathrm{F}$, $1 \mu \mathrm{F}=10^{-6} \mathrm{~F}$
nanofaradio, $\mathrm{nF}$, $1 \mathrm{nF}=10^{-9} \mathrm{~F}$
picofaradio, $\mathrm{pF}$, $1 \mathrm{pF}=10^{-12} \mathrm{~F}$

2.2. CAPACITORES O CONDENSADORES.
Un capacitor o condensador es un dispositivo o sistema formado por dos conductores que poseen cargas iguales y opuestas, separados una distancia, por lo general, muy pequeña.
Un capacitor típico se compone de un par de placas paralelas de área A, separadas por una distancia d, tal como se muestra en la figura 1. La función fundamental de un capacitor es la de almacenar carga eléctrica y también energía. Esta función de los capacitores es la que determina sus amplias aplicaciones en electricidad y electrónica.

2.3. CÁLCULO DE LA CAPACIDAD O CAPACITANCIA.
El cálculo de la capacitancia para cualquier tipo de capacitor no es difícil. Para geometrías sencillas; se puede hallar en primer lugar la magnitud del campo eléctrico E mediante la Ley de Gauss y
[FIGURA: Diagrama de un capacitor de placas paralelas con campo eléctrico E y distancia d]
Figura 1. Capacitor de placas paralelas.

84
47

<!-- pagina 47 -->

## Página 47

luego, integrando el campo a lo largo de una trayectoria cualquiera, se calcula la diferencia de potencial V entre las placas mediante la relación:
\[
V=-\int_{a}^{b} \vec{E} \cdot d \vec{l}
\]
Así, para un capacitor de placas paralelas, la capacidad C esta dada por:
\[
C=\frac{\varepsilon_{0} A}{d}
\]
(3)
En esta ecuación A es el área de las placas del condensador, d es la distancia de separación entre ellas y $\varepsilon_{0}$ es la constante de permitividad cuyo valor es:
$\varepsilon_{0}=8.85 \times 10^{-12} \mathrm{C}^{2} / \mathrm{Nm}^{2}$
La ecuación [3] nos permite concluir que la capacidad de un condensador depende solamente de la forma y disposición geométrica de los conductores que forman el capacitor.
En la práctica se acostumbra rellenar el espacio entre las placas con un material aislante, conocido como dieléctrico, con la finalidad de aumentar la capacidad. Los materiales aislantes o dieléctricos varían en cuanto a su capacidad para soportar un campo eléctrico, a esta capacidad se le llama "constante dieléctrica" del material.

2.4. CARGA Y DESCARGA DE UN CAPACITOR.
La figura 2 representa el circuito de un capacitor y un resistor (circuito RC) conectados en serie a una fuente de voltaje dc. En el instante en que se cierra el interruptor S a la posición 1, el capacitor C que inicialmente estaba descargado comienza a cargarse a través de la resistencia R. En todo momento, durante el proceso de carga del capacitor, debe cumplirse la segunda ley de Kirchoff, es decir, que la suma de los voltajes de la resistencia, $V_{R}$, y del capacitor, $V_{C}$, debe ser igual al voltaje de la fuente. Esto es:
$V_{0}=V_{R}+V_{C}$ o sea $V_{0}=i R+q / C$
Pero como $i=d q / d t$ se tiene finalmente que:
\[
V_{0}=R \frac{d q}{d t}+\frac{q}{C}
\]
(4)
85
48

<!-- pagina 48 -->

## Página 48

[FIGURA: Diagrama de un circuito RC con un interruptor S, resistencia R y capacitor C]
Figura 2. Esquema de un circuito RC.
La expresión (4) representa la "ecuación diferencial" del circuito, cuya solución es:
\[
q=C V_{0}\left(1-e^{-t / R C}\right)
\]
(5)
Del análisis de esta relación se puede notar lo siguiente:
1. En el instante $t=0$ (momento de colocar el interruptor en la posición 1) el voltaje del capacitor $V_{C}$ es cero.
2. Para un tiempo $t=\infty$ (tiempos largos con el interruptor en la posición 1) el voltaje del capacitor $V_{C}$ es igual al de la fuente, $V_{0}$.
Supongamos que ahora pasamos el interruptor S de la posición 1 a la posición 2. En estas condiciones, se desconecta la fuente y el capacitor comienza a descargarse a través de la resistencia R. Por lo tanto se tiene que $V_{C}=V_{R}$, o sea:
\[
\frac{q}{C}=-R \frac{d q}{d t}
\]
(6)
La ecuación (6) representa la "ecuación diferencial" del circuito y el signo menos significa que la corriente $i$ circula en sentido contrario con relación al proceso de carga. La solución a ésta ecuación es:
\[
q=V_{0} C e^{-t / R C}
\]
(7)
Del análisis de esta ecuación notamos que:
1. En el instante $t=0$ (momento en que el interruptor S pasa a la posición 2) el voltaje del capacitor $V_{C}$ es el mismo de la fuente $V_{0}$.
2. Para $t=\infty$ (tiempos largos con el interruptor S en la posición 2) el voltaje del capacitor $V_{C}$ es cero.

86
49

<!-- pagina 49 -->

## Página 49

Para lo anterior podemos concluir que un capacitor requiere de cierto tiempo $t$ para cargarse y también para descargarse. La carga y descarga del capacitor está gobernada por el factor $e^{-RC}$. El producto RC tiene dimensiones de tiempo y se conoce como "constante de tiempo" del circuito y se designa por la letra griega "$\tau$" ($\tau=RC$). R debe expresarse en ohmios y C en Faradios.
Un análisis breve del factor citado anteriormente, en términos de la constante de tiempo, permite ver que en un tiempo $t=RC$ el valor del exponencial es $e^{-1}$ cuyo valor numérico es 0.368 por lo que podemos decir que para un tiempo equivalente a una constante de tiempo el capacitor adquiere durante el proceso de carga un voltaje de $(1-0.368)$ veces $V_{0}$ $(0,632V_{0})$, equivalente al 63.2% de $V_{0}$, aproximadamente; por lo largo, durante el proceso de descarga, en el mismo tiempo, el capacitor reduce su voltaje hasta 0.368 veces $V_{0}$, o sea 36.8% de $V_{0}$. La figura 3 representa la gráfica del voltaje de carga y descarga de un capacitor en función del tiempo $t$.
[FIGURA: Gráfico de porcentaje de voltaje de carga y descarga de un capacitor en función del tiempo]
Figura 3. Porcentaje del voltaje de carga y descarga de un capacitor en función del tiempo.

87
50

<!-- pagina 50 -->

## Página 50

1.  **PARTE EXPERIMENTAL**
El circuito de la figura 2 se realizará mediante la sustitución de la fuente de voltaje
constante $V_0$ y el interruptor S por un generador de pulsos de duración de encendido
$T_e$ y de duración de apagado $T_a$, como se muestra en la figura 4.

[FIGURA: Diagrama de un circuito con un generador de pulsos y un capacitor, mostrando las señales de voltaje en el tiempo.]

**Nótese en la figura 4 que durante el tiempo $T_e$ el circuito tiene aplicado el voltaje $V_0$
(interruptor S en la posición 1) y por lo tanto durante ese tiempo el capacitor se carga
a través de la resistencia. Durante el tiempo $T_a$ el voltaje aplicado al circuito es cero
(interruptor S en la posición 2) por lo tanto durante ese tiempo, el capacitor se**

[FIGURA: Gráfico de voltaje vs tiempo, mostrando la equivalencia entre la señal pulsante y la fuente de voltaje constante con el interruptor en dos posiciones.]

**Figura 5. Equivalencia entre la señal pulsante y la fuente de voltaje
constante con el interruptor en las dos posiciones.**

51

<!-- pagina 51 -->

## Página 51

**3.1. MATERIAL**
*   1 osciloscopio.
*   1 generador de funciones (cuadrada).
*   1 resistencia de décadas.
*   1 capacitor

**3.2. PROCEDIMIENTO**
*   Arme el circuito de la figura 6 y hágalo revisar por el profesor.

[FIGURA: Diagrama de un circuito RC con un generador de funciones y un osciloscopio.]

**Figura 6. Circuito RC a utilizar en la práctica.**

*   Ajuste las escalas de tiempo y de voltaje del osciloscopio para tener en la
    pantalla del mismo una sola curva de carga y descarga del capacitor.
*   Con la imagen bien estable en la pantalla del osciloscopio tome un número
    suficiente de valores del voltaje del capacitor para diferentes tiempos.
*   Con un ohmímetro determine el valor de la resistencia conectada en serie con
    el capacitor. Anote el valor de la resistencia de entrada del generador.
*   Mida el voltaje $V_0$, conectando en paralelo el generador al osciloscopio.
*   Cambie el capacitor utilizado por otro cuyo valor sea varias veces mayor o
    menor (aproximadamente unas diez veces). Sin cambiar la frecuencia de la
    señal empleada obtenga la imagen de carga y descarga en el osciloscopio.
    Describa lo que observa y explique lo que ocurre.

52

<!-- pagina 52 -->

## Página 52

**4. ACTIVIDADES**

*   Con los datos obtenidos, grafique $\operatorname{Ln}\left[\frac{V_0-V_c}{V_0}\right]$ para la carga en función del
    tiempo, siendo $V_0$ el valor de la fuente. Si los datos los tomó en la curva de
    descarga, entonces grafique $\operatorname{Ln}\left[\frac{V_c}{V_0}\right]$ en función del tiempo.
*   De la recta que resulta, determine el valor de la pendiente, usando el método de
    mínimo cuadrado
*   A través de la pendiente determine el valor de la capacitancia tomando como valor
    de R la suma de la resistencia utilizada más la resistencia de la fuente (50 ó
    600)$\Omega$.
*   Determine la desviación procentual del valor indicado por el fabricante para la
    capacitancia $C_R$, con respecto al valor C determinado por usted.

53

<!-- pagina 53 -->

## Página 53

**TABLA 1: VALORES DE LOS CONDENSADORES EXISTENTES EN EL
LABORATORIO.**

| N° DE BIENES | CAPACITANCIA |
| :----------- | :----------- |
| Cap 01       | 2,152 $\mu$F |
| Cap 02       | 103,0 nF     |
| Cap 03       | 10,09 nF     |
| T-9          | 5,106 $\mu$F |
| T-10         | 3,495 $\mu$F |
| T-15         | 45,52 nF     |
| T-16         | 5,081 nF     |
| 5317         | Arcilla: 4,368 nF |
| 68F,S        | Rectangular: 1,014 $\mu$F |
| 5319         | Negro: 229,2 nF |
|              | Arcilla: 7,577 nF |
| 5320         | Arcilla: 100,7 nF |
| 5323         | Mostaza: 489,2 nF |
|              | Arcilla: 6,860 nF |
|              | Gris: 198,6 nF |
| 5327         | 1,004 $\mu$F |
| 5329         | Arcilla: 8,810 nF |
|              | Negro: 228,7 nF |
| 5330         | Arcilla: 3,942 nF |
|              | Amarillo: 1,013 $\mu$F |

54

<!-- pagina 54 -->

## Página 54

TABLAS 2 y 3: VALORES DE LAS INDUCTANCIAS EXISTENTES EN EL LABORATORIO.

| N° BIENES | TIPO DE CONEXIÓN |
|---|---|---|
| | A -M | M - E | A - E |
| 5338 | 1,962 mH | 2,706 mH | 8,54 mH |
| 5339 | 1,942 mH | 2,748 mH | 8,55 mH |
| 5340 | 0,975 H | 1,468 H | 4,421 H |
| 5341 | 0,966 H | 1,411 H | 4,324 H |
| 5343 | 7,845 mH | 11,32 mH | 34,62 mH |
| 5344 | 7,902 mH | 11,70 mH | 35,34 mH |
| 5345 | 502,1 µH | 703,8 µH | 2,188 mH |

| N° BIENES | TIPO DE CONEXIÓN |
|---|---|---|---|---|---|
| | INFERIOR | DIAGONAL 1 | MEDIO | DIAGONAL 2 | SUPERIOR |
| 5346 | 8,6 µH | 8,5 µH | 17,8 µH | 8,6 µH | 2,9 µH |
| 5347 | 7,7 µH | 7,6 µH | 17,2 µH | 7,4 µH | 2,9 µH |

55
@

<!-- pagina 55 -->

## Página 55

MULTIMEDIDOR KEITHLEY 175 Y 175 A
VOLTAJE D. C.

| RANGO | RESOLUCIÓN | PRECISIÓN |
|---|---|---|
| 200 mV | 10µV | 0.03%+2d |
| 2V | 100µV | 0.03%+2d |
| 20V | 1mV | 0.03%+2d |
| 200V | 10mV | 0.03%+2d |
| 1000V | 100mV | 0.03%+2d |
RESISTENCIA DE ENTRADA: 11MΩ EN LOS RANGOS DE 200 mV, 2V Y 20V. 10Ω PARA LOS RANGOS 200V 1000V

INTENSIDAD DE CORRIENTE AC. (TRMS)
| RANGO | VOLTAJE MAX. EN EL AMP | PRECISIÓN |
|---|---|---|---|---|
| | | 20Hz-50Hz | 50Hz-10kHz | 10kHz-30kHz |
| 200µA-20mA | 0.3V | 1%+20d | 0.8%+20d | 2%+50d |
| 20mA | 0.3V | 1%+20d | 0.8%+20d | |
| 2000mA | 0.3V | 1%+20d | 0.8%+20d | |
| 10A | 0.3V | 1.5%+20d | 1%+20d | |

VOLTAJE A. C. (TRMS)
| RANGO | PRECISIÓN |
|---|---|---|---|---|---|
| | 20Hz-50Hz | 50Hz-10kHz | 10kHz-20kHz | 20kHz-50kHz | 50kHz-100kHz |
| 2V-750V | 1%+20d | 0.5%+20d | 1%+40d | 2.5%+75d | 5%+200d |
| 200mV | 1%+20d | 0.5%+20d | 1.5%+40d | 8%+75d | |

INTENSIDAD DE CORRIENTE D. C.
| RANGO | RESOLUCIÓN | VOLTAJE MAX. EN EL AMP | PRECISIÓN |
|---|---|---|---|
| 200µA | 10nA | 0.3V | 0.15%+2d |
| 2mA | 100nA | 0.3V | 0.15%+2d |
| 20mA | 1µA | 0.3V | 0.15%+2d |
| 200mA | 10µA | 0.3V | 0.2%+2d |
| 2000mA | 100µA | 0.3V | 0.2%+2d |
| 10A | 1mA | 0.3V | 0.75%+2d |

RESISTENCIA
| RANGO | RESOLUCIÓN | PRECISIÓN |
|---|---|---|
| 200 Ω | 10 | 0.05%+2d |
| 2 KΩ | 100 | 0.05%+2d |
| 20 KΩ | 1 | 0.05%+2d |
| 200 KΩ | 10 | 0.05%+2d |
| 2 MΩ | 100 | 0.05%+2d |
| 20 MΩ | 1 | 0.2%+2d |
| 200 MΩ | 100 | 2.0%+1d |
COEFICIENTES DE TEMPERATURA (C. T.): (0°-18°C): 0.1XESPECIFICACIONES DE LA PRECISIÓN INDICADA PARA CADA GRADO°C EXCEPTO 0 (0.07%+2d)°C PARA 50Hz-10kHz EN VAC

56
@

<!-- pagina 56 -->

## Página 56

MULTIMEDIDOR KEITHLEY 179 Y 179 A
VOLTAJE D. C.

| RANGO | LEC. MAX. | PRECISIÓN | C. T. | MAX. SEÑAL PERMITIDA |
|---|---|---|---|---|
| 200mV | 199.99 | 0.04%+3d | (0.006%+0.4d)°C | 1.200V momentáneo |
| 2V | 1,9999 | 0.04%+1d | (0.006%+0.2d)°C | 1.200V momentáneo |
| 20V | 19.999 | 0.04%+1d | (0.006%+0.2d)°C | 1.200V momentáneo |
| 200V | 199.99 | 0.04%+1d | (0.006%+0.2d)°C | 1.200V momentáneo |
| 1200V | 1200.0 | 0.04%+1d | (0.006%+0.2d)°C | 1.200V momentáneo |
RESISTENCIA DE ENTRADA: 10MΩ±1%

VOLTAJE A. C.

| RANGO | LEC. MAX. | PRECISIÓN | C. T. | MAX. SEÑAL PERMITIDA |
|---|---|---|---|---|
| 200mV | 199.99 | 0.7%+15d | (0.07%+2d)°C | 1000Vrms, 1400Vp |
| 2V | 1,9999 | 0.6%+15d | (0.07%+2d)°C | 1000Vrms, 1400Vp |
| 20V | 19.999 | 0.6%+15d | (0.07%+2d)°C | 1000Vrms, 1400Vp |
| 200V | 199.99 | 0.6%+15d | (0.07%+2d)°C | 1000Vrms, 1400Vp |
| 1200V | 1200.0 | 0.6%+15d | (0.05%+2d)°C | 1000Vrms, 1400Vp |
IMPEDANCIA DE ENTRADA: 1MΩ±1% EN SERIE CON UN CAPACITOR MENOR DE 75 pF

INTENSIDAD DE CORRIENTE AC Y DC

| RANGO | LEC. MAX. | PRECISIÓN | C. T. |
|---|---|---|---|---|---|
| | | DC | AC | DC | AC |
| 200µA | 199.99 | 0.2%+2d | 1%+15d | (0.01%+2d)°C | (0.07%+2d)°C |
| 2mA | 1,9999 | 0.2%+2d | 1%+15d | (0.01%+2d)°C | (0.07%+2d)°C |
| 20mA | 19.999 | 0.2%+2d | 1%+15d | (0.01%+2d)°C | (0.07%+2d)°C |
| 200mA | 199.99 | 0.2%+2d | 1%+15d | (0.01%+2d)°C | (0.07%+2d)°C |
| 2000mA | 1999.9 | 0.2%+2d | 1%+15d | (0.01%+2d)°C | (0.07%+2d)°C |
LAS RESISTENCIAS DE ENTRADA SON 1KΩ, 100Ω, 10Ω Y 0.1Ω RESPECTIVAMENTE

RESISTENCIA

| RANGO | LEC. MAX. | PRECISIÓN | C. T. |
|---|---|---|---|---|
| | | HI | LO | HI | LO |
| 2KΩ | 1,9999 | 0.15%+1d | | (0.02%+2d)°C |
| 20 KΩ | 19.999 | 0.04%+1d | 0.15%+15d | (0.003%+0.2d)°C | (0.02%+2d)°C |
| 200 KΩ | 199.99 | 0.04%+1d | 0.15%+15d | (0.003%+0.2d)°C | (0.02%+2d)°C |
| 2000 KΩ | 1999.9 | 0.04%+1d | 0.15%+15d | (0.003%+0.2d)°C | (0.02%+2d)°C |
| 20 MΩ | 19.999 | 0.10%+1d | | (0.02%+2d)°C |

57